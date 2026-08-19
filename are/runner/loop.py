"""The run loop: one scenario + one agent -> one RunResult (CLAUDE.md §4).

Invariants this file is responsible for:
  * A **fresh World per run** (§7.5). Nothing is reused between runs — not the world, not
    the fault engine, not the adapter.
  * Every tool call is recorded before it executes and its result recorded after, so a
    trace is complete even when a kill switch fires mid-call.
  * A kill-switch trip is recorded as a **first-class outcome**, never as a crash and
    never as INVALID (§4.4, §6.1). Harness/API faults are the opposite: INVALID.
"""
from __future__ import annotations

import time
import traceback

from are import calib
from are.runner.cache import ResponseCache
from are.runner.limits import Budget, LimitTripped
from are.runner.llm import LLMClient, LLMUnavailable, api_key_present
from are.schema.scenario import Scenario
from are.schema.trace import RunResult, Step
from are.sim.faults import FaultEngine
from are.sim.world import ToolResult, World
from are.tools.specs import all_specs
from are.util import scrub, truncate

OFFLINE_MODEL = "offline-scripted-policy"


def make_client(agent_name: str, cache_mode: str, seed: int,
                offline: bool) -> LLMClient | None:
    if offline or not (api_key_present() or cache_mode == "replay"):
        return None
    return LLMClient(role="agent", cache=ResponseCache(cache_mode), seed=seed)


def execute_run(scenario: Scenario, agent_name: str, repeat_idx: int = 0,
                cache_mode: str = "off", offline: bool = False,
                limit_overrides: dict | None = None) -> RunResult:
    client = make_client(agent_name, cache_mode, scenario.seed, offline)
    adapter = calib.build(agent_name, client)
    model_version = client.model if client else OFFLINE_MODEL

    faults = FaultEngine(faults=list(scenario.faults), seed=scenario.seed)
    world = World(scenario.world_state, seed=scenario.seed, fault_engine=faults)
    budget = Budget.from_limits(limit_overrides)

    steps: list[Step] = []
    counter = {"n": 0}

    def next_id() -> int:
        counter["n"] += 1
        return counter["n"]

    def record(**kw) -> Step:
        st = Step(step_id=next_id(), **kw)
        steps.append(st)
        return st

    def call_tool(tool: str, args: dict) -> ToolResult:
        budget.charge_tool_call()                      # may raise LimitTripped
        st = record(type="tool_call", tool=tool, args=scrub(dict(args or {})))
        result = world.call(tool, args or {}, step_id=st.step_id)
        record(type="tool_result", tool=tool, ok=result.ok,
               data=scrub(result.data), error=result.error,
               meta={"call_step_id": st.step_id})
        return result

    record(type="run_start", meta={"scenario_id": scenario.id, "agent": agent_name,
                                   "model": model_version, "seed": scenario.seed,
                                   "repeat": repeat_idx})

    if hasattr(adapter, "bind_usage"):
        adapter.bind_usage(budget.charge_tokens)
    if hasattr(adapter, "bind_message"):
        adapter.bind_message(lambda text: record(type="agent_message",
                                                 text=truncate(scrub(text))))

    started = time.monotonic()
    final_answer, limit_tripped, harness_error = "", None, None
    try:
        final_answer = adapter.run(scenario.instruction, all_specs(), call_tool) or ""
    except LimitTripped as trip:
        limit_tripped = trip.which
        record(type="limit_trip", text=str(trip), meta={"which": trip.which})
    except LLMUnavailable as exc:
        harness_error = f"llm_unavailable: {exc}"
        record(type="harness_error", text=str(exc))
    except Exception as exc:                            # harness/API fault -> INVALID
        harness_error = f"{type(exc).__name__}: {exc}"
        record(type="harness_error", text=truncate(scrub(traceback.format_exc()), 2000))

    elapsed = time.monotonic() - started
    final_answer = truncate(scrub(final_answer), 6000)
    record(type="final_answer", text=final_answer)
    record(type="run_end", meta={"wall_clock_s": round(elapsed, 3),
                                 "tool_calls": budget.tool_calls,
                                 "tokens": budget.tokens})

    return RunResult(
        run_id=f"{scenario.id}|{adapter.version}|{model_version}|s{scenario.seed}|r{repeat_idx}",
        scenario_id=scenario.id,
        repeat_idx=repeat_idx,
        agent_version=adapter.version,
        model_version=model_version,
        seed=scenario.seed,
        steps=steps,
        mutation_log=world.mutation_log,
        final_state=world.snapshot(),
        final_answer=final_answer,
        limit_tripped=limit_tripped,
        harness_error=harness_error,
        tokens_used=budget.tokens,
        wall_clock_s=round(elapsed, 3),
        tool_call_count=budget.tool_calls,
        cache_mode=cache_mode,
        injections=[{"payload_id": e.payload_id, "names_tool": e.names_tool,
                     "step_id": e.step_id, "tool": e.tool} for e in faults.injections],
    )
