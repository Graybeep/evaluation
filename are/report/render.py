"""HTML report (CLAUDE.md §7.4, §7.7, Day 3).

Reporting rules this file enforces mechanically, not by convention:

  * `n`, `invalid_rate`, model version, judge version and CI width appear on every score.
  * No point estimate is shown without an interval.
  * Judge-derived findings are marked "LLM-judged, unvalidated" every time they appear.
  * Pressure payloads are referenced **by id and category only** — never their text (§7.4).
    `assert_no_payload_text()` checks the rendered HTML and raises if a payload string
    leaked, including via a scenario instruction, which is where it would actually happen.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from are.probes import corpus
from are.schema.scenario import ScenarioSet
from are.schema.trace import RunResult
from are.schema.verdict import Verdict
from are.score.compute import compute
from are.util import pct

JUDGE_MODES = ("UNGROUNDED_CLAIM", "OVERCONFIDENT_SUMMARY")
MAX_DRILLDOWN = 12


def _esc(x) -> str:
    return html.escape(str(x), quote=True)


def _redact_payloads(text: str) -> str:
    """Replace any payload text that made it into an instruction with its id (§7.4)."""
    out = text
    for p in corpus.load_corpus():
        if p.text and p.text in out:
            out = out.replace(p.text, f"[pressure payload {p.id} / {p.category} — "
                                      f"text withheld, see probes/README.md]")
    return out


def assert_no_payload_text(html_doc: str) -> None:
    leaked = [p.id for p in corpus.load_corpus()
              if len(p.text) > 30 and p.text[:60] in html_doc]
    if leaked:
        raise AssertionError(f"payload text leaked into the report: {leaked} (§7.4)")


# ------------------------------------------------------------------ loading
def _load(run_dir: Path):
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    card = run_dir / "scorecard.json"
    meta["_defect_coverage"] = (json.loads(card.read_text(encoding="utf-8")).get("defect_coverage")
                                if card.exists() else None)
    verdicts = [Verdict(**v) for v in json.loads((run_dir / "verdicts.json").read_text(encoding="utf-8"))]
    scenarios = ScenarioSet(**json.loads((run_dir / "scenarios.json").read_text(encoding="utf-8"))).scenarios
    runs = []
    rp = run_dir / "runs.jsonl"
    if rp.exists():
        runs = [RunResult.model_validate_json(line) for line in
                rp.read_text(encoding="utf-8").splitlines() if line.strip()]
    return meta, verdicts, scenarios, runs


# ------------------------------------------------------------------ sections
def _interval(d: dict, as_pct=False) -> str:
    fmt = (lambda v: pct(v)) if as_pct else (lambda v: f"{v:.1f}")
    return (f"<span class='pt'>{fmt(d['point'])}</span>"
            f"<span class='ci'>[{fmt(d['low'])}, {fmt(d['high'])}] 95% CI, n={d['n']}</span>")


def _mode_chip(meta) -> str:
    """Repeated on every section header. A reader who scrolls past the top of the page
    must not lose the single most important qualifier on every number below."""
    offline = meta.get("offline")
    label = "OFFLINE — scripted policy" if offline else "ONLINE — live model"
    return f"<span class='modechip {'off' if offline else 'on'}'>{label}</span>"


def _mode_bar(meta) -> str:
    offline = meta.get("offline")
    if offline:
        return ("<div class='modebar off'>OFFLINE RUN — the agent under test was a "
                "<b>scripted calibration policy</b>, not a model. These numbers say the "
                "harness works; they say nothing about real model behaviour.</div>")
    return ("<div class='modebar on'>ONLINE RUN — live model: "
            f"<b>{_esc(meta.get('model_version'))}</b>. Sandbox L3 is degraded on this path "
            "(see the sandbox section).</div>")


def _headline(sc, meta) -> str:
    banner = ""
    if not sc.reportable:
        banner = ("<div class='alert'>invalid_rate exceeds 5% — <b>this run is not "
                  "reportable</b>. Fix the harness before quoting any number here (§6.1).</div>")
    if meta.get("offline"):
        banner += ("<div class='warn'>Offline mode: the agent under test was the "
                   "<b>scripted calibration policy</b>, not a model. Useful for showing the "
                   "platform works end to end; the headline numbers should come from an "
                   "LLM-backed run.</div>")
    if not meta.get("frozen_set"):
        banner += ("<div class='warn'>Not the frozen benchmark set — headline numbers are "
                   "reported on <code>frozen/</code> only (§3.4).</div>")
    return f"""
{banner}
<div class='grid'>
  <div class='card'><h3>composite</h3><div class='big'>{sc.composite.point:.1f}</div>
    <div class='ci'>[{sc.composite.low:.1f}, {sc.composite.high:.1f}] 95% CI
    ({sc.composite.method}, n={sc.composite.n} scenarios)</div>
    {"<div class='ci degen'><b>degenerate by construction</b> — all "
     f"{sc.composite.n} scenarios share one penalty value. Zero width means zero variance "
     "across scenarios, not a precise estimate.</div>" if sc.composite.degenerate else ""}
    </div>
  <div class='card'><h3>pass rate</h3><div class='big'>{pct(sc.pass_rate.point)}</div>
    <div class='ci'>[{pct(sc.pass_rate.low)}, {pct(sc.pass_rate.high)}]</div></div>
  <div class='card'><h3>invalid rate</h3><div class='big'>{pct(sc.invalid_rate)}</div>
    <div class='ci'>{'within' if sc.reportable else 'ABOVE'} the 5% ceiling (§6.1)</div></div>
  <div class='card'><h3>scale</h3><div class='big'>{sc.n_scenarios}</div>
    <div class='ci'>scenarios x {meta.get('n_repeats')} repeats = {sc.n_runs} runs</div></div>
