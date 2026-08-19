"""Execution limits — three independent kill switches (CLAUDE.md §4.4).

A loop can be cheap-and-fast, expensive-and-slow, or silent-and-stuck. One limit catches
one shape, so all three are enforced independently.

A trip is a **first-class failure mode** (TIMEOUT / BUDGET_EXCEEDED), never a crash and
never INVALID (§6.1).

Two tiers, deliberately not the same numbers:
  * LIMITS       — inner, per-run, enforced cooperatively inside the run (§4.4).
  * SANDBOX_CAPS — outer, enforced by the parent process killing the child (§7.9 L4).
    Looser on purpose: if the inner limit is doing its job the outer one never fires, so
    an outer trip means the inner enforcement itself failed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

LIMITS = dict(
    wall_clock_s=90,
    max_tool_calls=25,
    max_tokens=30_000,      # per run, tracked from API usage
)

SANDBOX_CAPS = dict(
    wall_clock_s=120,
    max_tool_calls=25,
    max_tokens=50_000,
)


class LimitTripped(Exception):
    """Raised inside the agent loop; caught by the runner and recorded, not re-raised."""

    def __init__(self, which: str, detail: str = ""):
        super().__init__(f"{which} limit tripped {detail}".strip())
        self.which = which
        self.detail = detail


@dataclass
class Budget:
    wall_clock_s: float
    max_tool_calls: int
    max_tokens: int
    # default_factory, not 0.0: a directly-constructed Budget must be usable,
    # otherwise `elapsed` is measured from the epoch and every check trips
    started: float = field(default_factory=time.monotonic)
    tool_calls: int = 0
    tokens: int = 0

    @classmethod
    def from_limits(cls, overrides: dict | None = None) -> "Budget":
        cfg = {**LIMITS, **(overrides or {})}
        b = cls(wall_clock_s=float(cfg["wall_clock_s"]),
                max_tool_calls=int(cfg["max_tool_calls"]),
                max_tokens=int(cfg["max_tokens"]))
        b.started = time.monotonic()
        return b

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def check_clock(self) -> None:
        if self.elapsed > self.wall_clock_s:
            raise LimitTripped("wall_clock_s", f"({self.elapsed:.1f}s)")

    def charge_tool_call(self) -> None:
        self.check_clock()
        self.tool_calls += 1
        if self.tool_calls > self.max_tool_calls:
            raise LimitTripped("max_tool_calls", f"({self.tool_calls})")

    def charge_tokens(self, n: int) -> None:
        self.tokens += int(n)
        if self.tokens > self.max_tokens:
            raise LimitTripped("max_tokens", f"({self.tokens})")
        self.check_clock()
