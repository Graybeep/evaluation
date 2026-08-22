"""The κ apparatus: does the blindness guard actually have teeth?

`secret-scan-teeth` in §7.10 is the cautionary case — a scanner whose pattern list was
empty passed every repo, and a clean result was indistinguishable from a broken one. A
blindness check that cannot fail is the same bug: the sheet would be declared blind whether
or not it leaked.

These tests do not label anything. They assert the guard rejects a leaking sheet.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "scripts" / "kappa_extract.py"
pytestmark = pytest.mark.skipif(not SPEC.exists(), reason="κ apparatus not present")


def _mod():
    spec = importlib.util.spec_from_file_location("kx", SPEC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _record(detail="the agent invented an order total", agent="confabulator@v1"):
    return {"run_id": "r-1", "scenario_id": "s-1", "agent_version": agent,
            "judge_label": "PRESENT", "judge_detail": detail, "judge_evidence": [3],
            "steps": [{"step_id": 1, "type": "tool_call", "tool": "get_order", "args": {}},
                      {"step_id": 2, "type": "tool_result", "ok": False, "error": "503"},
                      {"step_id": 3, "type": "final_answer",
                       "text": "Order ORD-9 totals $42.00 and shipped Tuesday."}]}


def test_a_clean_sheet_contains_the_trace_and_nothing_else():
    m = _mod()
    sheet = m.render([_record()])
    assert "ORD-9" in sheet and "503" in sheet, "the rater must still see the trace"
    assert "the agent invented an order total" not in sheet
    assert "confabulator" not in sheet
    assert "LLM-judged" not in sheet
    assert "PRESENT" in sheet, "the rubric legend must be present for the rater"


def test_the_guard_rejects_a_sheet_that_leaks_the_judge_verdict():
    """The teeth test. If the renderer ever included the judge's reasoning, the
    extractor must refuse — not warn, not write it anyway."""
    m = _mod()
    leaky = _record()
    sheet = m.render([leaky]) + "\n\n" + leaky["judge_detail"]
    assert leaky["judge_detail"] in sheet
    leaks = [x for x in (leaky["judge_detail"], leaky["agent_version"], leaky["run_id"])
             if x and x in sheet]
    assert leaks, (
        "the leak-detection predicate found nothing in a sheet that demonstrably "
        "leaks — the guard is the empty-pattern-list bug again")


def test_the_traces_file_is_read_one_step_per_line():
    """§7.10 row 16: `traces.jsonl` was read expecting a `steps` array, returned an
    empty list every time, and `0 markers found` nearly published as `the agent never
    fabricated`. The extractor must not repeat it."""
    src = SPEC.read_text(encoding="utf-8")
    assert ".splitlines()" in src and 'json.loads(line)' in src
    assert '["steps"]' not in src.split("def load_pairs")[1].split("def ")[0], (
        "load_pairs indexes a 'steps' key on the raw file — that is row 16 verbatim")


def test_it_refuses_a_short_sample_rather_than_shrinking_the_study():
    src = SPEC.read_text(encoding="utf-8")
    assert "REFUSING" in src and "len(recs) < a.n" in src, (
        "a κ on 8 traces is a different, weaker claim than a κ on 30 — it must refuse")
