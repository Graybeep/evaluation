"""Scenario data model (CLAUDE.md §3.1). Single source of truth."""
from __future__ import annotations

from typing import Literal, Any

from pydantic import BaseModel, Field, field_validator

AssertionKind = Literal[
    "no_call",                     # tool must never be called          {tool}
    "must_call",                   # tool must be called                {tool}
    "call_args_match",             # if called, args satisfy predicate  {tool, field, op, value}
    "mutations_subset_of",         # only these entities mutated        {entity_ids}
    "state_equals",                # final state field == value         {path, value}
    "max_tool_calls",              # loop guard                         {n}
    "must_request_clarification",  # agent must ask, not guess          {}
    "must_refuse",                 # agent must decline the action      {}
]

Severity = Literal["CRITICAL", "MAJOR", "MINOR"]
Category = Literal["safety", "correctness", "robustness", "efficiency"]

FaultKind = Literal[
    "LATENCY", "TRANSIENT_ERROR", "PARTIAL_DATA", "CONTRADICTION", "INJECTION"
]


class Assertion(BaseModel):
    kind: AssertionKind
    params: dict = Field(default_factory=dict)
    severity: Severity
    rationale: str  # human-readable; shown in report

    model_config = {"extra": "forbid"}


class FaultSpec(BaseModel):
    kind: FaultKind
    tool: str | None = None          # which tool the fault targets (None = any)
    params: dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class Scenario(BaseModel):
    id: str
    template_id: str
    category: Category
    instruction: str
    world_state: dict                # seeds the simulator
    assertions: list[Assertion]
    pressure_tags: list[str] = Field(default_factory=list)   # [] for benign
    pressure_level: Literal["P0", "P1", "P2", "P3", "P4", "P5"] = "P0"
    faults: list[FaultSpec] = Field(default_factory=list)
    seed: int = 0
    feasible: bool = False           # set by the feasibility gate (§3.3)
    frozen: bool = False             # in the frozen benchmark set?
    # provenance
    reference_plan: list[dict] = Field(default_factory=list)  # oracle solution, §3.3
    notes: str = ""

    model_config = {"extra": "forbid"}

    @field_validator("assertions")
    @classmethod
    def _nonempty(cls, v: list[Assertion]) -> list[Assertion]:
        if not v:
            raise ValueError("scenario must carry at least one assertion")
        return v


class ScenarioSet(BaseModel):
    """A serialisable bundle of scenarios (frozen set, exploratory pool, ...)."""
    name: str
    scenarios: list[Scenario]
    meta: dict[str, Any] = Field(default_factory=dict)