</div>
<table class='meta'>
  <tr><th>agent</th><td>{_esc(sc.agent_version)}</td>
      <th>injected defect</th><td>{_esc(meta.get('defect_note', 'n/a'))}</td></tr>
  <tr><th>model (pinned)</th><td>{_esc(sc.model_version)}</td>
      <th>judge</th><td>{_esc(sc.judge_version or 'not used')}</td></tr>
  <tr><th>scenario set</th><td>{_esc(meta.get('scenario_set'))}</td>
      <th>cache mode</th><td>{_esc(sc.cache_mode)} ({'replay = debugging only' if sc.cache_mode == 'replay' else 'statistics-safe'})</td></tr>
  <tr><th>provider retries</th><td>{sc.provider_fault_retries} 5xx retried across
      {sc.runs_needing_retry} run(s) — counted separately from invalid_rate (§Y2)</td>
      <th>&nbsp;</th><td>&nbsp;</td></tr>
  <tr><th>run id</th><td>{_esc(meta.get('run_id'))}</td>
      <th>wall clock</th><td>{_esc(meta.get('wall_clock_s'))}s</td></tr>
</table>"""


def _categories(sc, chip='') -> str:
    rows = "".join(
        f"<tr><td>{_esc(cat)}</td><td>{_interval(d['composite'])}</td>"
        f"<td>{_interval(d['pass_rate'], as_pct=True)}</td><td>{d['n_scenarios']}</td></tr>"
        for cat, d in sorted(sc.per_category.items()))
    return f"""<h2>Per category {chip}</h2>
<p class='note'>The composite alone hides an agent that is safe but useless (§8.1).</p>
<table><tr><th>category</th><th>composite</th><th>pass rate</th><th>n scenarios</th></tr>
{rows}</table>"""


def _modes(sc, chip='') -> str:
    rows = []
    for mode, d in sorted(sc.per_mode.items(), key=lambda kv: -kv[1]["rate"]["point"]):
        tag = ("<span class='judged'>LLM-judged, unvalidated</span>"
               if mode in JUDGE_MODES else "")
        rows.append(f"<tr><td>{_esc(mode)} {tag}</td><td class='sev-{d['severity']}'>"
                    f"{d['severity']}</td><td>{_interval(d['rate'], as_pct=True)}</td>"
                    f"<td>{d['scenarios_affected']}</td></tr>")
    if not rows:
        rows = ["<tr><td colspan=4>no failure modes detected</td></tr>"]
    return f"""<h2>Failure modes {chip}</h2>
