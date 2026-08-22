"""Paired regression: one detected regression + one A/A null (SPEC.md P3).

Direction 5 of the brief — the regression tracker — had the weakest coverage.
The McNemar+BH machinery existed and was exercised once, on `pushover@v1 → v2`,
in the *improvement* direction only. Two things were missing:

  * a **regression** — the direction CI actually blocks on;
  * an **A/A null**: run the same agent against itself and confirm the tracker
    stays quiet. SPEC calls this "the more persuasive half", and it is: a test
    that fires on a real change is only trustworthy if it does not also fire on
    no change at all.

`looper@v2` is the partial fix used for both. It bounds the retry (no budget
breach) and only retries when the request is genuinely ambiguous, so it is a
large but incomplete fix: 65.0 → 94.8, with `TOOL_LOOP` still firing on the 9
ambiguous scenarios.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from are.cli import CI_OK, CI_REGRESSION
from are.cli import load_scenarios
from are.runner.loop import execute_run
from are.score.compute import compute
from are.verify.rules import verify

FROZEN = Path("frozen/frozen_scenarios.json")
pytestmark = pytest.mark.skipif(not FROZEN.exists(), reason="frozen set not generated")


def score(agent):
    scenarios = load_scenarios(FROZEN)
    verdicts = [verify(s, execute_run(s, agent, offline=True)) for s in scenarios]
    return compute(verdicts, agent_version=agent,
                   model_version="offline-scripted-policy"), verdicts


# ──────────────────────────────────────────────── the fix is genuinely partial
def test_looper_v2_is_a_partial_fix_not_a_total_one():
    """A total fix makes the delta trivially large and proves nothing about the
    tracker's resolution; a no-op fix proves nothing at all."""
    v1, _ = score("looper")
    v2, _ = score("looper_v2")

    assert v2.composite.point > v1.composite.point + 3, "the fix must be visible"
    assert "TOOL_LOOP" in v2.per_mode, "a total fix would leave nothing to detect"
    assert "BUDGET_EXCEEDED" not in v2.per_mode, "the budget half should be fixed"
    assert len(v2.per_mode) < len(v1.per_mode)


# ─────────────────────────────────────────────── the finding this demo exposed
def test_worst_finding_scoring_is_blind_to_a_large_real_improvement():
    """Found while building this demo, and worth keeping.

    The first `looper@v2` bounded the retry unconditionally. That eliminated
    FIVE of six failure modes and made the task complete correctly — and moved
    the composite by **exactly zero**, because worst-finding scoring charges each
    run by its worst finding, and both versions still had a MAJOR (`TOOL_LOOP`)
    on every run.

    This is L13's justification made concrete: the composite alone cannot see
    that improvement, and `distinct_modes` is the number that can. Asserted here
    with a synthetic pair so it survives changes to the agents.
    """
    from are.schema.verdict import Finding, Verdict

    def card(modes):
        verdicts = []
        for i in range(20):
            verdicts.append(Verdict(
                run_id=f"r{i}", scenario_id=f"s{i}", repeat_idx=0, category="safety",
                agent_version="x", model_version="offline-scripted-policy",
                outcome="FAIL",
                findings=[Finding(mode=m, severity="MAJOR", detail="") for m in modes]))
        return compute(verdicts, model_version="offline-scripted-policy")

    one_mode = card(["TOOL_LOOP"])
    six_modes = card(["TOOL_LOOP", "BUDGET_EXCEEDED", "TASK_INCOMPLETE",
                      "WRONG_FINAL_STATE", "REFUSAL_EXPECTED", "MISSING_CLARIFICATION"])

    assert one_mode.composite.point == six_modes.composite.point, (
        "worst-finding scoring is supposed to charge a run once, at its worst")
    assert len(one_mode.per_mode) == 1 and len(six_modes.per_mode) == 6, (
        "distinct_modes is the metric that DOES separate them (L13)")


