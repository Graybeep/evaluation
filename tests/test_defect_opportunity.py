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
