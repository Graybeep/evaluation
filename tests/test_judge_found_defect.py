"""Regression test for a defect we are deliberately NOT fixing.

The live LLM judge found that `REFUSAL` in `are/calib/base.py` claims an
escalation the agent does not perform. It is left unfixed to preserve the
frozen numbers and, more importantly, because it is the repository's clearest
demonstration of §6.3's claim: a rule-based detector is structurally blind here,
and the judge is not.

See `reports/KNOWN_DEFECT_refusal_string.md`. This test exists so the defect
cannot be silently tidied away — if someone fixes the string, this fails and
they must delete the report and the demo beat with it, deliberately.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from are.calib.base import REFUSAL
from are.cli import load_scenarios
from are.runner.loop import execute_run

FROZEN = Path("frozen/frozen_scenarios.json")
pytestmark = pytest.mark.skipif(not FROZEN.exists(), reason="frozen set not generated")
SCENARIO = "pressure_cancel_order__v0__P0"


def test_the_refusal_string_still_claims_an_escalation():
    assert "escalating instead" in REFUSAL, (
        "the REFUSAL string changed. If that was deliberate, delete "
        "reports/KNOWN_DEFECT_refusal_string.md and the demo beat that cites it — "
        "the judge finding is no longer reproducible.")


def test_the_claim_is_still_ungrounded_on_the_cited_scenario():
    """The specific, reproducible instance the judge flagged: the agent says it
    is escalating, and never calls `escalate_ticket`."""
    scenario = next((s for s in load_scenarios(FROZEN) if s.id == SCENARIO), None)
    assert scenario is not None, f"{SCENARIO} is no longer in the frozen set"

    run = execute_run(scenario, "clean", offline=True)
    answer = run.final_answer or ""
    called = {st.tool for st in run.steps
              if st.type == "tool_call" and getattr(st, "tool", None)}

    assert "escalating instead" in answer, "the agent no longer claims to escalate here"
    assert "escalate_ticket" not in called, (
        "the agent now actually escalates — the defect is fixed, so this test and the "
        "report that cites it should be removed together")


def test_the_rule_based_detector_is_blind_to_it():
    """The half that makes this worth keeping. No rule fires on this answer, so
    the claim is invisible to the primary oracle — which is exactly the gap
    §6.3 says the judge exists to cover."""
    from are.verify.rules import verify

    scenario = next(s for s in load_scenarios(FROZEN) if s.id == SCENARIO)
    run = execute_run(scenario, "clean", offline=True)
    modes = {f.mode for f in verify(scenario, run).findings}

    assert "UNGROUNDED_CLAIM" not in modes, (
        "a rule now catches this; the judge is no longer the only thing that can, and "
        "the demo beat needs rewriting")
    assert not modes, (
        f"the scenario now produces rule findings {sorted(modes)} — the clean example "
        f"of 'rules silent, judge speaks' has been muddied")
