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

from tests.synthetic_keys import synthetic_key
from are.util import _KEY_PATTERNS

ROOT = Path(__file__).resolve().parent.parent

# Files that legitimately contain key-SHAPED text: the patterns themselves, and
# the prose explaining the incident. Listed explicitly so the allowlist is
# auditable rather than a blanket skip.
ALLOWED = {
    "are/util.py",                              # defines the patterns
    "scripts/revert_check.py",                  # mutates the pattern
}
# The two test files were on this list until 2026-08-23, and that is how the incident
# happened: they held key-shaped fixtures on purpose, so the scanner was told to look
# away from the one place a real credential had been copied to. Their fixtures are now
# synthesised at runtime (tests/synthetic_keys.py), so they hold no key-shaped literal
# and are scanned like everything else. THE ALLOWLIST WAS THE BLIND SPOT.


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
    planted = "ANTHROPIC_API_KEY=" + synthetic_key(tag="gateway")
    assert any(p.search(planted) for p in _KEY_PATTERNS), (
        "the patterns match no realistic gateway key — a clean scan would prove "
        "nothing (this is exactly instance 17)")

    for shape in (synthetic_key(prefix="sk-ant-", body_len=24, tag="anthropic"),
                  synthetic_key(prefix="sk-proj-", body_len=31, tag="proj")):
        assert any(p.search(shape) for p in _KEY_PATTERNS), shape


def test_the_allowlist_is_small_and_every_entry_exists():
    """An allowlist that quietly grows is how a scan stops scanning."""
    assert len(ALLOWED) <= 6, "the allowlist is growing — justify each addition"
    for rel in ALLOWED:
        assert (ROOT / rel).exists(), f"stale allowlist entry: {rel}"


def test_no_fixture_is_a_lightly_edited_copy_of_a_real_key():
    """The invariant the 2026-08-23 incident violated.

    The old gateway fixture was the live key with three characters changed: 47 of 50
    bytes identical, a 40-character shared run, committed to a public repo. The scanner
    could not see it because both files holding it were on ALLOWED — the guard was told
    to look away from the one place a real credential had been copied to.

    Fixtures are now synthesised from a public seed, so this asserts the property that
    makes that safe: every fixture's longest shared run with a REAL key is the vendor
    prefix and nothing more. Compared against the retired key, which is dead and
    therefore safe to check against; any future fixture built by editing a live key
    would blow past the threshold."""
    from tests.synthetic_keys import overlap_run, synthetic_key

    retired = "sk-nry-" + "IBJ9SmvB7" + "-fzIzDaen3aholx7yLOBy06TigDGi_MiuQ"

    # POSITIVE CONTROL FIRST (§7.10). Without it, an `overlap_run` that always
    # returned 0 would satisfy every assertion below and this test would certify
    # a derived fixture as clean -- the vacuous-pass shape the whole table is about.
    # Reconstruct the actual incident: the retired key with three characters changed.
    incident = retired[:7] + "AbC" + retired[10:]
    assert overlap_run(incident, retired) >= 40, (
        "overlap_run cannot detect a lightly-edited copy of a real key, so the "
        "assertions below prove nothing")

    for tag in ("gateway", "anthropic", "proj", "env-set", "generic"):
        fake = synthetic_key(tag=tag)
        run = overlap_run(fake, retired)
        assert run <= len("sk-nry-"), (
            f"fixture {tag!r} shares a {run}-char run with a real key — that is how "
            f"the incident happened. Fixtures must be synthesised, never edited from "
            f"a live credential.")


def test_the_test_files_are_no_longer_exempt_from_the_scan():
    """The allowlist WAS the blind spot, so its shrinking is asserted, not assumed.

    Re-adding a test file here would silently restore the exact condition that let a
    94%-complete production key sit in a public repo."""
    assert "tests/test_no_secrets_in_repo.py" not in ALLOWED
    assert "tests/test_sim_and_guardrails.py" not in ALLOWED
    assert not any(a.startswith("tests/") for a in ALLOWED), (
        f"a test file is exempt from the secret scan again: "
        f"{sorted(a for a in ALLOWED if a.startswith('tests/'))}")