<table><tr><th>mode</th><th>severity</th><th>rate across scenarios</th><th>scenarios affected</th></tr>
{''.join(rows)}</table>"""


def _pressure(sc, chip='') -> str:
    if len(sc.pressure) < 2:
        return ""
    def _delta(d) -> str:
        return "—" if d["delta_vs_P0"] is None else f"{d['delta_vs_P0']:+.1f}"

    rows = "".join(
        f"<tr><td>{lvl}</td><td>{d['composite']:.1f}</td><td>{_delta(d)}</td>"
        f"<td>{pct(d['pass_rate'])}</td><td>{d['n_scenarios']}</td></tr>"
        for lvl, d in sorted(sc.pressure.items()))
    return f"""<h2>Guardrail pressure (P0–P5) {chip}</h2>
<p class='note'>Same scenario body, same entities, same seeds — only the framing changes.
The number that matters is the <b>delta against the P0 control</b>, not the absolute
score. Payloads are referenced by id and category only (§7.4).</p>
<table><tr><th>level</th><th>composite</th><th>delta vs P0</th><th>pass rate</th><th>n</th></tr>
{rows}</table>"""


def _variance(sc, chip='') -> str:
    """Two variance axes, reported side by side and never described as each other (§8.3)."""
    if sc.flaky_measurable:
        flaky_cell = (f"{len(sc.flaky)} scenario(s): " + ", ".join(_esc(s) for s in sc.flaky[:6])
                      if sc.flaky else "none found")
    else:
        flaky_cell = ("<b>not measurable in this run</b> — the agent under test is "
                      "deterministic, or N=1. An empty list here means <i>not measured</i>, "
                      "not <i>none found</i>.")
    if sc.variant_sensitive:
        rows = "".join(
            f"<tr><td>{_esc(g['template_id'])}</td><td>{_esc(g['pressure_level'])}</td>"
            f"<td>{g['passing']} pass / {g['failing']} fail of {g['n_variants']}</td>"
            f"<td>{g['spread']:.2f}</td></tr>" for g in sc.variant_sensitive)
        para = (f"<table><tr><th>template</th><th>level</th><th>variants</th>"
                f"<th>spread</th></tr>{rows}</table>")
    else:
        para = "<p class='note'>No template flipped outcome across its sibling variants.</p>"

    return f"""<h2>Variance (§8.3) {chip}</h2>
<p class='note'>Two different axes. They are measured separately and neither number is ever
reported as the other.</p>
<table class='meta'>
 <tr><th>flake quarantine<br><span class='ci'>N repeats of one identical instruction —
     decode nondeterminism</span></th><td>{flaky_cell}</td></tr>
</table>
<h3 style='margin-top:14px'>variant sensitivity</h3>
<p class='note'>Sibling variants of one template at one pressure level. Audited against the
frozen set, variants differ in <code>world_state</code>, <code>seed</code>,
<code>faults</code>, <code>assertions</code> <b>and</b> <code>pressure_tags</code> — not
only in wording. So a flagged group means "not robust across its variants"; it is
<b>not</b> a paraphrase-sensitivity measurement and is not labelled as one.</p>
{para}"""


def _defect_coverage(cov: dict | None, chip: str = "") -> str:
    """Detection reported on its own denominator, with an interval (§U3)."""
    if not cov:
        return ""
    ci = cov.get("detection_ci") or {}
    rate = ("n/a" if cov.get("detection_rate") is None
            else f"{cov['detection_rate']:.0%}")
    interval = (f" <span class='ci'>95% CI [{ci['low']:.2f}, {ci['high']:.2f}] "
                f"(Wilson, n={ci['n']} scenarios)</span>" if ci else "")
    return f"""<h2>Injected-defect coverage — {_esc(cov['marker'])} {chip}</h2>
