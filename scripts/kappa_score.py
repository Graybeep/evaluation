# -*- coding: utf-8 -*-
"""Join human labels back to judge verdicts and compute kappa. See
reports/KAPPA_STUDY_COMMITMENT.md -- the rubric and reporting rules were fixed first.

    python scripts/kappa_score.py --labels kappa/labels.txt --key kappa/_key.json

`labels.txt` is one label per line, in sheet order: PRESENT / ABSENT / UNSURE.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from are.score.stats import cohens_kappa   # noqa: E402

VALID = {"PRESENT", "ABSENT", "UNSURE"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--rater", required=True, help="who labelled -- recorded in the report")
    ap.add_argument("--out", default="reports/kappa_study.json")
    a = ap.parse_args()

    key = json.loads(Path(a.key).read_text(encoding="utf-8"))
    human = [ln.strip().upper() for ln in
             Path(a.labels).read_text(encoding="utf-8").splitlines() if ln.strip()]
    recs = key["records"]

    if len(human) != len(recs):
        print(f"REFUSING: {len(human)} labels for {len(recs)} traces. A partial sheet is")
        print("not a smaller study; align them or re-extract.")
        return 2
    bad = sorted({x for x in human if x not in VALID})
    if bad:
        print(f"REFUSING: unrecognised labels {bad}. Allowed: {sorted(VALID)}")
        return 2

    pairs = [(h, r["judge_label"]) for h, r in zip(human, recs)]
    kept = [(h, j) for h, j in pairs if h != "UNSURE"]
    excluded = len(pairs) - len(kept)

    if len(kept) < 2:
        print(f"REFUSING: {len(kept)} usable pair(s) after excluding {excluded} UNSURE.")
        return 2

    # human_labels=True is a PROVENANCE claim (are/score/stats.py). --rater records who.
    k = cohens_kappa([h for h, _ in kept], [j for _, j in kept], human_labels=True)

    payload = {
        "mode": "UNGROUNDED_CLAIM", "rater": a.rater, "seed": key["seed"],
        "n_traces": len(pairs), "n_scored": len(kept), "n_excluded_unsure": excluded,
        "kappa": k.as_dict(),
        "disagreements": [{"i": r["i"], "human": h, "judge": j}
                          for (h, j), r in zip(pairs, recs) if h != j],
        "caveat": ("Agreement with ONE rater on ONE mode. Not a validation of the judge "
                   "overall: it covers UNGROUNDED_CLAIM only, and every judge finding "
                   "keeps its 'LLM-judged, unvalidated' tag regardless of this number."),
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"  rater        : {a.rater}")
    print(f"  n            : {len(kept)} scored, {excluded} excluded as UNSURE")
    print(f"  kappa        : {k.kappa:.3f}  [{k.low:.3f}, {k.high:.3f}]")
    print(f"  agreement    : {k.observed_agreement:.3f} observed / {k.expected_agreement:.3f} chance")
    print(f"  reading      : {k.interpretation}")
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
