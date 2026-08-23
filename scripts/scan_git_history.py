# -*- coding: utf-8 -*-
"""Scan every reachable commit for credential-shaped literals.

## Why this exists, when `tests/test_no_secrets_in_repo.py` already scans for keys

That test scans `git ls-files` — the **working tree**. Cleaning a secret out of the tree
does not remove it from history, so a green scan there says "the current checkout is
clean", while a reader takes it to mean "the repo is clean". Those are different claims
and on 2026-08-23 they had different answers: the tree was clean and 21 published commits
still carried a fixture derived from a live gateway key (§7.10 row 20).

That is the §7.10 error in the guard against §7.10 row 20's own incident — the check
asserted a narrower condition than the one people read off it. So the scope is now named
in the output: this script says HISTORY, that test says TREE, and neither is quoted as
the other.

## Output discipline

A secret scanner must never print the secret. Findings are reported as
`prefix… len=N` plus the commits and paths carrying them — enough to locate and purge,
never enough to authenticate. `--full` is deliberately not implemented.

Exit codes follow §7.6's three-way convention rather than a boolean:
    0  scanned, nothing found
    1  scanned, findings          -> the repo's problem
    2  could not scan             -> the harness's problem, never read as "clean"
"""
from __future__ import annotations

import argparse
import collections
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The same shapes `are.util._KEY_PATTERNS` uses, kept here as literals on purpose:
# importing them would make a mutation of that module silently disarm this scanner too,
# and one blind spot shared by both checks is how row 20 happened.
PATTERNS = {
    "anthropic": re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    "gateway/generic": re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9_\-]{19,}"),
}

# Literals that are provably not credentials. Keep this SHORT and justify each entry --
# row 20 was an allowlist entry that was individually reasonable and still hid a real key.
# The rule: a value may be exempt only if it cannot authenticate anywhere, and the reason
# must be a property of the value, never of the file that holds it.
BENIGN_SUBSTRINGS = (
    "sk-ant-abcd",          # obvious placeholder, documentation example
    "sk-ant-super",         # obvious placeholder ("supersecret"), documentation example
)


def _mask(s: str) -> str:
    """Never print more than the vendor prefix. `sk-nry-AbC9…` locates it; it cannot spend it."""
    keep = 11 if len(s) > 14 else max(4, len(s) // 3)
    return f"{s[:keep]}… len={len(s)}"


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True,
                       errors="replace")
    if r.returncode not in (0, 1):        # 1 == "no matches" for git grep
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()[:200]}")
    return r.stdout


def scan(revs: list[str]) -> dict:
    findings: dict[tuple, set] = collections.defaultdict(set)
    for rev in revs:
        # One grep per commit for the cheap anchor, then the real patterns on the hits.
        out = _git("grep", "-nIE", "sk-[A-Za-z0-9]", rev)
        if not out:
            continue
        for line in out.splitlines():
            # `git grep <rev>` yields "<rev>:<path>:<lineno>:<text>"
            parts = line.split(":", 3)
            if len(parts) < 4:
                continue
            path, text = parts[1], parts[3]
            for name, pat in PATTERNS.items():
                for m in pat.findall(text):
                    if any(b in m for b in BENIGN_SUBSTRINGS):
                        continue
                    findings[(name, _mask(m), path)].add(rev[:8])
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true",
                    help="scan every reachable commit (default: HEAD only)")
    args = ap.parse_args()

    try:
        if args.all:
            revs = _git("rev-list", "--all").split()
            scope = f"HISTORY — {len(revs)} commit(s), all refs"
        else:
            revs = ["HEAD"]
            scope = "HEAD only (use --all for history)"
        if not revs:
            print("SCAN FAILED: rev-list returned no commits — a pass here would be vacuous")
            return 2
        findings = scan(revs)
    except Exception as exc:                                  # noqa: BLE001
        print(f"SCAN FAILED ({type(exc).__name__}): {exc}")
        print("Exit 2 = NOT SCANNED. This is not a clean result and must not be read as one.")
        return 2

    print(f"scope: {scope}")
    print(f"patterns: {', '.join(PATTERNS)}")
    if not findings:
        print("\nRESULT: no credential-shaped literals found in the scanned scope.")
        return 0

    print(f"\nRESULT: {len(findings)} credential-shaped literal(s) found. "
          f"Values are masked by design.\n")
    for (name, masked, path), revset in sorted(findings.items(), key=lambda kv: -len(kv[1])):
        rs = sorted(revset)
        shown = ", ".join(rs[:6]) + (f", +{len(rs) - 6} more" if len(rs) > 6 else "")
        print(f"  [{name}] {masked}")
        print(f"      path:    {path}")
        print(f"      commits: {len(rs)}  ({shown})")
    print("\nA literal in history is NOT removed by deleting it from the tree.")
    print("Order of remediation: (1) ROTATE the credential — publication is already done,")
    print("and a rewrite cannot un-publish it; (2) purge history; (3) force-push and ask")
    print("collaborators to re-clone.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