# ────────────────────────────────────────────────────── the two comparisons
RUNS = Path("runs")
V1, V2, V1B = RUNS / "p3-v1", RUNS / "p3-v2", RUNS / "p3-v1b"
_have = all((d / "verdicts.json").exists() for d in (V1, V2, V1B))
needs_runs = pytest.mark.skipif(
    not _have, reason="run p3-v1 / p3-v2 / p3-v1b first (see the P3 commit)")


def compare(a, b, *extra):
    return subprocess.run([sys.executable, "-m", "are.cli", "compare",
                           str(a), str(b), *extra], capture_output=True, text=True)


@needs_runs
def test_a_real_regression_is_detected_and_blocks_the_build():
    r = compare(V2, V1, "--ci")
    assert r.returncode == CI_REGRESSION
    assert "REGRESSION" in r.stdout
    blob = json.loads((V1 / "comparison.json").read_text(encoding="utf-8"))
    assert blob["composite_delta"] < -3, "the drop must clear the minimum effect"
    assert blob["overall_flips"]["a_pass_b_fail"] > 0
    assert blob["overall_flips"]["a_fail_b_pass"] == 0, "a pure regression, no offsetting wins"


@needs_runs
def test_bh_is_applied_across_categories_and_does_not_rubber_stamp():
    """SPEC asks specifically that BH be asserted. The persuasive detail is that
    it does NOT mark everything significant: `efficiency` has n=3 and cannot
    reach significance even though every one of its scenarios flipped."""
    compare(V2, V1)
    blob = json.loads((V1 / "comparison.json").read_text(encoding="utf-8"))
    cats = {c["category"]: c for c in blob["per_category"]}
    assert len(cats) >= 4

    assert cats["safety"]["significant_bh"] is True
    assert cats["efficiency"]["significant_bh"] is False, (
        "n=3 must not reach significance — if it does, the correction is not "
        "being applied")
    assert cats["efficiency"]["b_flips"] > 0, (
        "…and that is despite every efficiency scenario flipping, which is the point")


@needs_runs
def test_an_improvement_is_detected_but_does_not_block():
    r = compare(V1, V2, "--ci")
    assert r.returncode == CI_OK
    assert "IMPROVEMENT" in r.stdout


# ──────────────────────────────────────────────────────────── the A/A null
@needs_runs
def test_aa_comparison_raises_no_alarm():
    """The same agent against itself, same seeds. Zero flips, no verdict, exit 0.

    A tracker that cannot stay quiet on no change would flag every release."""
    r = compare(V1, V1B, "--ci")
    assert r.returncode == CI_OK, "an A/A comparison must never fail a build"
    assert "no significant difference" in r.stdout

    blob = json.loads((V1B / "comparison.json").read_text(encoding="utf-8"))
    assert blob["overall_flips"]["a_pass_b_fail"] == 0
    assert blob["overall_flips"]["a_fail_b_pass"] == 0
    assert blob["composite_delta"] == 0.0
    assert not blob["meaningful_effect"]
    for c in blob["per_category"]:
        assert c["significant_bh"] is False, (
            f"A/A flagged {c['category']} as significant — the tracker is crying wolf")


@needs_runs
def test_the_aa_null_is_honest_about_what_it_proves():
    """§7.10 applied to this test itself.

    Offline the two A/A runs are byte-identical, because the policy is
    deterministic (see L9: within-scenario variance is exactly zero). So this
    null is guaranteed by construction, and it proves a real but BOUNDED thing:
    the machinery does not invent flips out of identical inputs. It is NOT
    evidence that the tracker survives sampling noise — that needs an online A/A,
    which has never been run. Asserted so the claim cannot quietly inflate.
    """
    a = json.loads((V1 / "verdicts.json").read_text(encoding="utf-8"))
    b = json.loads((V1B / "verdicts.json").read_text(encoding="utf-8"))
    outcomes_a = [v["outcome"] for v in a]
    outcomes_b = [v["outcome"] for v in b]
    assert outcomes_a == outcomes_b, (
        "the A/A runs diverged — if the offline policy has become "
        "nondeterministic, this null suddenly means much more and L9 is wrong")
