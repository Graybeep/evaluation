"""No credential may sit in the repository, in any tracked file.

Added after a live API key reached this session's transcript. It never reached
the repo — an exhaustive sweep of commits, blobs, reflog, stash, tags and the
working tree came back clean — but "it did not happen this time" is not a
control, and §7.1's guarantee ("the runner holds exactly one secret, loaded from
env, never logged") deserves one that runs.

This deliberately reuses `are.util._KEY_PATTERNS` — the same patterns `scrub()`
applies before writing a trace. So the repo scan and the trace scrub cannot
drift apart, and the instance-17 fix (the fallback that matched no gateway key)
protects both. If someone narrows those patterns again, this test loses teeth at
exactly the same moment `scrub()` does, and the mutation in
`scripts/revert_check.py` catches it.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from are.util import _KEY_PATTERNS

ROOT = Path(__file__).resolve().parent.parent

# Files that legitimately contain key-SHAPED text: the patterns themselves, and
# the prose explaining the incident. Listed explicitly so the allowlist is
# auditable rather than a blanket skip.
ALLOWED = {
    "are/util.py",                              # defines the patterns
    "tests/test_no_secrets_in_repo.py",         # this file
    "tests/test_sim_and_guardrails.py",         # asserts scrub() on fake keys
    "scripts/revert_check.py",                  # mutates the pattern
}


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=str(ROOT),
                         capture_output=True, text=True).stdout
    return [f for f in out.splitlines() if f.strip()]


def test_no_tracked_file_contains_a_credential():
    """The control. Scans every tracked file with the same patterns `scrub()`
    uses before writing a trace."""
    files = tracked_files()
    assert files, "git ls-files returned nothing — the scan would pass vacuously"

    offenders = []
    for rel in files:
        if rel in ALLOWED:
            continue
        p = ROOT / rel
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except (OSError, ValueError):
            continue
        for pat in _KEY_PATTERNS:
            m = pat.search(text)
            if m:
                offenders.append(f"{rel}: {m.group(0)[:12]}…")
                break

    assert offenders == [], (
        "credential-shaped strings in tracked files:\n  " + "\n  ".join(offenders))


def test_the_scan_can_actually_fail(tmp_path):
    """§7.10, applied to this test. A scanner that matches nothing would pass
    over a repo full of keys and look identical to a clean one — so prove the
    patterns fire on a realistic key before trusting a clean result."""
    planted = "ANTHROPIC_API_KEY=***REMOVED-KEY-FIXTURE-see-tests-synthetic_keys.py***"
    assert any(p.search(planted) for p in _KEY_PATTERNS), (
        "the patterns match no realistic gateway key — a clean scan would prove "
        "nothing (this is exactly instance 17)")

    for shape in ("sk-ant-abcdefgh12345678",
                  "***REMOVED-KEY-FIXTURE-see-tests-synthetic_keys.py***"):
        assert any(p.search(shape) for p in _KEY_PATTERNS), shape


def test_the_allowlist_is_small_and_every_entry_exists():
    """An allowlist that quietly grows is how a scan stops scanning."""
    assert len(ALLOWED) <= 6, "the allowlist is growing — justify each addition"
    for rel in ALLOWED:
        assert (ROOT / rel).exists(), f"stale allowlist entry: {rel}"
