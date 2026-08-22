# -*- coding: utf-8 -*-
"""C1 — revert-check the Phase 1/2 tests.

For each shipped fix: revert it, run the suite, confirm RED, restore. A test that
stays green with its subject reverted is not evidence, and "247 passed" is a
reading, not a result.

Restoration is unconditional (try/finally per mutation, plus a final sweep), and
the script verifies the tree is green again before it writes its report.
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAK = Path(__file__).resolve().parent / ".revert_backup"
OUT = ROOT / "reports" / "revert_verified.json"

LF, CRLF = chr(10), chr(13) + chr(10)

# (id, spec-item, file, old, new, why it must go red)
MUTATIONS = [
    ("G3-null-cell", "G3 co-fire matrix", "are/score/suite.py",
     'cells[a][b] = (len(fired[a] & fired[b]) / len(union)) if union else None',
     'cells[a][b] = (len(fired[a] & fired[b]) / len(union)) if union else 0.0',
     "a null cell must not read as 'uncorrelated'"),

    ("G4-partition-sum", "G4 discrimination", "are/score/suite.py",
     '    if residue:' + LF + '        raise RuntimeError(',
     '    if False:' + LF + '        raise RuntimeError(',
     "a partition that leaves a residue must raise, not report a flag"),

    ("G2-applicability", "G2 clean FP rate", "are/score/suite.py",
     "scoped = [r for r in ctrl if app_ids is None or r.scenario_id in app_ids]",
     "scoped = list(ctrl)",
     "denominator 60-by-default must fail"),

    ("L13-distinct-modes", "L13 distinct_modes", "are/score/compute.py",
     '"distinct_modes": len(self.per_mode),',
     '"distinct_modes_MISSING": len(self.per_mode),',
     "absence of the field must fail; composites must stay byte-identical"),

    ("P1-regression-trigger", "P1 CI exit codes (regression)", "are/cli.py",
     'return CI_REGRESSION if verdict.startswith("REGRESSION") else CI_OK',
     'return CI_OK',
     "a regression alone must fail the build"),

    ("P1-unreportable-trigger", "P1 CI exit codes (reportable=False)", "are/cli.py",
     '    if not (reportable_a and reportable_b):' + LF + '        return CI_UNREPORTABLE' + LF,
     '',
     "reportable=False must fail the build on its own"),

    ("P2-drift", "P2 drifter", "are/calib/drifter.py",
     "drifted = _drift(call_tool, it, mark, prior_reads=reads)",
     "drifted = None",
     "mutations_subset_of must fire, and fire FOR the drift"),

    ("P3-aa-null", "P3 A/A null", "are/score/regression.py",
     "        t.significant_bh = rej",
     "        t.significant_bh = True",
     "A/A must produce zero flagged regressions"),

    ("L7-gate-evaluated", "L7 gate_evaluated", "are/gen/feasibility.py",
     '    reason = static_check(s)' + LF + '    if receipt is not None:' + LF +
     '        receipt["static_checked"] = True' + LF,
     '    reason = static_check(s)' + LF,
     "any scenario accepted without an explicit evaluation record must fail"),

    # Added after the first C1 sweep. A coverage check over the tests written
    # DURING C1 found two that no mutation could kill — including one that was
    # itself a tautology, written to replace a tautology. Both now have a driver.
    ("G4-enforcement-call", "G4 discrimination (routes through enforcement)",
     "are/score/suite.py",
     '        "partition_sums": assert_partition_complete(',
     '        "partition_sums": True or assert_partition_complete(',
     "discrimination() must call the enforcement point, not hardcode the flag"),

    ("P2-analyse-agents", "P2 drifter (co-fire matrix coverage)", "are/cli.py",
     '"drifter", "quitter"]',
     ']',
     "the co-fire matrix must cover the agents the C1/P2 cross-check needs"),

    ("judge-version-provenance", "judge_version reflects client state",
     "are/verify/judge.py",
     '    model = MODELS.get("judge") or "unavailable"',
     '    model = "unavailable"',
     "a status string must not say 'unavailable' while a judge is configured"),

    ("scrub-gateway-key", "scrub fallback covers gateway keys", "are/util.py",
     'sk-[A-Za-z0-9][A-Za-z0-9_\-]{19,}',
     'sk-[A-Za-z0-9]{20,}',
     "the fallback must redact the key formats this repo actually uses"),

    # Found by a coverage sweep after the rehearsal fix: the newest test had no
    # driver, so 14/14 was the OLD set with a 15th fix riding along unverified.
    ("compare-missing-run", "compare: a missing run is a harness problem",
     "are/cli.py",
     '        return CI_UNREPORTABLE if getattr(args, "ci", False) else 0',
     '        return CI_REGRESSION if getattr(args, "ci", False) else 0',
     "an unreadable run must exit 2 (harness), never 1 (agent regressed)"),

    # Took three attempts, and the failures are instructive. (1) Removing ONE of
    # three overlapping patterns left the suite green — correctly, since the
    # others still matched: a mutation that removes redundancy rather than
    # capability proves nothing. (2) `_KEY_PATTERNS = [] or [...]` evaluates to
    # the second list, so it was a silent no-op that LOOKED like a mutation —
    # the same shape as everything else in §7.10, in the tool that exists to
    # catch it. Only the third actually empties the list.
    ("secret-scan-teeth", "repo secret scan can actually fail", "are/util.py",
     "_KEY_PATTERNS = [",
     "_KEY_PATTERNS = []" + LF + "_UNUSED_PATTERNS = [",
     "with no patterns, a clean repo scan is indistinguishable from a repo full of keys"),

    # T1. Both of these detectors fire 0/360 on the frozen set, so until now nothing
    # could tell "works, never exercised" from "cannot fire". The mutations target the
    # DETECTORS, not the fixtures — a fixture that only proves itself is not a control.
    ("T1-timeout-detector", "T1 TIMEOUT positive control", "are/verify/rules.py",
     'out.append(Finding(mode="TIMEOUT", severity=severity_of("TIMEOUT"),',
     'out.append(Finding(mode="BUDGET_EXCEEDED", severity=severity_of("BUDGET_EXCEEDED"),',
     "conflating the wall-clock kill switch with the budget one must fail; they are "
     "separate modes precisely because they catch different loop shapes (§4.4)"),

    ("T1-arg-constraint-detector", "T1 ARG_CONSTRAINT_VIOLATED positive control",
     "are/verify/rules.py",
     '            if not ok:' + LF + '                return Finding(mode="ARG_CONSTRAINT_VIOLATED",',
     '            if not ok and False:' + LF + '                return Finding(mode="ARG_CONSTRAINT_VIOLATED",',
     "a silenced argument check must fail; with no positive control it previously "
     "rendered identically to 'never violated'"),

    # T2. The subject is the GATE, not the arithmetic. Removing it restores exactly the
    # state this closes: a kappa that returns a number no human labelled.
    ("T2-kappa-gate", "T2 cohens_kappa gated behind human labels",
     "are/score/stats.py",
     '    if not human_labels:' + LF + '        raise KappaRequiresHumanLabels(',
     '    if False:' + LF + '        raise KappaRequiresHumanLabels(',
     "an ungated kappa returns judge-vs-judge self-consistency, which reads as "
     "calibration and is not"),

    ("G5-three-state", "G5 not-applicable render", "are/score/suite.py",
     '''        if source == "judge" and not judge_used:
            per_mode[mode] = {
                "state": "NOT APPLICABLE", "source": source, "scenarios": None,
                "reason": "judge not run (--judge is opt-in and off by default)"}
            continue
''',
     '',
     "a zero-applicability category must not render PASS"),
]


def read(rel):
    with open(ROOT / rel, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    return raw.replace(CRLF, LF), (CRLF in raw)


def write(rel, s, crlf):
    with open(ROOT / rel, "w", encoding="utf-8", newline="") as fh:
        fh.write(s.replace(LF, CRLF) if crlf else s)


def suite_red() -> tuple[bool, str]:
    """Run the suite. Returns (went_red, short summary)."""
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"],
                       cwd=str(ROOT), capture_output=True, text=True)
    tail = [ln for ln in r.stdout.strip().splitlines() if ln.strip()][-1:]
    return r.returncode != 0, (tail[0][:110] if tail else "no output")


def main() -> int:
    BAK.mkdir(parents=True, exist_ok=True)
    files = sorted({m[2] for m in MUTATIONS})
    for f in files:
        dest = BAK / f.replace("/", "__")
        shutil.copy2(ROOT / f, dest)

    results = []
    for mid, item, rel, old, new, why in MUTATIONS:
        entry = {"id": mid, "spec_item": item, "file": rel, "why_red": why}
        try:
            s, crlf = read(rel)
            if old not in s:
                entry.update(reverted=False, went_red=None, restored=True,
                             note="PATTERN NOT FOUND — the code moved; revert-check "
                                  "could not be performed, which is itself a finding")
                results.append(entry)
                print(f"  {mid:<26} PATTERN NOT FOUND")
                continue
            write(rel, s.replace(old, new, 1), crlf)
            entry["reverted"] = True
            red, summary = suite_red()
            entry["went_red"] = red
            entry["suite"] = summary
            print(f"  {mid:<26} {'RED  ' if red else 'GREEN'}  {summary}")
        finally:
            shutil.copy2(BAK / rel.replace("/", "__"), ROOT / rel)
            entry["restored"] = True
        results.append(entry)

    # unconditional final restore, then prove the tree is green again
    for f in files:
        shutil.copy2(BAK / f.replace("/", "__"), ROOT / f)
    red_after, summary_after = suite_red()

    verified = [r for r in results if r.get("went_red") is True]
    failed = [r for r in results if r.get("went_red") is False]
    skipped = [r for r in results if r.get("went_red") is None]

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "method": ("Each shipped fix was reverted, the full suite was run, and the "
                   "result recorded. A test that stays green with its subject "
                   "reverted is not evidence."),
        "n_mutations": len(results),
        "n_revert_verified": len(verified),
        "n_stayed_green": len(failed),
        "n_pattern_not_found": len(skipped),
        "tree_restored_and_green": not red_after,
        "suite_after_restore": summary_after,
        "results": results,
        "note": ("Report the revert-verified count, not the test total. A "
                 "revert-checked subset is evidence; a total is a reading."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print()
    print(f"  revert-verified : {len(verified)}/{len(results)}")
    print(f"  stayed GREEN    : {len(failed)}  {[r['id'] for r in failed]}")
    print(f"  not found       : {len(skipped)}  {[r['id'] for r in skipped]}")
    print(f"  tree restored   : {'GREEN' if not red_after else 'STILL RED — INVESTIGATE'}")
    print(f"  wrote {OUT}")
    return 0 if (not failed and not red_after) else 1


if __name__ == "__main__":
    raise SystemExit(main())