<p class='note'>Unit: {_esc(cov.get('unit', 'scenario'))}. The denominator is the scenarios
where the defect actually fired and a rule could see it — not the whole suite. A bare
"100%" would claim a certainty a sample of {ci.get('n', '?')} does not support.</p>
<table class='meta'>
 <tr><th>declared trigger</th><td>{_esc(cov['trigger'])}</td></tr>
 <tr><th>detected</th><td><b>{cov['scenarios_detected']}/{cov['scenarios_detectable']}
     = {rate}</b>{interval}</td></tr>
 <tr><th>escaped</th><td>{cov['scenarios_escaped']} — fired, a rule could have seen it,
     still passed. This is the number that matters.</td></tr>
 <tr><th>blind spot</th><td>{cov['scenarios_blind_spot']} — fired, but the scenario has no
     observable state change for a rule to check; only the (opt-in, uncalibrated) judge
     could see these.</td></tr>
 <tr><th>never fired</th><td>{cov['scenarios_gated_before_firing']} gated by the agent's own
     safety path (it refused or asked first), {cov['scenarios_no_trigger']} never handed the
     trigger. <b>A coverage limit of the scenario set, not a property of the
     detector.</b></td></tr>
 <tr><th>fired off-trigger</th><td>{cov['scenarios_fired_without_opportunity']} — a non-zero
     value here means the agent's defect is firing for the wrong reason, which attribution
     will not show.</td></tr>
</table>"""


def _drilldown(verdicts, scenarios, runs) -> str:
    by_scenario = {s.id: s for s in scenarios}
    by_run = {r.run_id: r for r in runs}
    # One entry per scenario. Repeats of a deterministic agent are identical, so without
    # this the drill-down spends all its slots re-printing the same four failures.
    failing, seen_scenarios = [], set()
    for v in verdicts:
        if v.outcome != "FAIL" or v.scenario_id in seen_scenarios:
            continue
        seen_scenarios.add(v.scenario_id)
        failing.append(v)
    failing.sort(key=lambda v: (0 if any(f.severity == "CRITICAL" for f in v.findings) else 1))
    blocks = []
    for v in failing[:MAX_DRILLDOWN]:
        s = by_scenario.get(v.scenario_id)
        r = by_run.get(v.run_id)
        findings = "".join(
            f"<li class='sev-{f.severity}'><b>{_esc(f.mode)}</b> "
            f"({_esc(f.severity)}{', LLM-judged, unvalidated' if f.source == 'judge' else ''})"
            f" — {_esc(f.detail)}"
            f"{f' <span class=steps>steps {f.evidence_step_ids}</span>' if f.evidence_step_ids else ''}</li>"
            for f in v.findings)
        steps = ""
        if r:
            lines = []
            for st in r.steps:
                if st.type == "tool_call":
                    lines.append(f"[{st.step_id}] CALL {st.tool}({json.dumps(st.args, default=str)})")
                elif st.type == "tool_result":
                    body = f"ERROR {st.error}" if not st.ok else json.dumps(st.data, default=str)[:220]
                    lines.append(f"[{st.step_id}] -> {body}")
                elif st.type in ("agent_message", "final_answer", "limit_trip", "harness_error"):
                    lines.append(f"[{st.step_id}] {st.type.upper()}: {(st.text or '')[:300]}")
            steps = "<pre>" + _esc(_redact_payloads("\n".join(lines[:40]))) + "</pre>"
        tags = ", ".join(v.pressure_tags) or "—"
        blocks.append(f"""<details><summary><b>{_esc(v.scenario_id)}</b>
  <span class='pill'>{_esc(v.category)}</span>
  <span class='pill'>{_esc(v.pressure_level)}</span>
  <span class='pill'>{len(v.findings)} finding(s)</span></summary>
  <p class='instr'><b>instruction:</b> {_esc(_redact_payloads(s.instruction if s else ''))}</p>
  <p class='note'>pressure payload: {_esc(tags)} (text withheld — see probes/README.md)</p>
  <ul>{findings}</ul>{steps}</details>""")
    if not blocks:
        blocks = ["<p>No failing runs.</p>"]
    return (f"<h2>Failing runs — trace drill-down</h2>"
            f"<p class='note'>Showing up to {MAX_DRILLDOWN} distinct failing scenarios, "
            f"CRITICAL first (one entry per scenario, not per repeat). "
            f"Full traces: <code>traces.jsonl</code>.</p>{''.join(blocks)}")


def _comparison(compare_dir: Path | None, run_dir: Path) -> str:
    path = None
    for cand in ((compare_dir / "comparison.json") if compare_dir else None,
                 run_dir / "comparison.json"):
        if cand and cand.exists():
            path = cand
            break
    if not path:
        return ""
    c = json.loads(path.read_text(encoding="utf-8"))
    rows = "".join(
        f"<tr><td>{_esc(t['category'])}</td><td>{t['n_scenarios']}</td>"
        f"<td>{t['a_pass']} → {t['b_pass']}</td><td>-{t['b_flips']} / +{t['c_flips']}</td>"
        f"<td>{t['p_value']:.4f}</td><td>{'yes' if t['significant_bh'] else 'no'}</td></tr>"
        for t in c["per_category"])
    f = c["overall_flips"]
    return f"""<h2>Paired regression — {_esc(c['baseline'])} → {_esc(c['candidate'])}</h2>
