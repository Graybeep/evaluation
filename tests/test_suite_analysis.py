"""Suite-level analysis (fix.md Tier 0): co-firing, discrimination, control
false positives, template coverage, distinct modes.

These report properties of the *suite*, so the tests here are mostly about the
shape of the answer rather than its value — specifically about the three ways
this repo has previously turned "not measured" into "measured clean":

  * a cell that could not be computed must be `None`, never `0.0`;
  * a partition must account for every scenario, with no residue;
  * a rate must carry the denominator it was computed against.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from are.score.suite import (ALWAYS_APPLICABLE, RULE_MODES, TRIGGERING_ASSERTION,
                             Row, applicability, cofire_matrix, discrimination,
                             distinct_modes, false_positives, template_coverage)

FROZEN = Path("frozen/frozen_scenarios.json")


def R(agent, sid, modes=(), outcome="FAIL", template="t", category="safety"):
    return Row(agent=agent, scenario_id=sid, template_id=template,
               category=category, modes=set(modes), outcome=outcome)


# ────────────────────────────────────────────────────────── G3 · co-firing
def test_matrix_is_fully_populated_no_silent_gaps():
    """fix.md's verify criterion: every cell present. A missing cell read as
    'uncorrelated' is the same fail-open as a 0 for 'nothing evaluated'."""
    rows = [R("a", "s1", ["DESTRUCTIVE_ACTION"]), R("b", "s2", ["TOOL_LOOP"])]
    m = cofire_matrix(rows)["matrix"]
    assert set(m) == set(RULE_MODES)
    for a in RULE_MODES:
        assert set(m[a]) == set(RULE_MODES), f"row {a} has missing cells"


def test_pair_that_never_fired_is_null_not_zero():
    """The load-bearing one. Two detectors that never fired have an UNDEFINED
    relationship; 0.0 would render as 'independent' and be read as evidence."""
    rows = [R("a", "s1", ["DESTRUCTIVE_ACTION"])]
    out = cofire_matrix(rows)
    assert out["matrix"]["TIMEOUT"]["TOOL_LOOP"] is None
    assert out["matrix"]["DESTRUCTIVE_ACTION"]["TIMEOUT"] == 0.0, (
        "one fired and the other did not — that IS a real zero")
    assert {"a": "TIMEOUT", "b": "TOOL_LOOP"} in out["undefined_pairs"] or \
           {"a": "TOOL_LOOP", "b": "TIMEOUT"} in out["undefined_pairs"]


def test_diagonal_is_the_raw_fire_count():
    rows = [R("a", f"s{i}", ["TOOL_LOOP"]) for i in range(4)]
    out = cofire_matrix(rows)
    assert out["matrix"]["TOOL_LOOP"]["TOOL_LOOP"] == 4.0
    assert out["fire_counts"]["TOOL_LOOP"] == 4


def test_perfect_correlation_is_flagged():
    rows = [R("a", f"s{i}", ["TOOL_LOOP", "BUDGET_EXCEEDED"]) for i in range(5)]
    pairs = cofire_matrix(rows)["correlated_pairs"]
    assert any({p["a"], p["b"]} == {"TOOL_LOOP", "BUDGET_EXCEEDED"} for p in pairs)


def test_single_agent_correlation_is_labelled_as_confounded():
    """A pair only one agent exercises is correlated because nothing separates
    them — a coverage finding, not proof of redundancy. Reporting it as the
    latter would overstate the result."""
    one = [R("looper", f"s{i}", ["TOOL_LOOP", "BUDGET_EXCEEDED"]) for i in range(5)]
    p = cofire_matrix(one)["correlated_pairs"][0]
    assert p["confounded_by_single_agent"] is True
    assert p["agents_exercising"] == ["looper"]

    two = one + [R("x", f"t{i}", ["TOOL_LOOP", "BUDGET_EXCEEDED"]) for i in range(5)]
    p2 = cofire_matrix(two)["correlated_pairs"][0]
    assert p2["confounded_by_single_agent"] is False
    assert p2["agents_exercising"] == ["looper", "x"]


def test_never_fired_detectors_are_named():
    rows = [R("a", "s1", ["DESTRUCTIVE_ACTION"])]
    assert "TIMEOUT" in cofire_matrix(rows)["never_fired"]


# ─────────────────────────────────────────────── G4 · suite discrimination
def test_partition_sums_with_no_residue():
    """§6's quitter/MISSING_CLARIFICATION precedent: never accept a partition
    that leaves scenarios unaccounted for."""
    rows = [R("a", "s1", outcome="PASS"), R("b", "s1", outcome="FAIL"),
            R("a", "s2", outcome="PASS"), R("b", "s2", outcome="PASS")]
    out = discrimination(rows)
    assert out["partition_sums"] is True
    assert out["separating"] + out["non_separating"] + out["incomplete"] == out["n_scenarios"]


def test_a_scenario_everyone_passes_separates_nothing():
    rows = [R("a", "s1", outcome="PASS"), R("b", "s1", outcome="PASS")]
    out = discrimination(rows)
    assert out["non_separating"] == 1
    assert out["effective_suite_size"] == 0, (
        "a scenario carrying no comparative information must not inflate the "
        "effective suite size")


def test_scenario_missing_an_agent_is_incomplete_not_zero():
    """Not run against every agent means it CANNOT be scored for separation —
    a third state, not a zero."""
    rows = [R("a", "s1", outcome="PASS"), R("b", "s1", outcome="FAIL"),
            R("a", "s2", outcome="PASS")]                       # b never ran s2
    out = discrimination(rows)
    assert out["incomplete"] == 1 and out["incomplete_ids"] == ["s2"]
    assert out["partition_sums"] is True


# ──────────────────────────────────────── G2 · false positives on control
def test_denominator_is_applicability_not_the_whole_suite():
    """Dividing by 60 makes a detector that could only fire on 3 scenarios look
    20x safer than it is."""
    rows = [R("clean", f"s{i}", []) for i in range(60)]
    app = {m: set() for m in RULE_MODES}
    app["ARG_CONSTRAINT_VIOLATED"] = {"s0", "s1", "s2"}
    out = false_positives(rows, applicable=app)
    v = out["per_detector"]["ARG_CONSTRAINT_VIOLATED"]
    assert v["applicable_n"] == 3, "denominator must be applicable scenarios"
    assert v["upper_bound"] > 0.4, (
        "0/3 knows almost nothing; the upper bound must say so loudly")


def test_zero_applicability_is_not_applicable_not_a_clean_zero():
    rows = [R("clean", "s1", [])]
    out = false_positives(rows, applicable={m: set() for m in RULE_MODES})
    v = out["per_detector"]["TIMEOUT"]
    assert v["state"] == "NOT APPLICABLE"
    assert v["rate"] is None and v["upper_bound"] is None, (
        "no opportunity to be wrong is not a 0% false-positive rate")


def test_upper_bound_is_reported_because_it_bounds_a_bad_thing():
    rows = [R("clean", f"s{i}", []) for i in range(36)]
    out = false_positives(rows, applicable={m: {f"s{i}" for i in range(36)}
                                            for m in RULE_MODES})
    v = out["per_detector"]["DESTRUCTIVE_ACTION"]
    assert v["rate"] == 0.0
    assert 0.05 < v["upper_bound"] < 0.15, (
        "0/36 is 'at most ~10%', never '0%'")


def test_a_flagged_control_is_surfaced():
    rows = [R("clean", "s1", ["DESTRUCTIVE_ACTION"])]
    out = false_positives(rows, applicable={m: {"s1"} for m in RULE_MODES})
    assert "DESTRUCTIVE_ACTION" in out["detectors_with_any_false_positive"]


def test_missing_control_is_reported_not_treated_as_clean():
    out = false_positives([R("looper", "s1", ["TOOL_LOOP"])])
    assert out["state"] == "MISSING"


# ────────────────────────────────────────────────── applicability mapping
def test_every_rule_detector_has_an_applicability_rule():
    """An unmapped detector silently gets n=0 and disappears from G2."""
    unmapped = [m for m in RULE_MODES
                if m not in TRIGGERING_ASSERTION and m not in ALWAYS_APPLICABLE]
    assert unmapped == [], f"detectors with no applicability rule: {unmapped}"


# ─────────────────────────────────────────────── G6 · template coverage
@pytest.mark.skipif(not FROZEN.exists(), reason="frozen set not generated")
def test_template_coverage_sums_to_the_suite():
    from are.cli import load_scenarios

    sc = load_scenarios(FROZEN)
    out = template_coverage(sc)
    assert out["sums_to_total"] is True
    assert out["n_scenarios"] == len(sc)
    assert sum(t["scenarios"] for t in out["per_template"]) == len(sc)


# ──────────────────────────────────────────────────── L13 · distinct modes
def test_distinct_modes_is_additive_and_counts_breadth():
    rows = [R("looper", "s1", ["TOOL_LOOP", "BUDGET_EXCEEDED"]),
            R("looper", "s2", ["WRONG_FINAL_STATE"]),
            R("clean", "s1", [])]
    out = distinct_modes(rows)
    assert out["looper"]["distinct_modes"] == 3
    assert out["clean"]["distinct_modes"] == 0
    assert out["looper"]["by_severity"]["MAJOR"]


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen set not generated")
def test_reporting_distinct_modes_does_not_change_any_score():
    """L13 is purely additive. Composite scoring must be byte-identical with
    the new reporting in place, or this stopped being a report and became a
    change to published numbers."""
    from are.cli import load_scenarios
    from are.runner.loop import execute_run
    from are.score.compute import compute
    from are.verify.rules import verify

    sc = load_scenarios(FROZEN)[:12]
    verdicts = [verify(s, execute_run(s, "looper", offline=True)) for s in sc]
    before = compute(verdicts, model_version="offline-scripted-policy").composite.point

    rows = [Row(agent="looper", scenario_id=s.id, template_id=s.template_id,
                category=s.category, modes={f.mode for f in v.findings},
                outcome=v.outcome) for s, v in zip(sc, verdicts)]
    distinct_modes(rows)

    after = compute(verdicts, model_version="offline-scripted-policy").composite.point
    assert before == after


# ─────────────────────────────────────────────────── emitted artifacts
REPORTS = Path("reports")


@pytest.mark.skipif(not (REPORTS / "detector_cofire.json").exists(),
                    reason="run `python -m are.cli analyse` first")
def test_emitted_reports_are_well_formed():
    co = json.loads((REPORTS / "detector_cofire.json").read_text(encoding="utf-8"))
    assert len(co["modes"]) == len(RULE_MODES)
    # fix.md specified an 8x8 matrix from "8 independent rule detectors".
    # There are 11; the spec was written against a stale count.
    assert len(co["matrix"]) == 11

    di = json.loads((REPORTS / "suite_discrimination.json").read_text(encoding="utf-8"))
    assert di["partition_sums"] is True
    assert di["n_scenarios"] == 60

    tc = json.loads((REPORTS / "template_coverage.json").read_text(encoding="utf-8"))
    assert tc["sums_to_total"] is True


# ─────────────────────────────── published figures must match the artifacts
@pytest.mark.skipif(not FROZEN.exists(), reason="frozen set not generated")
def test_readme_fabrication_split_matches_the_artifact():
    """L11/L12. The README publishes a 17 / 18 / 25 partition and a 0.82 Wilson
    lower bound. fix.md described it as "17/43", collapsing two distinct buckets
    — a scenario that never got the trigger and one where the agent's own gate
    stopped it are different findings, so the finer split is published."""
    from are.calib.defects import coverage
    from are.cli import load_scenarios
    from are.runner.loop import execute_run
    from are.score.stats import wilson_ci
    from are.verify.rules import verify

    sc = load_scenarios(FROZEN)
    rows = [(s, r, verify(s, r).outcome)
            for s, r in ((s, execute_run(s, "confabulator", offline=True)) for s in sc)]
    cov = coverage("confabulator", rows)

    fired = cov["scenarios_defect_fired"]
    no_trigger = cov["scenarios_no_trigger"]
    gated = cov["scenarios_gated_before_firing"]
    assert fired + no_trigger + gated == len(sc), "the partition must leave no residue"
    assert (fired, no_trigger, gated) == (17, 18, 25), (
        "README publishes this split; update both together")

    lb = wilson_ci(cov["scenarios_detectable"], cov["scenarios_detectable"]).low
    assert round(lb, 2) == 0.82, "README quotes the 0.82 lower bound, not the point"


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen set not generated")
def test_offline_invalid_rate_is_zero_and_reportable():
    """"Invalid rate is a gate, not a published number" — it is published now,
    so it needs a check that would notice it changing."""
    from are.cli import load_scenarios
    from are.runner.loop import execute_run
    from are.score.compute import compute
    from are.verify.rules import verify

    sc = load_scenarios(FROZEN)
    for agent in ("clean", "confabulator", "looper", "pushover"):
        verdicts = [verify(s, execute_run(s, agent, offline=True)) for s in sc]
        card = compute(verdicts, agent_version=agent,
                       model_version="offline-scripted-policy")
        assert card.invalid_rate == 0.0, f"{agent} invalid_rate is no longer 0"
        assert card.reportable is True, f"{agent} is no longer reportable"


# ──────────────────────────────────── L9 · what N=3 does and does not buy
@pytest.mark.skipif(not FROZEN.exists(), reason="frozen set not generated")
def test_offline_within_scenario_variance_is_exactly_zero():
    """N=3 measures within-scenario decode noise. Against a deterministic
    scripted policy that quantity is exactly zero, so offline the three repeats
    carry NO information — they are three identical runs.

    This is stated in the README rather than left for a reviewer to notice, and
    asserted here so the claim cannot rot."""
    import collections

    from are.cli import load_scenarios
    from are.runner.loop import execute_run
    from are.verify.rules import verify

    for agent in ("looper", "pushover", "confabulator"):
        per_scenario = collections.defaultdict(set)
        for s in load_scenarios(FROZEN):
            for rep in range(3):
                v = verify(s, execute_run(s, agent, offline=True, repeat_idx=rep))
                per_scenario[s.id].add(v.outcome)
        mixed = [sid for sid, outs in per_scenario.items() if len(outs) > 1]
        assert mixed == [], (
            f"{agent}: {len(mixed)} scenario(s) vary across repeats offline. If this "
            f"is real, offline flakiness is now measurable and the README claim that "
            f"it is structurally unmeasurable must be updated.")


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen set not generated")
def test_loopers_zero_width_ci_is_degenerate_for_the_stated_reason():
    """§7 says `looper`'s zero-width interval comes from 60 identical *scenario*
    scores. A cheaper explanation is available — offline runs are identical — and
    it would be wrong. Same symptom, different cause.

    Proven by counterexample rather than by assertion: `pushover` and
    `confabulator` have exactly the same zero within-scenario variance and
    non-degenerate intervals, because the bootstrap resamples SCENARIOS. So
    identical repeats cannot be what collapses an interval.
    """
    import collections

    from are.cli import load_scenarios
    from are.runner.loop import execute_run
    from are.score.compute import compute
    from are.verify.rules import verify

    scenarios = load_scenarios(FROZEN)
    cards, spread = {}, {}
    for agent in ("looper", "pushover", "confabulator"):
        verdicts = [verify(s, execute_run(s, agent, offline=True, repeat_idx=r))
                    for s in scenarios for r in range(3)]
        cards[agent] = compute(verdicts, agent_version=agent,
                               model_version="offline-scripted-policy")
        spread[agent] = collections.Counter(
            v.outcome for v in verdicts[::3])          # one repeat per scenario

    # looper: every scenario lands on the same outcome -> nothing to resample
    assert len(spread["looper"]) == 1, "looper's scenarios are no longer uniform"
    assert cards["looper"].composite.degenerate is True
    assert cards["looper"].composite.high == cards["looper"].composite.low

    # the counterexample: same determinism, different scenario spread, real width
    for agent in ("pushover", "confabulator"):
        assert len(spread[agent]) > 1
        assert cards[agent].composite.degenerate is False, (
            f"{agent} should have a real interval — if it does not, the bootstrap "
            f"is collapsing for a reason other than scenario uniformity")
        assert cards[agent].composite.high > cards[agent].composite.low


# ─────────────────────── G1 · three findings, or one counted three times?
@pytest.mark.skipif(not FROZEN.exists(), reason="frozen set not generated")
def test_quitters_signatures_are_mostly_disjoint_not_triple_counted():
    """fix.md G1, to be answered before the demo rather than during it.

    `quitter` firing several signatures from one injected defect is presented as
    a strength. The hostile reading is that these are correlated categories
    triple-counting one failure. The co-fire structure settles it, and the
    answer is neither option:

      REFUSAL_EXPECTED       30 scenarios  ]
      TASK_INCOMPLETE        14            ]- pairwise Jaccard 0.000 between
      WRONG_FINAL_STATE      14            ]  these three GROUPS: fully disjoint
      MISSING_CLARIFICATION   9            ]

    but TASK_INCOMPLETE and WRONG_FINAL_STATE have Jaccard **1.000** — the same
    14 scenarios, always together. So: three genuinely distinct findings about
    three disjoint situations, ONE of which is described by two mode names.

    That single double-count does not inflate the score: worst-finding scoring
    (§8.1) charges the pair once, at the MAJOR of the two. It does inflate a
    naive distinct-mode count, which is why L13 reports breadth separately.
    """
    import collections
    import itertools

    from are.cli import load_scenarios
    from are.runner.loop import execute_run
    from are.verify.rules import verify
    from are.verify.taxonomy import SEVERITY

    scenarios = load_scenarios(FROZEN)
    fired = {}
    for s in scenarios:
        v = verify(s, execute_run(s, "quitter", offline=True))
        for f in v.findings:
            fired.setdefault(f.mode, set()).add(s.id)

    def jaccard(a, b):
        u = fired[a] | fired[b]
        return len(fired[a] & fired[b]) / len(u) if u else None

    # the pair that IS one event under two names
    assert jaccard("TASK_INCOMPLETE", "WRONG_FINAL_STATE") == 1.0
    assert SEVERITY["TASK_INCOMPLETE"] == "MINOR"
    assert SEVERITY["WRONG_FINAL_STATE"] == "MAJOR"

    # every other pairing is fully disjoint -> genuinely separate findings
    groups = ["REFUSAL_EXPECTED", "WRONG_FINAL_STATE", "MISSING_CLARIFICATION"]
    for a, b in itertools.combinations(groups, 2):
        assert jaccard(a, b) == 0.0, (
            f"{a} and {b} now overlap; the 'three disjoint findings' answer to G1 "
            f"no longer holds and the demo answer must change")

    # and the partition accounts for all 60, with no residue
    buckets = collections.Counter()
    for s in scenarios:
        modes = {f.mode for f in verify(s, execute_run(s, "quitter", offline=True)).findings}
        if not modes:
            buckets["passed"] += 1
        elif "REFUSAL_EXPECTED" in modes:
            buckets["refused_nothing"] += 1
        elif {"TASK_INCOMPLETE", "WRONG_FINAL_STATE"} <= modes:
            buckets["incomplete_and_wrong_state"] += 1
        elif "MISSING_CLARIFICATION" in modes:
            buckets["did_not_ask"] += 1
        else:
            buckets["unclassified"] += 1

    assert buckets["unclassified"] == 0, "the G1 partition leaves a residue"
    assert sum(buckets.values()) == len(scenarios) == 60
    assert dict(buckets) == {"refused_nothing": 30, "incomplete_and_wrong_state": 14,
                             "did_not_ask": 9, "passed": 7}
