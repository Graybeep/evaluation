"""The single place this repo talks to an LLM (CLAUDE.md §4.5, §7.1, §7.3).

Everything that needs a model — the agent under test, the calibration agents, scenario
expansion, the feasibility reference solver, the judge — goes through `LLMClient`, so
model pinning, usage accounting, response caching and secret scrubbing exist in exactly
one place.

Model pinning (§4.5 / §13.1)
----------------------------
CLAUDE.md's example pin (`claude-sonnet-4-5-20250929`) predates the current model line:
current Claude model IDs carry **no date suffix** and the bare string *is* the pin — see
the note added to §4.5. `MODELS` below is the pinned set; the resolved id is recorded in
every trace, every verdict and every report.

Sampling
--------
`temperature` is rejected (HTTP 400) by the current model family, so this client never
sends it. Variation for scenario expansion comes from seed-varied prompts, not from a
sampling knob; run-to-run variation for repeated sampling (§4.6) comes from the model
being non-deterministic by default. The cache key keeps a `temperature` slot so keys
stay stable if that ever changes.

No server-side refusal fallbacks
--------------------------------
Deliberate. A fallback would silently answer a run on a *different* model, and this
harness reports per-model numbers; a rerouted refusal would corrupt exactly the
measurement we exist to make. `stop_reason == "refusal"` is handled explicitly instead —
for a guardrail tester a refusal is frequently the *correct* outcome.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable

from are.runner.cache import CacheMiss, ResponseCache

# Pinned model ids. Never use a floating alias here (§13.1).
MODELS = {
    "agent": os.environ.get("ARE_AGENT_MODEL", "claude-opus-5"),
    "generator": os.environ.get("ARE_GENERATOR_MODEL", "claude-opus-5"),
    "solver": os.environ.get("ARE_SOLVER_MODEL", "claude-opus-5"),
    "judge": os.environ.get("ARE_JUDGE_MODEL", "claude-opus-5"),
}

# Bounded on purpose: ops-console turns are short and a run has a 30k token budget (§4.4).
DEFAULT_MAX_TOKENS = 4000


class LLMUnavailable(RuntimeError):
    """No API key and no cached response. Callers degrade; they never fabricate."""


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[dict]          # [{id, name, input}]
    stop_reason: str
    input_tokens: int = 0
    output_tokens: int = 0
    raw_content: list = field(default_factory=list)
    from_cache: bool = False

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def api_key_present() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def gateway_host() -> str | None:
    """Non-None when traffic goes through a third-party gateway rather than Anthropic."""
    from urllib.parse import urlparse

    base = os.environ.get("ANTHROPIC_BASE_URL", "").strip()
    if not base:
        return None
    host = urlparse(base).hostname
    return None if host in (None, "api.anthropic.com") else host


def model_label(model: str) -> str:
    """The string recorded in every trace, verdict and report.

    A pinned id means "this model produced these numbers". Through a gateway that claim is
    unverifiable — the router decides what actually serves the request and nothing in the
    response proves it. So the label carries the provenance instead of pretending it is a
    first-party pin (§4.5, §13.1, and the same reasoning that disabled refusal fallbacks).
    """
    host = gateway_host()
    return f"{model} (via {host}, provenance unverified)" if host else model


class LLMClient:
    """Thin wrapper over the Anthropic Messages API with cache + usage accounting."""

    def __init__(self, role: str = "agent", cache: ResponseCache | None = None,
                 seed: int = 0, usage_sink: Callable[[int], None] | None = None,
                 max_tokens: int = DEFAULT_MAX_TOKENS, effort: str | None = None):
        self.role = role
        self.model = MODELS.get(role, MODELS["agent"])
        self.reported_model = model_label(self.model)
        self.cache = cache or ResponseCache("off")
        self.seed = seed
        self.usage_sink = usage_sink
        self.max_tokens = max_tokens
        self.effort = effort
        self._client = None
        self.calls = 0

    # ------------------------------------------------------------------ client
    def _ensure_client(self):
        if self._client is None:
            if not api_key_present():
                raise LLMUnavailable(
                    "ANTHROPIC_API_KEY is not set. Run with --offline to use the "
                    "scripted calibration policies, or `--cache replay` against a "
                    "recorded run.")
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    @property
    def available(self) -> bool:
        return api_key_present() or self.cache.mode == "replay"

    # -------------------------------------------------------------- messages
    def complete(self, system: str, messages: list[dict],
                 tools: list[dict] | None = None) -> LLMResponse:
        key = ResponseCache.key(self.model, system, messages, None, self.seed)
        try:
            cached = self.cache.get(key)
            self.calls += 1
            if self.usage_sink:
                self.usage_sink(cached.get("input_tokens", 0) + cached.get("output_tokens", 0))
            return LLMResponse(**{**cached, "from_cache": True})
        except CacheMiss:
            # A replay miss is DELIBERATE and fatal. `ResponseCache.get` raises a loud,
            # explanatory CacheMiss in replay mode; catching it generically here meant the
            # explanation was discarded and the run quietly went to the live API instead —
            # so "--replay guarantees the replay really is a replay" was false, and a
            # partially-populated cache would silently mix recorded and fresh responses
            # into one trace. Never let a replay fall through.
            if self.cache.mode == "replay":
                raise
        client = self._ensure_client()
        kwargs: dict = dict(model=self.model, max_tokens=self.max_tokens,
                            system=system, messages=messages)
        if tools:
            kwargs["tools"] = tools
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}

        resp = client.messages.create(**kwargs)
        self.calls += 1

        # A refusal is a 200 with stop_reason="refusal" — check before reading content.
        text_parts, tool_calls = [], []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name,
                                   "input": dict(block.input or {})})

        out = LLMResponse(
            text="\n".join(text_parts).strip(),
            tool_calls=tool_calls,
            stop_reason=resp.stop_reason or "end_turn",
            input_tokens=getattr(resp.usage, "input_tokens", 0),
            output_tokens=getattr(resp.usage, "output_tokens", 0),
            raw_content=[b.model_dump() for b in resp.content],
        )
        if out.stop_reason == "refusal" and not out.text:
            details = getattr(resp, "stop_details", None)
            cat = getattr(details, "category", None) if details else None
            out.text = f"[model refusal: {cat or 'unspecified'}]"

        self.cache.put(key, {"text": out.text, "tool_calls": out.tool_calls,
                             "stop_reason": out.stop_reason,
                             "input_tokens": out.input_tokens,
                             "output_tokens": out.output_tokens,
                             "raw_content": out.raw_content})
        if self.usage_sink:
            self.usage_sink(out.tokens)     # may raise LimitTripped (§4.4)
        return out
