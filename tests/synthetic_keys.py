"""Structurally realistic fake credentials, synthesised — never edited from a real one.

## Why this module exists

The scrub/scan tests needed a key that *looks* real enough to prove the patterns fire.
The fixture used until 2026-08-23 was the live gateway key with **three characters
changed**: 47 of 50 bytes identical, a 40-character shared run. It sat in two tracked
test files on a public repo, so anyone with a clone had 94% of a production credential
and the vendor prefix telling them where to spend it.

The scanner could not catch it. Both files were on its own `ALLOWED` list — they had to
be, because they contain key-shaped text on purpose. **The guard's blind spot was
exactly the place the secret was kept.**

This is §7.10 lesson (b) in its most literal form. That lesson says a test derived from
the implementer's model can only catch deviations *from* that model; here the fixture was
not derived from a mental model of a key, it was derived from **the key itself**. Row 17
was already about this regex and this key format, and the fix for row 17 left the sample
it had been built from sitting in the tests.

## The fix, and why it beats encrypting the fixture

Encrypting a test fixture means shipping the ciphertext *and* the means to decrypt it, so
the plaintext is still recoverable from the repo. Synthesising removes the secret instead
of hiding it: **there is no key-shaped literal in any tracked file to leak.**

Deterministic, so tests stay reproducible; derived from a fixed public seed string, so
the output demonstrably cannot encode a real credential.
"""
from __future__ import annotations

import hashlib
import string

_ALPHABET = string.ascii_letters + string.digits + "-_"
_SEED_NOTE = "ARE-SYNTHETIC-FIXTURE-v1-not-derived-from-any-real-credential"


def synthetic_key(prefix: str = "sk-nry-", body_len: int = 43, tag: str = "default") -> str:
    """A fake key with the right SHAPE and no relationship to a real one.

    The body is a hash of a public constant. Two properties matter and both are
    asserted in `tests/test_no_secrets_in_repo.py`:
      * it matches the scrub/scan patterns, so the teeth-tests still have teeth;
      * it appears in no tracked file as a literal, so it cannot be the next incident.
    """
    out, block, i = [], b"", 0
    while len(out) < body_len:
        block = hashlib.sha256(f"{_SEED_NOTE}|{tag}|{i}".encode()).digest()
        out.extend(_ALPHABET[b % len(_ALPHABET)] for b in block)
        i += 1
    return prefix + "".join(out[:body_len])


def overlap_run(a: str, b: str) -> int:
    """Longest substring of `a` that also occurs in `b`. Used to prove a fixture is
    not a lightly-edited copy of something real."""
    best = 0
    for i in range(len(a)):
        for j in range(i + 1, len(a) + 1):
            if a[i:j] in b:
                best = max(best, j - i)
            else:
                break
    return best
