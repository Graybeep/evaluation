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

# Provider-fault retry policy. Bounded and counted, never silent.
# 5xx ONLY: a 429 from this gateway means "insufficient credits", which retrying cannot
# fix and which must surface as a real failure rather than be masked by backoff.
#
# The ceiling is hard (§AA3). Retries are how provider instability stops corrupting an
# agent measurement; they are also how it becomes invisible. A run that needed four
# retries to clear is a DIFFERENT FACT from one that passed clean, so the count keeps
# flowing through the single `provider_fault_retries` counter (§Y2) into the scorecard
# and the report. Raising the env override past MAX buys silence, not reliability.
MAX_PROVIDER_RETRIES = 4
PROVIDER_RETRIES = min(int(os.environ.get("ARE_PROVIDER_RETRIES", "4")),
                       MAX_PROVIDER_RETRIES)
RETRY_BACKOFF_S = float(os.environ.get("ARE_RETRY_BACKOFF_S", "2.0"))
MAX_BACKOFF_S = 16.0
# Per-minute windows need outwaiting, not jitter.
RATE_LIMIT_BACKOFF_S = float(os.environ.get("ARE_RATE_LIMIT_BACKOFF_S", "20.0"))


class ProviderFault(RuntimeError):
    """A 200 whose body a provider-agnostic caller cannot parse.

    Distinct from a 5xx only in how it arrives. The first-party Anthropic API always
    returns a `content` list; a third-party gateway can return HTTP 200 with
    `content: null` on an empty, filtered or truncated upstream completion. That is a
    provider failure wearing a success status code, and it must be classified as one.

    Specifically it must NOT be read as an empty completion, because "the model produced
    no output" is a claim about AGENT BEHAVIOUR that a null body does not support — the
    same misattribution T2 and U4 each caught once already.
    """


def _is_provider_fault(exc: Exception) -> bool:
    if isinstance(exc, ProviderFault):
        return True
    status = getattr(exc, "status_code", None)
    return isinstance(status, int) and 500 <= status < 600


# Credit exhaustion is fatal and must surface; a per-minute rate limit is transient and
# backoff clears it. Both arrive as 429, so the two are separated by the error body.
_FATAL_429 = ("insufficient", "credit", "balance", "top up", "topup", "payment")
_TRANSIENT_429 = ("rate_limited", "rate limit", "rate-limit",
                  "per-minute", "per minute", "too many requests")


def _is_rate_limited(exc: Exception) -> bool:
    """A 429 that backoff can clear.

    The original policy said "a 429 from this gateway means insufficient credits, which
    retrying cannot fix" and made every 429 fatal. That was written from an ASSUMPTION
    about what the gateway means by 429 and never checked against a real response body.
    The first full online run returned **359 of 360 runs INVALID** on
    `{'type': 'rate_limited', 'message': 'Per-minute ...'}` — the retryable kind, thrown
    away because the code believed 429 could only ever mean one thing.

    §7.10 lesson (b): a rule derived from the implementer's model catches only deviations
    FROM that model, never errors IN it. So the two meanings are now read off the error
    itself, and credit exhaustion stays fatal exactly as intended.

    ## VALIDATION STATUS: unit-tested and revert-verified, NOT validated against a live 429

    Stated here because the gap that produced this bug was believing an untested claim
    about the endpoint, and a fix nobody has watched work is the same kind of claim.

    What exists: five unit cases covering both branches (including a body naming *both*
    rate-limiting and credit exhaustion, where a naive substring check picks wrong), and
    mutation `T6-rate-limit-429`, which drives the suite red when the fatal/transient
    split is removed.

    What does NOT exist: a recorded live run in which a 429 was raised, retried, and
    recovered. Two attempts on 2026-08-23 failed to produce one — a suite run timed out
    before persisting, and a direct probe made 8 successful calls without ever tripping
    the limit. **No 429 was observed, so nothing about this path was exercised**; absence
    of a rate limit is not evidence that the rate-limit branch works.

    To close it, capture a run whose scorecard shows `provider_fault_retries > 0` with
    `invalid_rate` at 0 — retries that *recovered*, rather than retries that ran out.
    """
    if getattr(exc, "status_code", None) != 429:
        return False
    blob = f"{exc}".lower()
    if any(w in blob for w in _FATAL_429):
        return False                       # insufficient credits -> must surface (§AA3)
    return any(w in blob for w in _TRANSIENT_429)


def _is_retryable(exc: Exception) -> bool:
    return _is_provider_fault(exc) or _is_rate_limited(exc)


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
        # Counted separately from invalid_rate: retries that SUCCEEDED still say something
        # about the endpoint, and that signal must not vanish into a clean-looking PASS.
        self.provider_fault_retries = 0

    # ------------------------------------------------------------------ client
    def _ensure_client(self):
        if self._client is None:
            if not api_key_present():
                raise LLMUnavailable(
                    "ANTHROPIC_API_KEY is not set. Run with --offline to use the "
                    "scripted calibration policies, or `--cache replay` against a "
                    "recorded run.")
            import anthropic
            # max_retries=0: the SDK's own retry is SILENT, and a silent retry launders how
            # unstable the endpoint actually was. We retry ourselves so every attempt is
            # counted and surfaced (§Y2) — a run that needed two retries to succeed is not
            # the same as one that succeeded clean, even when both end in PASS.
            self._client = anthropic.Anthropic(max_retries=0)
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

        import time as _time

        last: Exception | None = None
        resp = None
        for attempt in range(PROVIDER_RETRIES + 1):
            try:
                resp = client.messages.create(**kwargs)
                if getattr(resp, "content", None) is None:
                    raise ProviderFault(
                        "gateway returned HTTP 200 with content=None "
                        f"(stop_reason={getattr(resp, 'stop_reason', None)!r}); "
                        "treated as a provider fault, never as an empty agent turn")
                break
            except Exception as exc:
                last = exc
                if attempt >= PROVIDER_RETRIES or not _is_retryable(exc):
                    raise
                self.provider_fault_retries += 1
                # A per-minute limit needs to outwait the window, not merely jitter past
                # a blip, so it gets its own floor rather than the 5xx backoff curve.
                delay = min(RETRY_BACKOFF_S * (2 ** attempt), MAX_BACKOFF_S)
                if _is_rate_limited(exc):
                    delay = max(delay, RATE_LIMIT_BACKOFF_S * (attempt + 1))
                _time.sleep(delay)
        if resp is None:                                        # pragma: no cover
            raise last if last else RuntimeError("no response and no exception")
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
