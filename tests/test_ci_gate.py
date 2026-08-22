"""Opt-in CI exit codes (SPEC.md P1).

The brief's framing is "continuous integration for autonomous agents", which
needs an exit code to be instantiable at all. That collides with §7.6 — *the
scorecard advises, it does not gate* — so the rule was narrowed in CLAUDE.md
before this code was written: **the default stays advisory (exit 0)**, and
gating is opt-in via `--ci`.

The exit codes carry the §6.1 three-way distinction rather than collapsing to
pass/fail, because collapsing them is the bug §7.10 exists to prevent:

    0  no meaningful regression        —
    1  regression detected             the AGENT's problem
    2  not reportable                  the HARNESS's problem, never an agent finding

P1 asks for both trigger conditions to be asserted **separately**, and
specifically that `reportable=False` fails the build on its own. That is bug #7
exactly — a verdict rendered from data the platform had already rejected.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from are.cli import CI_OK, CI_REGRESSION, CI_UNREPORTABLE, ci_exit_code

REG = "REGRESSION — significant and larger than the minimum meaningful effect"
IMP = "IMPROVEMENT — significant and larger than the minimum meaningful effect"
NIL = "no significant difference"


# ─────────────────────────────────────────── the two triggers, independently
def test_regression_alone_fails_the_build():
    assert ci_exit_code(REG, True, True) == CI_REGRESSION


def test_unreportable_alone_fails_the_build_even_with_no_regression():
    """The condition P1 calls out by name. A run over the invalid-rate ceiling
    must fail on its own, with no regression anywhere near it — otherwise the
    harness silently passes its own broken data through."""
    assert ci_exit_code(IMP, True, False) == CI_UNREPORTABLE
    assert ci_exit_code(NIL, False, True) == CI_UNREPORTABLE
    assert ci_exit_code(NIL, False, False) == CI_UNREPORTABLE


def test_a_clean_comparison_passes():
    assert ci_exit_code(NIL, True, True) == CI_OK
    assert ci_exit_code(IMP, True, True) == CI_OK


def test_unreportable_outranks_regression_and_is_not_reported_as_one():
    """Order matters. Data the platform rejected cannot support a claim about
    the agent in EITHER direction, so an unreportable run must never surface as
    'regression' — that would be bug #7, blaming the agent for our outage."""
    assert ci_exit_code(REG, True, False) == CI_UNREPORTABLE
    assert ci_exit_code(REG, True, False) != CI_REGRESSION


def test_the_three_codes_are_distinct():
    """A CI job that cannot tell 1 from 2 is misconfigured, and it cannot tell
    them apart if we hand it the same number."""
    assert len({CI_OK, CI_REGRESSION, CI_UNREPORTABLE}) == 3


# ───────────────────────────────────────────────── the default stays advisory
RUNS = Path("runs")
A, B = RUNS / "pushover-v1", RUNS / "pushover-v2"
_have_runs = (A / "verdicts.json").exists() and (B / "verdicts.json").exists()


def _compare(*extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "are.cli", "compare",
                           str(A), str(B), *extra],
                          capture_output=True, text=True)


@pytest.mark.skipif(not _have_runs, reason="pushover v1/v2 runs not on disk")
def test_without_the_flag_the_command_never_gates():
    """§7.6: the tool must not arrive pre-wired to block a build. Asserted on a
    real regression, not just the happy path — reversing the pair is a genuine
    REGRESSION verdict, and it must STILL exit 0 without --ci."""
    r = subprocess.run([sys.executable, "-m", "are.cli", "compare",
                        str(B), str(A)], capture_output=True, text=True)
    assert "REGRESSION" in r.stdout, "expected the reversed pair to be a regression"
    assert r.returncode == 0, "the default must stay advisory even on a regression"
    assert "advisory only" in r.stdout


@pytest.mark.skipif(not _have_runs, reason="pushover v1/v2 runs not on disk")
def test_with_the_flag_a_real_regression_exits_nonzero():
    r = subprocess.run([sys.executable, "-m", "are.cli", "compare",
                        str(B), str(A), "--ci"], capture_output=True, text=True)
    assert r.returncode == CI_REGRESSION
    assert "CI GATE: FAIL" in r.stdout


@pytest.mark.skipif(not _have_runs, reason="pushover v1/v2 runs not on disk")
def test_with_the_flag_an_improvement_still_passes():
    r = _compare("--ci")
    assert r.returncode == CI_OK
    assert "CI GATE: PASS" in r.stdout


@pytest.mark.skipif(not _have_runs, reason="pushover v1/v2 runs not on disk")
def test_a_machine_readable_artifact_is_written():
    """P1(b). CI needs something to parse, not just an exit code."""
    _compare()
    blob = json.loads((B / "comparison.json").read_text(encoding="utf-8"))
    for key in ("baseline", "candidate", "composite_delta", "overall_flips", "verdict"):
        assert key in blob, f"comparison.json is missing {key!r}"


def test_readme_documents_the_gate_and_the_code_distinction():
    """The snippet P1 asks for has to say that 1 and 2 mean different things —
    a job that treats them alike reintroduces the bug the codes prevent."""
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "--ci" in readme
    assert "exit 2" in readme or "code 2" in readme
    assert "uses: actions/checkout" in readme, "P1(c) asks for a CI snippet"