<p class='note'>Identical scenario set, seeds and world states. McNemar on pass↔fail flips;
per-category tests corrected with Benjamini–Hochberg at q=0.10. Minimum meaningful effect:
3 composite points (§8.2).</p>
<p><b>composite {c['composite_a']:.1f} → {c['composite_b']:.1f}
({c['composite_delta']:+.1f})</b> —
flips pass→fail {f['a_pass_b_fail']}, fail→pass {f['a_fail_b_pass']},
McNemar p={f['p_value']:.4f}</p>
<p class='verdict'>{_esc(c['verdict'])}</p>
<table><tr><th>category</th><th>n</th><th>pass</th><th>flips</th><th>p</th><th>significant (BH)</th></tr>
{rows}</table>"""


def _sandbox(meta) -> str:
    sb = meta.get("sandbox", {})
    rows = "".join(f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>" for k, v in sb.items())
    return f"<h2>Sandbox in effect for this run (§7.9)</h2><table class='meta'>{rows}</table>"


CSS = """
:root{--fg:#1a1c1f;--mut:#6b7280;--bd:#e3e6ea;--bg:#fff;--acc:#1f6feb;
      --crit:#b91c1c;--maj:#b45309;--min:#4b5563;--ok:#166534;}
*{box-sizing:border-box}
body{font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,sans-serif;color:var(--fg);
     background:var(--bg);margin:0;padding:32px;max-width:1080px}
h1{font-size:24px;margin:0 0 4px} h2{font-size:18px;margin:32px 0 8px;
   border-bottom:1px solid var(--bd);padding-bottom:6px}
h3{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:0 0 6px}
.sub{color:var(--mut);margin:0 0 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:16px 0}
.card{border:1px solid var(--bd);border-radius:8px;padding:14px}
.big{font-size:30px;font-weight:600;line-height:1.1}
.ci{color:var(--mut);font-size:12px;display:block;margin-top:2px}
.pt{font-weight:600;margin-right:6px}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:14px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--bd);vertical-align:top}
th{color:var(--mut);font-weight:600}
table.meta th{width:150px}
.note{color:var(--mut);font-size:13px;margin:4px 0 10px}
.alert{background:#fef2f2;border:1px solid #fecaca;color:#7f1d1d;padding:12px;border-radius:8px;margin:12px 0}
.warn{background:#fffbeb;border:1px solid #fde68a;color:#78350f;padding:12px;border-radius:8px;margin:12px 0}
.judged{background:#eef2ff;color:#3730a3;border:1px solid #c7d2fe;border-radius:999px;
        padding:1px 8px;font-size:11px;margin-left:6px;white-space:nowrap}
.pill{background:#f3f4f6;border-radius:999px;padding:1px 9px;font-size:12px;color:var(--mut);margin-left:6px}
.sev-CRITICAL{color:var(--crit)} .sev-MAJOR{color:var(--maj)} .sev-MINOR{color:var(--min)}
details{border:1px solid var(--bd);border-radius:8px;padding:10px 14px;margin:8px 0}
summary{cursor:pointer}
pre{background:#f8fafc;border:1px solid var(--bd);border-radius:6px;padding:10px;
    overflow-x:auto;font-size:12px;line-height:1.45}
.instr{background:#f8fafc;padding:8px 10px;border-radius:6px}
.steps{color:var(--mut);font-size:12px}
.verdict{font-weight:600}
.degen{color:#78350f;background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:5px 7px;margin-top:6px;display:block}
.modebar{position:sticky;top:0;z-index:9;margin:-32px -32px 18px;padding:10px 32px;
         font-size:13px;border-bottom:1px solid var(--bd)}
.modebar.off{background:#fffbeb;color:#78350f}
.modebar.on{background:#ecfdf5;color:#065f46}
.modechip{font-size:11px;font-weight:600;border-radius:999px;padding:2px 9px;margin-left:8px;
          vertical-align:middle;letter-spacing:.02em}
.modechip.off{background:#fef3c7;color:#78350f;border:1px solid #fde68a}
.modechip.on{background:#d1fae5;color:#065f46;border:1px solid #a7f3d0}
footer{margin-top:40px;color:var(--mut);font-size:12px;border-top:1px solid var(--bd);padding-top:12px}
"""


def render_report(run_dir: Path, compare_dir: Path | None = None,
                  out_name: str = "report.html") -> Path:
    run_dir = Path(run_dir)
    meta, verdicts, scenarios, runs = _load(run_dir)
    sc = compute(verdicts, agent_version=meta["agent_version"],
                 model_version=meta["model_version"],
                 judge_version=meta.get("judge", {}).get("version"),
                 judge_used=meta.get("judge", {}).get("used", False),
                 cache_mode=meta.get("cache_mode", "off"))

    chip = _mode_chip(meta)
    notes = "".join(f"<li>{_esc(n)}</li>" for n in sc.notes)
    flaky = _variance(sc, chip)

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ARE report — {_esc(sc.agent_version)}</title><style>{CSS}</style></head><body>
{_mode_bar(meta)}
<h1>Agent Reliability Engine — scorecard</h1>
<p class='sub'>{_esc(sc.agent_version)} on {_esc(meta.get('scenario_set'))} ·
generated {_esc(meta.get('started_at'))}</p>
{_headline(sc, meta)}
{_categories(sc, chip)}
{_modes(sc, chip)}
{_pressure(sc, chip)}
{_defect_coverage(meta.get('_defect_coverage'), chip)}
{_comparison(compare_dir, run_dir)}
{flaky}
{_drilldown(verdicts, scenarios, runs)}
{_sandbox(meta)}
<h2>Read this before quoting a number</h2>
<ul class='note'>
<li>The scorecard <b>advises; it does not gate</b> (§7.6). A hard automated gate on this
score invites optimising the eval instead of the agent.</li>
<li>Findings marked <span class='judged'>LLM-judged, unvalidated</span> come from a
secondary LLM judge with <b>no human-labelled agreement study</b>. Treat as advisory (§11.1).</li>
<li>Absolute scores are not comparable across agents with different toolsets. Only paired,
same-suite comparisons are meaningful (§11.5).</li>
<li>Scenarios come from hand-authored templates; coverage is bounded by template
imagination, not by the real failure distribution (§11.2).</li>
{notes}
</ul>
<footer>Agent Reliability Engine · property-based testing for LLM agents ·
verdicts computed from traces and final world state, not inferred ·
pressure payloads referenced by id only (§7.4)</footer>
</body></html>"""

    assert_no_payload_text(doc)
    out = run_dir / out_name
    out.write_text(doc, encoding="utf-8")
    return out
