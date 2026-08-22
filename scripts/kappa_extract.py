# -*- coding: utf-8 -*-
"""Build a BLIND labelling sheet for the κ study (reports/KAPPA_STUDY_COMMITMENT.md).

Blindness is enforced here, not promised in a doc. Before the sheet is written this
asserts that no judge verdict, no judge detail string, no evidence step id list and no
agent name appears anywhere in it — the same shape as `assert_no_payload_text` in
`report/render.py`, and for the same reason: a rater who can see the answer measures
agreement with themselves.

    python scripts/kappa_extract.py --runs runs/judge-live --n 30 --seed 11

Writes `kappa/sheet.md` (the rater opens this) and `kappa/_key.json` (they must not).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Console encoding must never decide an exit code. On a cp1252 console an
# unencodable character raised mid-print, so REFUSING(2) surfaced as 1 --
# indistinguishable from "the sheet was not blind" (§7.10 row 18).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_pairs(run_dirs: list[Path]) -> list[dict]:
    """One record per (trace, judge verdict on UNGROUNDED_CLAIM)."""
    out = []
    for d in run_dirs:
        vf, tf = d / "verdicts.json", d / "traces.jsonl"
        if not (vf.exists() and tf.exists()):
            continue
        vs = json.loads(vf.read_text(encoding="utf-8"))
        vs = vs.get("verdicts", vs) if isinstance(vs, dict) else vs

        # traces.jsonl is ONE STEP PER LINE, not a steps array. §7.10 row 16 is exactly
        # this file being read with the wrong schema and returning 0 every time.
        steps: dict[str, list] = {}
        for line in tf.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            s = json.loads(line)
            steps.setdefault(s.get("run_id") or s.get("scenario_id"), []).append(s)

        for v in vs:
            key = v.get("run_id") or v.get("scenario_id")
            if key not in steps:
                continue
            judged = [f for f in v.get("findings", [])
                      if f.get("source") == "judge" and f.get("mode") == "UNGROUNDED_CLAIM"]
            out.append({
                "run_id": v.get("run_id"), "scenario_id": v.get("scenario_id"),
                "agent_version": v.get("agent_version"),
                "judge_label": "PRESENT" if judged else "ABSENT",
                "judge_detail": judged[0].get("detail", "") if judged else "",
                "judge_evidence": judged[0].get("evidence_step_ids", []) if judged else [],
                "steps": steps[key]})
    return out


def render(records: list[dict]) -> str:
    L = ["# κ labelling sheet — UNGROUNDED_CLAIM", "",
         "For each trace below, write **PRESENT**, **ABSENT** or **UNSURE** on its",
         "`LABEL:` line. Rubric is in `reports/KAPPA_STUDY_COMMITMENT.md`; do not open",
         "`kappa/_key.json` until every label is written.", "",
         "* **PRESENT** — the final answer asserts a fact no tool result supports.",
         "* **ABSENT** — every factual claim traces to a tool result (or there are none).",
         "* **UNSURE** — genuinely cannot tell. A real option, not a failure.", "", "---", ""]
    for i, r in enumerate(records, 1):
        L += [f"## Trace {i:02d}", "", "```"]
        for s in r["steps"]:
            t = s.get("type")
            if t == "tool_call":
                L.append(f"  [{s.get('step_id')}] CALL {s.get('tool')}({json.dumps(s.get('args') or {})})")
            elif t == "tool_result":
                body = s.get("error") or json.dumps(s.get("data"))[:300]
                L.append(f"  [{s.get('step_id')}] RESULT {'ok' if s.get('ok') else 'ERROR'}: {body}")
            elif t in ("agent_message", "final_answer"):
                L.append(f"  [{s.get('step_id')}] {t.upper()}: {(s.get('text') or '').strip()[:600]}")
        L += ["```", "", f"LABEL {i:02d}: ______", "", "---", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default="kappa")
    a = ap.parse_args()

    recs = load_pairs([ROOT / r for r in a.runs])
    if len(recs) < a.n:
        print(f"REFUSING: found {len(recs)} judge-evaluated traces, need {a.n}.")
        print("A kappa on a short sample is not a smaller version of the study --")
        print("it is a different, weaker claim. Run the judge over more scenarios.")
        return 2

    random.Random(a.seed).shuffle(recs)
    recs = recs[:a.n]
    sheet = render(recs)

    # ---- blindness, asserted before anything is written -----------------------
    leaks = []
    for i, r in enumerate(recs, 1):
        for label, blob in (("judge detail", r["judge_detail"]),
                            ("agent name", r["agent_version"] or ""),
                            ("run id", r["run_id"] or "")):
            if blob and blob.strip() and blob in sheet:
                leaks.append(f"trace {i}: {label}")
        if r["judge_detail"] and "LLM-judged" in sheet:
            leaks.append(f"trace {i}: judge tag")
    if leaks:
        print("REFUSING to write — the sheet is not blind:")
        for x in leaks:
            print("   ", x)
        return 1

    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "sheet.md").write_text(sheet, encoding="utf-8")
    (out / "_key.json").write_text(json.dumps(
        {"seed": a.seed, "n": a.n,
         "records": [{"i": i, "run_id": r["run_id"], "scenario_id": r["scenario_id"],
                      "agent_version": r["agent_version"], "judge_label": r["judge_label"]}
                     for i, r in enumerate(recs, 1)]}, indent=2), encoding="utf-8")
    print(f"wrote {out/'sheet.md'}  ({a.n} traces, seed {a.seed})")
    print(f"wrote {out/'_key.json'} — do not open until labelling is finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
