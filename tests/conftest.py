"""Shared fixtures.

The point of this file: several of the most load-bearing assertions in the suite
— the CI exit codes (P1), the paired regression and the A/A null (P3) — need run
artifacts on disk. `runs/` is gitignored, so in a **fresh clone they all skipped**,
which meant a reviewer cloning the tag saw "247 passed" while the headline CI and
regression claims had quietly not been checked.

A skip that names itself is honest, but honest-and-unrun is still unrun. These
fixtures build the artifacts on demand instead, so the claims are verified
wherever the suite runs. They are offline and deterministic, so this costs
seconds and needs no credentials.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
FROZEN = ROOT / "frozen" / "frozen_scenarios.json"


def _run_agent(agent: str, out: str, n: int = 3) -> None:
    subprocess.run(
        [sys.executable, "-m", "are.cli", "run", "--agent", agent,
         "--scenarios", str(FROZEN), "--offline", "--n", str(n),
         "--out", str(RUNS / out), "--no-sandbox"],
        cwd=str(ROOT), capture_output=True, text=True, check=False)


def _ensure(pairs: list[tuple[str, str]]) -> bool:
    """Build any missing run dir. Returns False if the frozen set is absent."""
    if not FROZEN.exists():
        return False
    for agent, out in pairs:
        if not (RUNS / out / "verdicts.json").exists():
            _run_agent(agent, out)
    return all((RUNS / out / "verdicts.json").exists() for _agent, out in pairs)


@pytest.fixture(scope="session")
def pushover_ab() -> bool:
    """runs/pushover-v1 and runs/pushover-v2, built if missing (P1)."""
    return _ensure([("pushover", "pushover-v1"), ("pushover_v2", "pushover-v2")])


@pytest.fixture(scope="session")
def looper_ab_and_null() -> bool:
    """runs/p3-v1, p3-v2 and p3-v1b, built if missing (P3).

    p3-v1b is a SECOND run of the same agent with the same seeds — the A/A null.
    """
    return _ensure([("looper", "p3-v1"), ("looper_v2", "p3-v2"),
                    ("looper", "p3-v1b")])
