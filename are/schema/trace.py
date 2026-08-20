"""Execution trace model. One JSONL object per step (CLAUDE.md §9)."""
from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

StepType = Literal[
    "run_start", "agent_message", "tool_call", "tool_result",
    "final_answer", "limit_trip", "harness_error", "run_end",
    # Harness instrumentation for the known-defective calibration agents only: records
    # that an agent entered its declared defect branch (are/calib/defects.py). Never
    # produced by, or read from, an agent under evaluation.
    "defect_marker",
]


class Step(BaseModel):
    step_id: int
    type: StepType
    t: float = Field(default_factory=time.time)
    # tool_call / tool_result
    tool: str | None = None
    args: dict | None = None
    ok: bool | None = None
    data: Any = None
    error: str | None = None
    # agent_message / final_answer
    text: str | None = None
    # bookkeeping
    meta: dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class Mutation(BaseModel):
    entity_id: str
    entity_type: str
    tool: str
    args: dict
    tier: str                 # READ / MUTATING / IRREVERSIBLE
    step_id: int
    succeeded: bool
    t: float = Field(default_factory=time.time)

    model_config = {"extra": "forbid"}


class RunResult(BaseModel):
    """Everything the verifier needs, plus provenance (§7.5)."""
    run_id: str
    scenario_id: str
    repeat_idx: int
    agent_version: str
    model_version: str
    seed: int
    steps: list[Step]
    mutation_log: list[Mutation]
    final_state: dict
    final_answer: str = ""
    injections: list[dict] = Field(default_factory=list)   # payload_id/names_tool/step_id
    limit_tripped: str | None = None      # wall_clock_s | max_tool_calls | max_tokens
    harness_error: str | None = None      # -> INVALID
    tokens_used: int = 0
    provider_fault_retries: int = 0   # 5xx retried and eventually succeeded (§Y2)
    wall_clock_s: float = 0.0
    tool_call_count: int = 0
    cache_mode: str = "off"

    model_config = {"extra": "forbid"}
