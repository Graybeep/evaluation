"""Feasibility-gate audit by mutation testing (CLAUDE.md §3.3).

A gate that rejects nothing is indistinguishable from no gate — from the *outside*. The
discard rate alone cannot tell those apart: 0% is also what a perfectly working gate reports
when every authored scenario is genuinely feasible, which is the state you want to be in.

So the gate's power is measured directly instead of assumed. `audit()` injects known
defects into copies of real scenarios and reports what fraction the gate rejects. That
number belongs next to the discard rate in any claim about the gate.

Two mutation classes are expected to score low, and the reason is not a gate defect:
`no_call` on a read tool and `max_tool_calls: 0` are both genuinely *satisfiable* for the
refuse/ask templates, whose reference solution makes no tool calls at all. The gate is
right to keep those; the mutation is simply not impossible there.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from are.gen.feasibility import check
from are.schema.scenario import Assertion, Scenario


def _first_order(s: Scenario) -> str:
    return next(iter(s.world_state.get("orders", {})), "ORD-1000")


def _plan_tool(s: Scenario) -> str:
    return s.reference_plan[0]["tool"] if s.reference_plan else "get_order"


MUTATIONS = {
    "unsatisfiable state_equals": lambda s: Assertion(
        kind="state_equals", params={"path": f"orders.{_first_order(s)}.status",
                                     "value": "impossible-value"},
        severity="MAJOR", rationale="mutation-test"),
    "must_call a tool no solution uses": lambda s: Assertion(
        kind="must_call", params={"tool": "delete_customer"},
        severity="MAJOR", rationale="mutation-test"),
    "entity id that does not exist": lambda s: Assertion(
        kind="mutations_subset_of", params={"entity_ids": ["ORD-999999"]},
        severity="MINOR", rationale="mutation-test"),
    "unknown tool referenced": lambda s: Assertion(
        kind="no_call", params={"tool": "drop_database"},
        severity="MINOR", rationale="mutation-test"),
    "no_call on a tool the plan needs": lambda s: Assertion(
        kind="no_call", params={"tool": _plan_tool(s)},
        severity="CRITICAL", rationale="mutation-test"),
    "impossible call budget (n=0)": lambda s: Assertion(
        kind="max_tool_calls", params={"n": 0}, severity="MAJOR", rationale="mutation-test"),
}

# Mutations that only make a scenario impossible when a solution actually calls tools.
PLAN_DEPENDENT = {"no_call on a tool the plan needs", "impossible call budget (n=0)"}


@dataclass
class AuditResult:
    n_sampled: int
    baseline_rejected: int
    per_mutation: dict = field(default_factory=dict)   # name -> {caught, of, applicable}

    @property
    def overall_catch_rate(self) -> float:
        caught = sum(d["caught"] for d in self.per_mutation.values())
        total = sum(d["applicable"] for d in self.per_mutation.values())
        return caught / total if total else 0.0

    def as_dict(self) -> dict:
        return {"n_sampled": self.n_sampled, "baseline_rejected": self.baseline_rejected,
                "overall_catch_rate": round(self.overall_catch_rate, 4),
                "per_mutation": self.per_mutation}


def audit(pool: list[Scenario], sample: int = 40, seed: int = 7,
          solver: str = "deterministic") -> AuditResult:
    rng = random.Random(seed)
    chosen = rng.sample(pool, min(sample, len(pool)))
    baseline = sum(1 for s in chosen if not check(s, solver=solver)[0])
    res = AuditResult(n_sampled=len(chosen), baseline_rejected=baseline)

    for name, make in MUTATIONS.items():
        caught = applicable = 0
        for s in chosen:
            # a plan-dependent mutation is only *impossible* if a solution calls tools
            if name in PLAN_DEPENDENT and not s.reference_plan:
                continue
            applicable += 1
            mutant = s.model_copy(deep=True)
            mutant.assertions.append(make(s))
            if not check(mutant, solver=solver)[0]:
                caught += 1
        res.per_mutation[name] = {"caught": caught, "applicable": applicable,
                                  "of": len(chosen)}
    return res
