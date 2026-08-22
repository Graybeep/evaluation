"""`cohens_kappa` is implemented and called from nowhere. That is the gap this closes.

Unused-but-present is worse than absent. A reader skimming `score/stats.py` sees a kappa
implementation sitting beside the bootstrap and the McNemar test — both of which *are*
wired — and reasonably concludes agreement was measured. Nothing in the artifacts
contradicts that, because absence of a kappa field renders identically to "we didn't print
it". Same family as `judge_version()` returning `"unavailable"` while the judge answered.

Deleting it would be the wrong fix: the maths is right, and §11.1 names the κ study as the
one genuinely closable gap. So it is **gated** — reachable on purpose, unreachable by
accident — and these tests assert the three things that make the gate real:

  1. it raises by default, with a reason;
  2. nothing in `are/` calls it, so "unreached" is a fact about the code, not a hope;
  3. no shipped artifact carries a kappa value, so nothing can *read* as calibrated.

If T3 (the κ study) lands, (1) gains a legitimate caller and (2) and (3) change together
with the disclosure. Until then all three must hold.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from are.score.stats import KappaRequiresHumanLabels, cohens_kappa

ARE = Path(__file__).resolve().parent.parent / "are"


def test_it_raises_by_default_rather_than_returning_a_number():
    """The load-bearing assertion. A kappa returned here would be judge-vs-judge
    self-consistency, which is not calibration and would be read as calibration."""
    with pytest.raises(KappaRequiresHumanLabels) as e:
        cohens_kappa(["FAIL", "PASS", "FAIL"], ["FAIL", "PASS", "PASS"])
    msg = str(e.value)
    assert "human labels" in msg and "§11.1" in msg, (
        "the error must say WHY it refuses, not just that it refused")


def test_the_refusal_is_not_an_arithmetic_failure():
    """It refuses on provenance, not on the numbers — so it must compute cleanly the
    moment real labels exist. Otherwise the gate is hiding a broken implementation and
    T3 would discover that at the worst possible moment."""
    k = cohens_kappa(["FAIL", "PASS", "FAIL", "PASS"], ["FAIL", "PASS", "PASS", "PASS"],
                     bootstrap=200, human_labels=True)
    assert 0.0 <= k.observed_agreement <= 1.0
    assert k.n == 4
    assert isinstance(k.interpretation, str) and k.interpretation


def test_nothing_in_the_package_calls_it():
    """'Unreached' asserted over the code, not assumed.

    A static reference scan rather than a coverage run: coverage tells you it was not
    called *on the paths the tests exercised*, which is precisely the weaker claim that
    §7.10 warns about."""
    offenders = []
    for py in ARE.rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        if "cohens_kappa" not in src:
            continue
        if py.name == "stats.py" and py.parent.name == "score":
            continue                          # its own definition
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = getattr(f, "id", None) or getattr(f, "attr", None)
                if name == "cohens_kappa":
                    offenders.append(f"{py.relative_to(ARE.parent)}:{node.lineno}")
    assert offenders == [], (
        f"cohens_kappa is now called from {offenders}. If that is the T3 study, this "
        f"test and the README/CLAUDE.md disclosure must change together — a live call "
        f"site with a stale 'no κ is reported' claim is worse than either alone.")


def test_its_own_definition_is_the_only_reference_that_survives_a_grep():
    """Guards the shape of the previous test: if the function were renamed or
    re-exported, the AST scan above would quietly find nothing to check."""
    hits = sorted(p.relative_to(ARE.parent).as_posix()
                  for p in ARE.rglob("*.py") if "cohens_kappa" in p.read_text(encoding="utf-8"))
    assert hits == ["are/score/stats.py"], (
        f"cohens_kappa is referenced in {hits}; the AST scan assumes one definition site")


def test_no_shipped_artifact_carries_a_kappa_value():
    """The reader-facing half. The gate stops accidental computation; this stops a
    number reaching a report by any route, including one hand-pasted."""
    root = Path(__file__).resolve().parent.parent
    suspects = []
    for j in list((root / "reports").glob("*.json")) + list(root.glob("runs/*/scorecard.json")):
        try:
            blob = json.loads(j.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue

        def walk(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    if "kappa" in k.lower():
                        suspects.append(f"{j.name}:{path}/{k}")
                    walk(v, f"{path}/{k}")
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f"{path}[{i}]")

        walk(blob)
    assert suspects == [], (
        f"a kappa value reached a shipped artifact: {suspects}. No agreement study has "
        f"been run, so this number cannot be what a reader will take it for.")


def test_the_disclosure_still_says_no_kappa_is_reported():
    """Docs and code asserted together. The failure mode being prevented is drift in
    EITHER direction: a live call site under a 'no κ' claim, or a 'κ reported' claim
    with nothing computing it — CLAUDE.md §0.5 records that the table once claimed
    exactly the latter."""
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
    assert "no κ is reported" in readme or "no kappa is reported" in readme.lower(), (
        "README no longer states that no κ is reported — if the study ran, update this "
        "test; if it did not, restore the disclosure")
