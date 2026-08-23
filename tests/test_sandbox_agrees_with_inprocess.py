"""The sandboxed path and the in-process path must observe the same agent.

Found by the T4 fresh-clone check, and it is the most consequential §7.10 instance so
far because **every surface said the run was healthy**:

    composite 65.0   invalid 0.0%   reportable True

...while `looper` recorded **zero tool calls** and none of its declared modes. The child
put a ~20KB trace on an `mp.Queue`; the parent was inside `proc.join()` and not draining
it, so the feeder blocked past the pipe buffer and the child never exited. The outer
120s cap then fired and `_killed()` synthesised a skeleton with `harness_error=None` —
a harness deadlock wearing an agent's failure mode.

`clean` (~2KB) fit inside the buffer, so it passed, which is why this survived. The
defect scaled with trace size, and only the loudest agent was big enough to trip it.

Two consequences, both asserted below:

  1. the paths must agree on the **defect signature**, not merely on the composite —
     the composite was identical (65.0) in both, which is what hid it;
  2. an outer-cap kill must not score as agent behaviour. It means the inner switches
     failed, which `limits.py` already calls a harness problem.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from are.cli import load_scenarios
from are.runner.loop import execute_run
from are.runner.sandbox import run_sandboxed
from are.verify.rules import verify

FROZEN = Path("frozen/frozen_scenarios.json")
pytestmark = pytest.mark.skipif(not FROZEN.exists(), reason="frozen set not generated")


@pytest.fixture(scope="module")
def loop_scenario():
    return load_scenarios(FROZEN)[0]


def test_the_looping_agent_actually_runs_inside_the_sandbox(loop_scenario):
    """The direct assertion. `looper` makes 40 calls and must trip the inner budget.

    Asserted on tool_call_count, not on the composite: the composite was 65.0 whether
    the agent ran or deadlocked, and that coincidence is the entire reason this went
    unnoticed."""
    r = run_sandboxed(loop_scenario, "looper", offline=True)
    assert r.harness_error is None, f"sandboxed run failed: {r.harness_error}"
    assert r.tool_call_count >= 25, (
        f"looper made {r.tool_call_count} tool calls in the sandbox; it makes 40 "
        f"in-process. A run that observed nothing is not a run that found nothing.")
    assert r.limit_tripped == "max_tool_calls", (
        f"expected the INNER budget switch, got {r.limit_tripped!r}. 'wall_clock_s' "
        f"here means the outer cap fired, i.e. the harness deadlocked again.")
    assert r.model_version != "unknown", (
        "model_version 'unknown' means this is a synthesised skeleton, not a real run")


@pytest.mark.parametrize("agent", ["clean", "looper", "pushover", "confabulator"])
def test_both_paths_reach_the_same_verdict(agent, loop_scenario):
    """Agreement on the finding set, for every calibration agent.

    Parametrised deliberately: the bug scaled with trace size, so testing only the
    small agents would have passed throughout."""
    sandboxed = run_sandboxed(loop_scenario, agent, offline=True)
    inprocess = execute_run(loop_scenario, agent, offline=True)

    assert sandboxed.harness_error is None
    s_modes = {f.mode for f in verify(loop_scenario, sandboxed).findings}
    i_modes = {f.mode for f in verify(loop_scenario, inprocess).findings}
    assert s_modes == i_modes, (
        f"{agent}: sandboxed run found {sorted(s_modes)}, in-process found "
        f"{sorted(i_modes)}. The sandbox must not change what is observed about the "
        f"agent — L2 is process isolation, not a different experiment.")


def test_an_outer_cap_kill_is_a_harness_finding_not_an_agent_one(loop_scenario):
    """`limits.py`: an outer trip means the INNER enforcement failed, so the run
    observed nothing about the agent and must route to INVALID (§6.1).

    Previously it returned harness_error=None and scored as a clean agent TIMEOUT —
    invalid_rate 0.0%, reportable True. 'Not measured' and 'measured clean' rendered
    identically, which is the §7.10 rule verbatim."""
    from are.runner.sandbox import _killed

    r = _killed(loop_scenario, "looper", 0, 120.0)
    assert r.harness_error, "an outer-cap kill must carry a harness_error"
    assert r.limit_tripped == "wall_clock_s"

    v = verify(loop_scenario, r)
    assert v.outcome == "INVALID", (
        f"outer-cap kill scored {v.outcome}; a run that observed nothing about the "
        f"agent cannot be one of its failures (§13.5)")
    assert r.steps[0].meta.get("observed_agent_behaviour") is False


def test_the_outer_cap_stays_above_the_inner_limit(loop_scenario):
    """The outer cap backs up the inner switches; it must not overtake them.

    `--wall-clock` overrides the INNER limit only. With the outer cap hardcoded at
    120s, an online run at `--wall-clock 240` would have the outer firing first on
    every slow-but-legal run — and since row 19 an outer trip is INVALID, each would
    be charged to the harness instead of the agent. A backstop that fires before the
    thing it backs up is not a backstop."""
    import inspect

    from are.runner.limits import LIMITS
    from are.runner.sandbox import run_sandboxed

    src = inspect.getsource(run_sandboxed)
    assert "SANDBOX_CAPS[\"wall_clock_s\"])" in src and "inner * 1.5" in src, (
        "the outer cap is no longer derived from the inner limit")

    for inner in (LIMITS["wall_clock_s"], 240.0, 600.0):
        outer = max(120.0, inner * 1.5 + 30.0)
        assert outer > inner * 1.4, (
            f"inner {inner}s vs outer {outer}s leaves too little margin; the outer "
            f"cap would fire on runs the inner switch should have owned")
