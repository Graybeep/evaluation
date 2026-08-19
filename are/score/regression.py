"""Paired regression tracker (CLAUDE.md §8.2, §8.3, §7.6).

Comparison rules, all of them load-bearing:

  * **Paired only.** Same scenario set, same seeds, same world states. An unpaired
    two-proportion test throws away the pairing and needs several times the sample size
    for the same power. `compare()` refuses to run on a mismatched scenario set.
  * **McNemar on pass<->fail flips**, exact binomial, at the scenario level (majority of
    that scenario's valid runs). Raw flip counts are always reported next to the p-value,
    so the finding survives even if you distrust the test (§12).
  * **Benjamini–Hochberg at q=0.10** across the per-category tests. Uncorrected, you get a
    false regression alarm nearly every release and the team disables the gate.
  * **Effect size, not just p.** A significant 0.4-point composite drop is noise; the
    minimum meaningful effect is 3 composite points and is stated in the output.
  * **Flaky scenarios are excluded** from the test and listed separately (§8.3).

The output advises. It never gates (§7.6) — no function here returns "block the merge".
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from are.schema.verdict import Verdict
from are.score.compute import MIN_MEANINGFUL_EFFECT, compute, roll_scenarios
from are.score.stats import benjamini_hochberg, mcnemar

HISTORY_PATH = Path("runs/history.jsonl")


@dataclass
class CategoryTest:
    category: str
    n_scenarios: int
    a_pass: int
    b_pass: int
    b_flips: int          # A pass -> B fail
    c_flips: int          # A fail -> B pass
    p_value: float
    significant_bh: bool = False


@dataclass
class Comparison:
    baseline: str
    candidate: str
    n_scenarios_compared: int
    excluded_flaky: list[str]
    composite_a: float
    composite_b: float
    composite_delta: float
    meaningful_effect: bool
    overall_flips: dict
    overall_p: float
    per_category: list[CategoryTest] = field(default_factory=list)
    verdict: str = ""
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["per_category"] = [asdict(c) for c in self.per_category]
        return d


def _scenario_pass(roll) -> bool | None:
    """Majority of valid runs. None when the scenario has no valid run in this arm."""
    if not roll or roll.n_valid == 0:
        return None
    return roll.n_pass * 2 > roll.n_valid


def compare(baseline: list[Verdict], candidate: list[Verdict],
            baseline_name: str = "A", candidate_name: str = "B",
            q: float = 0.10) -> Comparison:
    ra, rb = roll_scenarios(baseline), roll_scenarios(candidate)
    shared = sorted(set(ra) & set(rb))
    if not shared:
        raise ValueError("no shared scenarios — a version comparison must be paired (§8.2)")

    only_a, only_b = sorted(set(ra) - set(rb)), sorted(set(rb) - set(ra))
    flaky = sorted({sid for sid in shared if ra[sid].flaky or rb[sid].flaky})

    usable = [sid for sid in shared if sid not in flaky
              and _scenario_pass(ra[sid]) is not None
              and _scenario_pass(rb[sid]) is not None]

    b_flips = sum(1 for sid in usable if _scenario_pass(ra[sid]) and not _scenario_pass(rb[sid]))
    c_flips = sum(1 for sid in usable if not _scenario_pass(ra[sid]) and _scenario_pass(rb[sid]))
    overall = mcnemar(b_flips, c_flips)

    sc_a = compute([v for v in baseline if v.scenario_id in usable], exclude_flaky=False)
    sc_b = compute([v for v in candidate if v.scenario_id in usable], exclude_flaky=False)
    delta = sc_b.composite.point - sc_a.composite.point

    cats = sorted({ra[sid].category for sid in usable})
    tests: list[CategoryTest] = []
    for cat in cats:
        ids = [sid for sid in usable if ra[sid].category == cat]
        bf = sum(1 for sid in ids if _scenario_pass(ra[sid]) and not _scenario_pass(rb[sid]))
        cf = sum(1 for sid in ids if not _scenario_pass(ra[sid]) and _scenario_pass(rb[sid]))
        m = mcnemar(bf, cf)
        tests.append(CategoryTest(
            category=cat, n_scenarios=len(ids),
            a_pass=sum(1 for sid in ids if _scenario_pass(ra[sid])),
            b_pass=sum(1 for sid in ids if _scenario_pass(rb[sid])),
            b_flips=bf, c_flips=cf, p_value=m.p_value))
    for t, rej in zip(tests, benjamini_hochberg([t.p_value for t in tests], q=q)):
        t.significant_bh = rej

    meaningful = abs(delta) >= MIN_MEANINGFUL_EFFECT
    if delta < 0 and meaningful and overall.p_value < 0.05:
        verdict = "REGRESSION — significant and larger than the minimum meaningful effect"
    elif delta > 0 and meaningful and overall.p_value < 0.05:
        verdict = "IMPROVEMENT — significant and larger than the minimum meaningful effect"
    elif overall.p_value < 0.05:
        verdict = (f"statistically significant but below the {MIN_MEANINGFUL_EFFECT}-point "
                   f"minimum meaningful effect — treat as noise in practice")
    else:
        verdict = "no significant difference"

    notes = [f"minimum meaningful effect: {MIN_MEANINGFUL_EFFECT} composite points",
             "this report advises; it does not gate (§7.6)"]
    if flaky:
        notes.append(f"{len(flaky)} flaky scenario(s) excluded from the test (§8.3)")
    if only_a or only_b:
        notes.append(f"unpaired scenarios ignored: {len(only_a)} only in {baseline_name}, "
                     f"{len(only_b)} only in {candidate_name}")

    return Comparison(
        baseline=baseline_name, candidate=candidate_name,
        n_scenarios_compared=len(usable), excluded_flaky=flaky,
        composite_a=round(sc_a.composite.point, 2),
        composite_b=round(sc_b.composite.point, 2),
        composite_delta=round(delta, 2), meaningful_effect=meaningful,
        overall_flips=overall.as_dict(), overall_p=overall.p_value,
        per_category=tests, verdict=verdict, notes=notes)


# ------------------------------------------------------------------- history
def append_history(entry: dict, path: Path | str = HISTORY_PATH) -> None:
    """Append-only JSONL. Never rewritten, so a regression trail cannot be quietly edited."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def read_history(path: Path | str = HISTORY_PATH) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
