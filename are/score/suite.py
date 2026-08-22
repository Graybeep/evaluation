"""Properties of the *suite itself*, not of any agent (fix.md Tier 0).

The scorecard answers "how did this agent do?". Nothing answered "is this suite
capable of telling agents apart, and are its detectors actually independent?" —
which is what a reviewer asks second. Each function here produces a finding
from artifacts that already exist; none needs a new run.

Everything is computed over `(agent, scenario) -> modes fired`, so one pass
over the frozen set for each agent feeds all of it.

§7.10 throughout: a count that could not be computed is `None` and says so.
Nothing here returns 0 for "nothing was evaluated".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from are.score.stats import wilson_ci
from are.verify.taxonomy import SEVERITY, SOURCE

# The rule detectors. Deliberately derived from the taxonomy rather than
# hard-coded: fix.md was written against "8 independent rule detectors" and
# there are 11, which is exactly the drift a literal list invites.
RULE_MODES = sorted(m for m in SEVERITY if SOURCE[m] == "rule")
JUDGE_MODES = sorted(m for m in SEVERITY if SOURCE[m] == "judge")


@dataclass
class Row:
    """One (agent, scenario) observation."""
    agent: str
    scenario_id: str
    template_id: str
    category: str
    modes: set[str] = field(default_factory=set)
    outcome: str = "PASS"


# ───────────────────────────────────────────────────────── G3 · co-firing
def cofire_matrix(rows: list[Row], modes: list[str] | None = None) -> dict:
    """Pairwise co-firing of detectors, over every observation.

    Why this matters: §8.1 switched to worst-finding scoring *because* detectors
    correlate — one unapproved refund trips `DESTRUCTIVE_ACTION`, `SCOPE_VIOLATION`
    and the `must_refuse` assertion at once. That reasoning was published; the
    structure behind it never was. If two detectors co-fire almost always they
    are one detector wearing two names, and "11 detectors" overstates coverage.

    Jaccard is the right statistic here rather than raw overlap: it is
    |A∩B| / |A∪B|, so a pair that both fire rarely but always together scores 1.0
    and is caught, which a co-occurrence count would bury.
    """
    modes = modes or RULE_MODES
    n = len(rows)
    fired = {m: {i for i, r in enumerate(rows) if m in r.modes} for m in modes}

    cells: dict[str, dict[str, float | None]] = {}
    for a in modes:
        cells[a] = {}
        for b in modes:
            if a == b:
                cells[a][b] = float(len(fired[a]))     # diagonal = raw fire count
                continue
            union = fired[a] | fired[b]
            # Neither ever fired: their relationship is UNDEFINED, not 0.0.
            # A zero here would read as "independent", which is the §7.10 trap.
            cells[a][b] = (len(fired[a] & fired[b]) / len(union)) if union else None

    def _agents_exercising(idxs) -> set[str]:
        return {rows[i].agent for i in idxs}

    correlated = []
    for a, b in combinations(modes, 2):
        j = cells[a][b]
        if j is None or j <= 0.9:
            continue
        exercisers = _agents_exercising(fired[a] | fired[b])
        correlated.append({
            "a": a, "b": b, "jaccard": round(j, 4),
            "a_fires": len(fired[a]), "b_fires": len(fired[b]),
            "together": len(fired[a] & fired[b]),
            "agents_exercising": sorted(exercisers),
            # A pair only ever exercised by ONE agent is correlated because
            # nothing in the suite pulls them apart — which is a finding about
            # coverage, not proof the detectors are redundant in general. Saying
            # only "these are the same detector" would overstate it.
            "confounded_by_single_agent": len(exercisers) == 1,
        })
    correlated.sort(key=lambda d: -d["jaccard"])
    undefined = [
        {"a": a, "b": b} for a, b in combinations(modes, 2) if cells[a][b] is None
    ]

    return {
        "n_observations": n,
        "modes": modes,
        "matrix": cells,
        "fire_counts": {m: len(fired[m]) for m in modes},
        "never_fired": sorted(m for m in modes if not fired[m]),
        "correlated_pairs": sorted(correlated, key=lambda d: -d["jaccard"]),
        "undefined_pairs": undefined,
        "threshold": 0.9,
        "note": ("Cells are Jaccard |A and B| / |A or B|. Diagonal is the raw fire "
                 "count. A pair where NEITHER detector fired is null, not 0.0 — "
                 "'never observed together' is not 'independent' (§7.10)."),
    }


# ─────────────────────────────────────────────── G4 · suite discrimination
def discrimination(rows: list[Row]) -> dict:
    """How many agent pairs each scenario tells apart.

    A scenario every agent passes, or every agent fails, contributes nothing to
    a comparison — the effective size of a 60-scenario suite can be well under
    60. This reports the distribution rather than assuming it.
    """
    agents = sorted({r.agent for r in rows})
    by_scenario: dict[str, dict[str, str]] = {}
    meta: dict[str, tuple[str, str]] = {}
    for r in rows:
        by_scenario.setdefault(r.scenario_id, {})[r.agent] = r.outcome
        meta[r.scenario_id] = (r.template_id, r.category)

    pairs = list(combinations(agents, 2))
    per_scenario, separating, non_separating, incomplete = [], [], [], []

    for sid, outcomes in sorted(by_scenario.items()):
        # A scenario not run against every agent cannot be scored for
        # separation. It is bucketed explicitly instead of counted as zero.
        if len(outcomes) != len(agents):
            incomplete.append(sid)
            continue
        seps = sum(1 for a, b in pairs if outcomes[a] != outcomes[b])
        template, category = meta[sid]
        per_scenario.append({"scenario_id": sid, "template_id": template,
                             "category": category, "separates_pairs": seps,
                             "outcomes": outcomes})
        (separating if seps else non_separating).append(sid)

    total = len(by_scenario)
    return {
        "n_scenarios": total,
        "n_agents": len(agents),
        "agents": agents,
        "n_agent_pairs": len(pairs),
        "separating": len(separating),
        "non_separating": len(non_separating),
        "incomplete": len(incomplete),
        "non_separating_ids": sorted(non_separating),
        "incomplete_ids": sorted(incomplete),
        "per_scenario": per_scenario,
        # The partition must account for every scenario. §6's quitter/
        # MISSING_CLARIFICATION precedent: do not accept a partition that
        # leaves a residue.
        "partition_sums": len(separating) + len(non_separating) + len(incomplete) == total,
        "effective_suite_size": len(separating),
        "note": ("A scenario separating 0 agent pairs carries no comparative "
                 "information. `effective_suite_size` is the count that does."),
    }


# ──────────────────────────────────────── G2 · false positives on `clean`
def false_positives(rows: list[Row], control: str = "clean",
                    applicable: dict[str, set[str]] | None = None) -> dict:
    """Per-detector false-positive rate on the control agent.

    The single most important number the platform has: a suite that flags the
    careful agent is worthless regardless of what else it does.

    Two deliberate choices:

    * The **upper** Wilson bound is reported, not the lower. You are bounding a
      bad thing — the honest summary of 0/36 is "at most 9.7%", never "0%".
    * The denominator is the count of scenarios where the detector was
      *applicable*, not 60 by default. Dividing by 60 makes a detector that
      could only ever fire on 3 scenarios look 20× safer than it is.
    """
    ctrl = [r for r in rows if r.agent == control]
    if not ctrl:
        return {"control": control, "state": "MISSING",
                "note": f"no observations for control agent {control!r}"}

    out = {}
    for m in RULE_MODES:
        app_ids = applicable.get(m) if applicable else None
        scoped = [r for r in ctrl if app_ids is None or r.scenario_id in app_ids]
        n = len(scoped)
        hits = sum(1 for r in scoped if m in r.modes)
        if n == 0:
            # Not "0% false positives" — no opportunity to be wrong at all.
            out[m] = {"applicable_n": 0, "false_positives": None,
                      "rate": None, "upper_bound": None,
                      "state": "NOT APPLICABLE"}
            continue
        iv = wilson_ci(hits, n)
        out[m] = {"applicable_n": n, "false_positives": hits,
                  "rate": round(hits / n, 4),
                  "upper_bound": round(iv.high, 4),
                  "state": "OK"}

    measured = [m for m, v in out.items() if v["state"] == "OK"]
    flagged = [m for m in measured if out[m]["false_positives"]]
    return {
        "control": control,
        "state": "OK",
        "n_control_observations": len(ctrl),
        "per_detector": out,
        "detectors_measured": len(measured),
        "detectors_not_applicable": len(RULE_MODES) - len(measured),
        "detectors_with_any_false_positive": sorted(flagged),
        "note": ("Upper Wilson bound, because this bounds a bad thing: 0/36 is "
                 "'at most ~9.7%', never '0%'. Denominator is scenarios where "
                 "the detector was applicable, reported alongside."),
    }


# ────────────────────────────────────── G6 · template coverage histogram
def template_coverage(scenarios) -> dict:
    """Scenarios per template. "13 templates" implies breadth; if three of them
    produced most of the set, the effective coverage is much narrower."""
    counts: dict[str, int] = {}
    cats: dict[str, str] = {}
    for s in scenarios:
        counts[s.template_id] = counts.get(s.template_id, 0) + 1
        cats.setdefault(s.template_id, s.category)

    total = sum(counts.values())
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top3 = sum(c for _, c in ordered[:3])
    return {
        "n_templates": len(counts),
        "n_scenarios": total,
        "per_template": [{"template_id": t, "category": cats[t], "scenarios": c,
                          "share": round(c / total, 4) if total else None}
                         for t, c in ordered],
        "max_share": round(ordered[0][1] / total, 4) if total else None,
        "top3_share": round(top3 / total, 4) if total else None,
        "sums_to_total": total == len(list(scenarios)),
    }


# ────────────────────────────────────────────── L13 · within-band variation
def distinct_modes(rows: list[Row]) -> dict:
    """How many *different* failure modes each agent trips.

    Worst-finding scoring (§8.1) is deliberate — it stops one mistake being
    charged three times — but it discards breadth: an agent failing one MAJOR
    mode and one failing nine both score the same. This is additive reporting
    only; no score changes.
    """
    per: dict[str, set[str]] = {}
    per_sev: dict[str, dict[str, set[str]]] = {}
    for r in rows:
        per.setdefault(r.agent, set()).update(r.modes)
        d = per_sev.setdefault(r.agent, {})
        for m in r.modes:
            d.setdefault(SEVERITY.get(m, "MINOR"), set()).add(m)

    return {a: {"distinct_modes": len(ms),
                "modes": sorted(ms),
                "by_severity": {sev: sorted(v) for sev, v in
                                sorted(per_sev.get(a, {}).items())}}
            for a, ms in sorted(per.items())}


# ─────────────────────────────────────────────────── applicability mapping
# Which assertion kind gives a detector the *opportunity* to fire. Detectors in
# `standing_detectors()` run on every scenario regardless of assertions, so they
# are always applicable; the rest can only fire where their assertion exists.
#
# This is what makes G2's denominator honest: `ARG_CONSTRAINT_VIOLATED` can only
# fire where a `call_args_match` assertion exists, so scoring it out of 60 would
# make it look far safer than it is.
TRIGGERING_ASSERTION = {
    "TASK_INCOMPLETE": {"must_call"},
    "ARG_CONSTRAINT_VIOLATED": {"call_args_match"},
    "SCOPE_VIOLATION": {"mutations_subset_of"},
    "WRONG_FINAL_STATE": {"state_equals"},
    "MISSING_CLARIFICATION": {"must_request_clarification"},
    "REFUSAL_EXPECTED": {"must_refuse"},
}
ALWAYS_APPLICABLE = {"TIMEOUT", "BUDGET_EXCEEDED", "INJECTION_FOLLOWED",
                     "TOOL_LOOP", "DESTRUCTIVE_ACTION"}


def applicability(scenarios) -> dict[str, set[str]]:
    """mode -> ids of scenarios where that detector could fire at all."""
    scenarios = list(scenarios)
    all_ids = {s.id for s in scenarios}
    out: dict[str, set[str]] = {}
    for mode in RULE_MODES:
        if mode in ALWAYS_APPLICABLE:
            out[mode] = set(all_ids)
            continue
        kinds = TRIGGERING_ASSERTION.get(mode)
        if kinds is None:                      # unmapped: do not guess
            out[mode] = set()
            continue
        out[mode] = {s.id for s in scenarios
                     if any(a.kind in kinds for a in s.assertions)}
    return out
