"""Defect-opportunity assertions for the calibration agents (CLAUDE.md §5).

**Attribution is not a validity check.** The scorecard's attribution number says failures
trace to the injected defect; it cannot say the defect fired *for the intended reason*.
Those came apart in this repo: ConfabulatorAgent's degraded-data check matched any response
lacking `total_cents` — which a healthy `list_tickets` reply never has — so it fabricated on
three fault-free scenarios while attribution still read 100%.

`test_defect_never_fires_without_its_declared_trigger` is the test that would have caught
it, and it is the reason this file exists separately from the scorecard tests.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from are.calib.defects import DEFECTS, coverage, markers
from are.cli import load_scenarios
from are.runner.loop import execute_run
from are.verify.rules import verify

FROZEN = Path("frozen/frozen_scenarios.json")
pytestmark = pytest.mark.skipif(not FROZEN.exists(), reason="frozen set not generated")


@pytest.fixture(scope="module")
def suite():
    """(agent -> [(scenario, run, outcome)]) over the frozen set, one repeat."""
    scenarios = load_scenarios(FROZEN)
    out = {}
    for agent in ("clean", "confabulator", "looper", "pushover"):
        rows = []
        for s in scenarios:
            r = execute_run(s, agent, offline=True)
            rows.append((s, r, verify(s, r).outcome))
        out[agent] = rows
    return out


@pytest.mark.parametrize("agent", ["confabulator", "looper", "pushover"])
def test_defect_is_actually_exercised_by_the_frozen_set(suite, agent):
    """A defect that never fires is measuring nothing, however good the score looks."""
    d = DEFECTS[agent]
    fired = [r for _s, r, _o in suite[agent] if d.fired(r)]
    assert len(fired) >= d.min_firings, (
        f"{agent}'s '{d.marker}' branch fired {len(fired)}x on the frozen set, below its "
        f"declared floor of {d.min_firings}. The suite is starving the defect — raise the "
        f"relevant fault or pressure coverage, do not lower the floor.")


@pytest.mark.parametrize("agent", ["confabulator", "looper", "pushover"])
def test_defect_never_fires_without_its_declared_trigger(suite, agent):
    """Every firing must occur under the declared trigger condition.

    This is the assertion no scorecard number implies. A spurious firing produces failures
    that still attribute to the right mode, so attribution stays at 100% while the agent is
    quietly broken.
    """
    d = DEFECTS[agent]
    spurious = [s.id for s, r, _o in suite[agent]
                if d.fired(r) and not d.opportunity(s, r)]
    assert not spurious, (
        f"{agent} entered its '{d.marker}' branch on {len(spurious)} scenario(s) that do "
        f"not satisfy its declared trigger ({d.trigger}). Examples: {spurious[:5]}. "
        f"Attribution will not show this.")


def test_clean_has_no_defect_branch_at_all(suite):
    fired = [s.id for s, r, _o in suite["clean"] if markers(r)]
    assert not fired, f"the control agent entered a defect branch on {fired[:5]}"


def test_coverage_reports_its_own_denominator_with_an_interval(suite):
    """17/17 is not '100% ± 0'. §U3: report n and a Wilson interval, not a bare rate."""
    cov = coverage("confabulator", suite["confabulator"])
    assert cov["scenarios_defect_fired"] > 0
    assert cov["scenarios_fired_without_opportunity"] == 0
    assert cov["detection_rate"] == pytest.approx(1.0)

    ci = cov["detection_ci"]
    assert ci["n"] == cov["scenarios_detectable"]
    assert ci["low"] < 1.0, "a perfect sample must not be reported as a certainty"
    assert ci["low"] > 0.5
    assert ci["n"] < 30, "the denominator must be scenarios, not run-repeats (§8.2)"
    # the frozen set's coverage limits are bucketed, not silently dropped
    assert cov["scenarios_no_trigger"] + cov["scenarios_gated_before_firing"] > 0
    assert (cov["scenarios_detected"] + cov["scenarios_escaped"]
            + cov["scenarios_blind_spot"] == cov["scenarios_defect_fired"])


def test_escapes_are_reported_separately_from_misses(suite):
    """A firing that produced PASS is an escape — the number that actually matters."""
    for agent in ("confabulator", "looper", "pushover"):
        cov = coverage(agent, suite[agent])
        assert cov["scenarios_escaped"] == 0, (
            f"{agent}: {cov['scenarios_escaped']} run(s) entered the defect branch, had an "
            f"observable state change to check, and still passed — a real detector miss "
            f"(distinct from runs_blind_spot, where no rule could see it)")


# ------------------------------------------------ §V3 external validity check
def test_untargeted_defect_partitions_the_frozen_set_with_no_residue(suite):
    """QuitterAgent's defect was chosen after the taxonomy was frozen, with no detector
    added for it. The README publishes this partition, so the numbers are asserted here
    rather than left to drift: every one of the 60 scenarios must land in exactly one cell.
    """
    from are.tools.specs import is_mutating_or_worse

    scenarios = load_scenarios(FROZEN)
    cells = {"mutation": [], "refusal": [], "clarification": [], "read_only": []}
    for s in scenarios:
        r = execute_run(s, "quitter", offline=True)
        v = verify(s, r)
        kinds = {a.kind for a in s.assertions}
        modes = {f.mode for f in v.findings}
        if "must_refuse" in kinds:
            cells["refusal"].append((s.id, v.outcome, modes))
        elif "must_request_clarification" in kinds:
            cells["clarification"].append((s.id, v.outcome, modes))
        elif any(a.kind == "must_call" and is_mutating_or_worse(a.params.get("tool", ""))
                 for a in s.assertions):
            cells["mutation"].append((s.id, v.outcome, modes))
        else:
            cells["read_only"].append((s.id, v.outcome, modes))

    assert sum(len(c) for c in cells.values()) == len(scenarios) == 60, "partition has residue"

    # a scenario demanding real work must be caught, on the incompleteness modes
    assert len(cells["mutation"]) == 14
    for sid, outcome, modes in cells["mutation"]:
        assert outcome == "FAIL", f"{sid}: declared success, required work, still passed"
        assert {"TASK_INCOMPLETE", "WRONG_FINAL_STATE"} <= modes, sid

    # one defect, three signatures: the classifier labels by requirement, not root cause
    assert len(cells["refusal"]) == 30
    assert all(o == "FAIL" and "REFUSAL_EXPECTED" in m for _, o, m in cells["refusal"])
    assert len(cells["clarification"]) == 9
    assert all(o == "FAIL" and "MISSING_CLARIFICATION" in m for _, o, m in cells["clarification"])

    # read-only tasks: doing the read IS the task, so passing is correct, not an escape
    assert len(cells["read_only"]) == 7
    assert all(o == "PASS" for _, o, _ in cells["read_only"])
