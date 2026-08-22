"""Positive controls for the two detectors that never fire on the frozen set.

`reports/detector_cofire.json` records `never_fired: [ARG_CONSTRAINT_VIOLATED, TIMEOUT]`
across 360 observations. Left there, that is exactly the §7.10 shape: a detector with no
positive control is indistinguishable from a detector that *cannot* fire, and the co-fire
matrix renders both as `0`.

**The finding is about the suite, not the detectors.** Same shape as L7's 0/174: the frozen
set contains no scenario that constrains a tool argument, and its scripted policies are far
too fast to trip a 90s wall clock. That is a coverage gap in the scenario set. These
fixtures close the *control* gap — they do not close the coverage gap, and the docs say so
rather than letting a green test imply otherwise.

Deliberately synthetic and outside the frozen set (§13.7: the frozen set is not touched to
make a number look better). Each fixture is minimal and must trip **exactly one** mode —
a control that fires three detectors cannot show which one it exercised.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from are.schema.scenario import Scenario
from are.schema.trace import RunResult
from are.verify.rules import verify

FX = Path(__file__).parent / "fixtures"
CASES = ["detector_timeout", "detector_arg_constraint"]


def load(name: str):
    d = json.loads((FX / f"{name}.json").read_text(encoding="utf-8"))
    return d, Scenario(**d["scenario"]), RunResult(**d["run"])


def modes_of(scenario, run) -> set[str]:
    return {f.mode for f in verify(scenario, run).findings}


@pytest.mark.parametrize("name", CASES)
def test_the_detector_fires_on_its_own_fixture(name):
    """The positive control itself. If this fails, the detector is dead code."""
    d, s, r = load(name)
    fired = modes_of(s, r)
    assert d["expect_fires"] in fired, (
        f"{name}: {d['expect_fires']} did not fire on a run built specifically to trip "
        f"it. Fired instead: {sorted(fired) or 'nothing'}")


@pytest.mark.parametrize("name", CASES)
def test_the_control_is_unconfounded(name):
    """Exactly one mode, so a firing can only be attributed to the thing under test.

    Same argument as `drifter`: a control that also trips DESTRUCTIVE_ACTION cannot
    separate its target detector from that one."""
    d, s, r = load(name)
    assert modes_of(s, r) == {d["expect_fires"]}, (
        f"{name} trips more than its target mode; it is no longer a clean control")


@pytest.mark.parametrize("name", CASES)
def test_the_other_detector_stays_silent(name):
    """The cross-negative. Firing on its own fixture proves the detector is alive;
    staying silent on the other's proves it is *specific* and not simply always-on."""
    d, s, r = load(name)
    fired = modes_of(s, r)
    for quiet in d["must_not_fire"]:
        assert quiet not in fired, (
            f"{name}: {quiet} fired on a fixture that does not exhibit it — the "
            f"detector is not specific to its own condition")


def test_each_fixture_is_the_negative_case_for_the_other():
    """Stated as a property over the pair rather than per-file, so adding a third
    fixture without wiring the cross-check cannot pass silently."""
    targets = {}
    fired = {}
    for name in CASES:
        d, s, r = load(name)
        targets[name] = d["expect_fires"]
        fired[name] = modes_of(s, r)
    for name in CASES:
        for other in CASES:
            if other == name:
                continue
            assert targets[other] not in fired[name], (
                f"{targets[other]} fired on {name}'s fixture; the two controls are "
                f"not mutually exclusive and neither isolates its detector")


def test_the_arg_constraint_fixture_is_anchored_and_therefore_not_vacuous():
    """§7.10: `call_args_match` means 'IF called, args satisfy the predicate', so an
    agent that never calls the tool satisfies it by doing nothing. `static_check`
    rejects an unanchored one.

    Asserting the fixture PASSES the real gate — rather than eyeballing the JSON —
    is what makes this a control over the detector as the gate admits it, not over a
    hand-made object the gate would have thrown out."""
    from are.gen.feasibility import static_check

    _d, s, _r = load("detector_arg_constraint")
    assert static_check(s) is None, (
        f"the fixture would be rejected by the feasibility gate: {static_check(s)}")

    stripped = s.model_copy(deep=True)
    stripped.assertions = [a for a in stripped.assertions if a.kind != "must_call"]
    assert static_check(stripped) is not None, (
        "removing the anchoring must_call left the scenario acceptable — the gate is "
        "no longer catching vacuous call_args_match, which is the whole reason the "
        "fixture is authored this way")


@pytest.mark.parametrize("name", CASES)
def test_the_fixtures_never_enter_the_frozen_set(name):
    """§13.7. These exist precisely so the frozen set does NOT have to be edited to
    give the detectors a positive case."""
    d, s, _r = load(name)
    assert s.frozen is False
    frozen = Path("frozen/frozen_scenarios.json")
    if frozen.exists():
        ids = {x["id"] for x in json.loads(frozen.read_text(encoding="utf-8"))["scenarios"]}
        assert s.id not in ids, f"{s.id} leaked into the frozen set"
    assert d["scenario"]["notes"].startswith("synthetic fixture")


def test_the_suite_gap_these_controls_do_not_close():
    """The honest half, asserted rather than written in a comment.

    These fixtures prove the detectors work. They do NOT put a constrained-argument
    or slow-agent scenario into the frozen set, so the co-fire report must keep
    reporting both modes as never-fired *there*. If someone 'fixes' that by counting
    fixture runs in the suite report, this fails — a control must not be laundered
    into coverage."""
    report = Path("reports/detector_cofire.json")
    if not report.exists():
        pytest.skip("run `are analyse` first")
    d = json.loads(report.read_text(encoding="utf-8"))
    assert set(d["never_fired"]) == {"ARG_CONSTRAINT_VIOLATED", "TIMEOUT"}, (
        f"never_fired changed to {d['never_fired']}. If the frozen set genuinely "
        f"gained coverage, update this test AND the docs. If fixture runs were folded "
        f"into the suite report, that is laundering a control into coverage — revert it.")
    for mode in ("ARG_CONSTRAINT_VIOLATED", "TIMEOUT"):
        assert d["fire_counts"][mode] == 0
