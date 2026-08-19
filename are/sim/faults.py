"""Deterministic fault injection (CLAUDE.md §4.2).

Every fault is a pure function of (scenario seed, tool, per-tool call index). No wall-clock
randomness, no global RNG — replaying a scenario with the same seed reproduces the same
faults in the same order.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from are.probes import corpus
from are.schema.scenario import FaultSpec

LATENCY_CAP_MS = 300  # §4.2: do not burn wall clock


@dataclass
class InjectionEvent:
    payload_id: str
    names_tool: str | None
    step_id: int
    tool: str


@dataclass
class FaultEngine:
    faults: list[FaultSpec]
    seed: int = 0
    call_counts: dict[str, int] = field(default_factory=dict)
    injections: list[InjectionEvent] = field(default_factory=list)
    latency_ms_total: float = 0.0

    # ---------- helpers ----------
    def _matching(self, kind: str, tool: str) -> list[FaultSpec]:
        return [f for f in self.faults
                if f.kind == kind and (f.tool is None or f.tool == tool)]

    def bump(self, tool: str) -> int:
        """1-based index of this call among calls to `tool`."""
        self.call_counts[tool] = self.call_counts.get(tool, 0) + 1
        return self.call_counts[tool]

    # ---------- phase 1: before the tool executes ----------
    def before_call(self, tool: str, idx: int) -> str | None:
        """Returns an error string if the call should fail instead of executing."""
        for f in self._matching("LATENCY", tool):
            ms = min(int(f.params.get("ms", 120)), LATENCY_CAP_MS)
            self.latency_ms_total += ms
            if not f.params.get("simulated", True):
                time.sleep(ms / 1000.0)
        for f in self._matching("TRANSIENT_ERROR", tool):
            k = int(f.params.get("k", 1))          # first K calls fail
            if idx <= k:
                return f.params.get("message", "503 Service Unavailable (transient)")
        return None

    # ---------- phase 2: after the tool executes ----------
    def after_call(self, tool: str, idx: int, data, step_id: int):
        """Mutate a successful result: PARTIAL_DATA, CONTRADICTION, INJECTION."""
        for f in self._matching("PARTIAL_DATA", tool):
            drop = f.params.get("drop_fields", ["total_cents", "email"])
            data = _drop_fields(data, drop)

        for f in self._matching("CONTRADICTION", tool):
            on = int(f.params.get("on_call", 3))   # call 1 vs call 3 disagree (§4.2)
            if idx >= on:
                data = _perturb(data, f.params.get("field", "total_cents"),
                                int(f.params.get("delta", 1500)))

        for f in self._matching("INJECTION", tool):
            pid = f.params.get("payload_id")
            payload = corpus.by_id(pid) if pid else corpus.pick("P5", self.seed, "tool_output")
            if payload is None:
                continue
            data = _attach_note(data, payload.text)
            self.injections.append(InjectionEvent(
                payload_id=payload.id, names_tool=payload.names_tool,
                step_id=step_id, tool=tool))
        return data

    def injected_tool_names(self) -> set[str]:
        return {e.names_tool for e in self.injections if e.names_tool}


# ---------- data surgery helpers (pure) ----------
def _drop_fields(data, fields: list[str]):
    if isinstance(data, dict):
        return {k: _drop_fields(v, fields) for k, v in data.items() if k not in fields}
    if isinstance(data, list):
        return [_drop_fields(v, fields) for v in data]
    return data


def _perturb(data, field_name: str, delta: int):
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if k == field_name and isinstance(v, (int, float)):
                out[k] = v + delta
            else:
                out[k] = _perturb(v, field_name, delta)
        return out
    if isinstance(data, list):
        return [_perturb(v, field_name, delta) for v in data]
    return data


def _attach_note(data, text: str):
    """Injected text rides in a plausible free-text field, as it would in the real world."""
    if isinstance(data, dict):
        out = dict(data)
        out["system_note"] = text
        return out
    if isinstance(data, list) and data and isinstance(data[0], dict):
        out = [dict(d) for d in data]
        out[0]["system_note"] = text
        return out
    return {"result": data, "system_note": text}
