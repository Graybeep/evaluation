"""Verdict + failure-mode model (CLAUDE.md §6)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Outcome = Literal["PASS", "FAIL", "INVALID"]

FailureMode = Literal[
    # rule-based (primary)
    "DESTRUCTIVE_ACTION",
    "SCOPE_VIOLATION",
    "WRONG_FINAL_STATE",
    "TOOL_LOOP",
    "TIMEOUT",
    "BUDGET_EXCEEDED",
    "MISSING_CLARIFICATION",
    "TASK_INCOMPLETE",
    "INJECTION_FOLLOWED",
    "REFUSAL_EXPECTED",
    "ARG_CONSTRAINT_VIOLATED",
    # judge-based (secondary, labelled)
    "UNGROUNDED_CLAIM",
    "OVERCONFIDENT_SUMMARY",
]


class Finding(BaseModel):
    mode: FailureMode
    severity: Literal["CRITICAL", "MAJOR", "MINOR"]
    detail: str
    assertion_idx: int | None = None
    evidence_step_ids: list[int] = Field(default_factory=list)
    source: Literal["rule", "judge"] = "rule"
    judge_confidence: float | None = None

    model_config = {"extra": "forbid"}


class Verdict(BaseModel):
    run_id: str
    scenario_id: str
    repeat_idx: int
    category: str
    agent_version: str
    model_version: str
    outcome: Outcome
    findings: list[Finding] = Field(default_factory=list)
    invalid_reason: str | None = None
    pressure_level: str = "P0"
    pressure_tags: list[str] = Field(default_factory=list)
    tool_call_count: int = 0
    wall_clock_s: float = 0.0
    tokens_used: int = 0

    model_config = {"extra": "forbid"}

    @property
    def critical(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "CRITICAL"]
