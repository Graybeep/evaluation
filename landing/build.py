"""Bake real engine output into the landing page (CLAUDE.md §7.7, §7.10).

    python landing/build.py

The landing page is a *view*, never a second implementation: it renders numbers the engine already
produced and never re-derives one. Every figure here is read from an artifact written by
`are.score.compute` / `are.score.regression` — `runs/<id>/scorecard.json`,
`runs/calibration.json`, `runs/<id>/comparison.json`, `runs/history.jsonl` — so the page
cannot drift away from the CLI and disagree about a number.

Two rules from CLAUDE.md are load-bearing here and are implemented, not assumed:

  §7.10  Absence of a signal is never rendered as success. A missing artifact, an
         unreportable run, a NaN composite and a structurally-unmeasurable flake list are
         four *distinct* states, and each one prints as itself. `state` on every block is
         one of OK / MISSING / UNREPORTABLE / NOT_MEASURED — never a bare zero.

  §7.7   Nothing is emitted without n, an interval, and the model/judge version that
         produced it.

Writes `landing/data/site.json` and bakes the same JSON into the
`<script id="are-data">` block of `landing/index.html` so the page also works from
`file://`, where `fetch()` is blocked by CORS.
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
HERE = Path(__file__).resolve().parent
DATA_OUT = HERE / "data" / "site.json"
# Emitted as JS, not JSON, on purpose: every page loads it with a plain <script
# src>, which works over file:// too. A fetch() of a .json sibling does not —
# browsers treat file:// origins as opaque and block it. The pages must open by
# double-click, so the data has to arrive as a script.
JS_OUT = HERE / "assets" / "data.js"
PAGES = ("index.html", "connect.html", "results.html")

# The four §5 calibration agents, in the order the acceptance criterion ranks them.
CALIB = [
    ("clean", "runs/calib-clean", "none (control)"),
    ("confabulator", "runs/calib-confabulator", "answers from priors when a tool errors"),
    ("looper", "runs/calib-looper", "re-searches instead of concluding"),
    ("pushover", "runs/calib-pushover", "complies with authority/urgency framing"),
]
COMPARISON = "runs/demo-pushover-v2/comparison.json"

MISSING: list[str] = []


def load(rel: str):
    """Read a JSON artifact, or record it as MISSING. Never invent a default."""
    p = ROOT / rel
    if not p.exists():
        MISSING.append(rel)
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        MISSING.append(f"{rel} (unreadable: {exc.__class__.__name__})")
        return None


def finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def interval(iv: dict | None) -> dict | None:
    """Carry the interval through with its method and n (§7.7), or None."""
    if not isinstance(iv, dict) or not finite(iv.get("point")):
        return None
    return {
        "point": round(iv["point"], 1),
        "low": round(iv["low"], 1) if finite(iv.get("low")) else None,
        "high": round(iv["high"], 1) if finite(iv.get("high")) else None,
        "method": iv.get("method"),
        "n": iv.get("n"),
        "degenerate": bool(iv.get("degenerate")),
    }


# ─────────────────────────────────────────────────────────── calibration block
def calibration() -> dict:
    cal = load("runs/calibration.json")
    agents, headline = [], None

    for name, rel, defect in CALIB:
        sc = load(f"{rel}/scorecard.json")
        if sc is None:
            agents.append({"agent": name, "defect": defect, "state": "MISSING"})
            continue

        comp = interval(sc.get("composite"))
        if comp is None:
            # A run whose composite is NaN is unreportable, not zero (§6.1).
            agents.append({"agent": name, "defect": defect, "state": "UNREPORTABLE",
                           "invalid_rate": sc.get("invalid_rate")})
            continue

        agents.append({
            "agent": name,
            "agent_version": sc.get("agent_version"),
            "defect": defect,
            "state": "OK" if sc.get("reportable") else "UNREPORTABLE",
            "composite": comp,
            "invalid_rate": round(sc.get("invalid_rate", 0) * 100, 1),
            "reportable": bool(sc.get("reportable")),
            "n_scenarios": sc.get("n_scenarios"),
            "n_runs": sc.get("n_runs"),
            "model_version": sc.get("model_version"),
            "judge_used": bool(sc.get("judge_used")),
            # §8.3: an empty list against a deterministic agent means NOT MEASURED.
            "flaky_measurable": bool(sc.get("flaky_measurable")),
            "flaky_count": len(sc.get("flaky_scenarios") or []),
            "per_category": {
                k: interval(v.get("composite"))
                for k, v in (sc.get("per_category") or {}).items()
            },
            "pressure": {
                k: {"delta": v.get("delta_vs_P0"), "n": v.get("n_scenarios"),
                    "composite": v.get("composite")}
                for k, v in (sc.get("pressure") or {}).items()
            },
            "modes": sorted(
                ({"mode": m, "severity": v.get("severity"),
                  "scenarios_affected": v.get("scenarios_affected"),
                  "rate": interval(v.get("rate"))}
                 for m, v in (sc.get("per_mode") or {}).items()),
                key=lambda d: -(d["scenarios_affected"] or 0),
            )[:6],
        })
        if name == "clean":
            headline = sc

    if cal is None:
        acceptance = {"state": "MISSING"}
    else:
        acceptance = {
            "state": "OK",
            "verdict": cal.get("verdict"),
            "accepted": bool(cal.get("accepted")),
            "checks": [{"check": c["check"], "passed": bool(c["passed"])}
                       for c in cal.get("checks", [])],
        }

    return {"agents": agents, "acceptance": acceptance, "headline": headline}


# ──────────────────────────────────────────────────────────────── trend block
def trend() -> dict:
    """Real composite history. Unreportable runs stay in, flagged — not dropped.

    Silently dropping them would make the series read cleaner than the record actually is,
    which is the §7.10 error in chart form.
    """
    p = RUNS / "history.jsonl"
    if not p.exists():
        MISSING.append("runs/history.jsonl")
        return {"state": "MISSING", "points": []}

    pts = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") != "run":
            continue
        comp = (row.get("composite") or {}).get("point")
        pts.append({
            "agent": row.get("agent_version"),
            "at": row.get("at"),
            "value": round(comp, 1) if finite(comp) else None,
            "invalid_rate": round((row.get("invalid_rate") or 0) * 100, 1),
            "offline": bool(row.get("offline")),
            # value is None  <=>  the run produced no reportable composite
            "state": "OK" if finite(comp) else "UNREPORTABLE",
        })

    if not pts:
        return {"state": "NOT_MEASURED", "points": []}
    return {
        "state": "OK",
        "points": pts[-24:],
        "n_total": len(pts),
        "n_unreportable": sum(1 for p_ in pts if p_["state"] == "UNREPORTABLE"),
    }


# ─────────────────────────────────────────────────────────── regression block
def regression() -> dict:
    cmp_ = load(COMPARISON)
    if cmp_ is None:
        return {"state": "MISSING"}
    flips = cmp_.get("overall_flips") or {}
    return {
        "state": "OK",
        "baseline": cmp_.get("baseline"),
        "candidate": cmp_.get("candidate"),
        "composite_a": cmp_.get("composite_a"),
        "composite_b": cmp_.get("composite_b"),
        "delta": cmp_.get("composite_delta"),
        "meaningful": bool(cmp_.get("meaningful_effect")),
        "n_scenarios": cmp_.get("n_scenarios_compared"),
        "a_pass_b_fail": flips.get("a_pass_b_fail"),
        "a_fail_b_pass": flips.get("a_fail_b_pass"),
        "p_value": cmp_.get("overall_p"),
        "method": flips.get("method"),
        "verdict": cmp_.get("verdict"),
    }


def main() -> int:
    site = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "baked": True,
        "calibration": calibration(),
        "trend": trend(),
        "regression": regression(),
        "missing": MISSING,
    }

    # Provenance stamp: which model actually produced these numbers (§4.5, §7.7).
    models = {a.get("model_version") for a in site["calibration"]["agents"]
              if a.get("model_version")}
    site["model_version"] = sorted(models)[0] if len(models) == 1 else (
        "MIXED: " + ", ".join(sorted(models)) if models else "UNKNOWN")
    site["mode"] = "OFFLINE" if any("offline" in (m or "") for m in models) else "ONLINE"

    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    DATA_OUT.write_text(json.dumps(site, indent=2), encoding="utf-8")

    blob = json.dumps(site, separators=(",", ":"))
    header = (
        "/* GENERATED by landing/build.py - do not edit.",
        "   Engine output, copied verbatim. The site renders this; it never",
        "   re-derives a number from it. Re-run build.py after any new run. */",
    )
    JS_OUT.parent.mkdir(parents=True, exist_ok=True)
    nl = chr(10)
    JS_OUT.parent.mkdir(parents=True, exist_ok=True)
    JS_OUT.write_text(nl.join(header) + nl + "window.ARE_DATA = " + blob + ";" + nl,
                      encoding="utf-8")

    # Every page must actually load the data and the tooltip glossary. A page
    # that silently lost its <script src> would render an empty shell that looks
    # like "no findings" rather than "never loaded" — the §7.10 failure this
    # project keeps re-learning. So assert it here rather than trust it.
    for name in PAGES:
        page = HERE / name
        if not page.exists():
            print(f"ERROR: {name} is missing", file=sys.stderr)
            return 1
        html = page.read_text(encoding="utf-8")
        for need in ("assets/data.js", "assets/tips.js", "assets/common.js"):
            if need not in html:
                print(f"ERROR: {name} does not load {need}", file=sys.stderr)
                return 1

    ok = sum(1 for a in site["calibration"]["agents"] if a["state"] == "OK")
    print(f"baked {JS_OUT.relative_to(ROOT)}  ({len(blob):,} bytes)")
    print(f"  pages       : {len(PAGES)} verified to load data + tips + common")
    print(f"  agents      : {ok}/{len(CALIB)} OK")
    print(f"  trend       : {site['trend']['state']} "
          f"({len(site['trend'].get('points', []))} pts, "
          f"{site['trend'].get('n_unreportable', 0)} unreportable)")
    print(f"  regression  : {site['regression']['state']}")
    print(f"  model       : {site['model_version']}  [{site['mode']}]")
    if MISSING:
        # Not fatal, but never silent: the page will render these as MISSING too.
        print(f"  MISSING     : {', '.join(MISSING)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
