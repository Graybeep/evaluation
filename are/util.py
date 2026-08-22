"""Small shared helpers. `scrub` is a guardrail, not a convenience (CLAUDE.md §7.1)."""
from __future__ import annotations

import os
import re

# API-key shapes. Applied to every string that reaches disk.
# The live-value replacement in scrub() is the primary defence and catches
# whatever ANTHROPIC_API_KEY currently holds. These patterns are the FALLBACK,
# for text scrubbed where that variable is not set — a stored artifact
# re-scrubbed later, a subprocess without the env, or a key that arrived from
# somewhere other than our own config (a gateway echoing it back).
#
# The second pattern was `sk-[A-Za-z0-9]{20,}`, whose character class excludes
# `-` and `_`. That matches Anthropic-style keys and MISSES the gateway keys
# this repo actually uses online (`sk-nry-…`), so the fallback was inert for the
# only key format the online path has ever seen. The test only ever asserted
# `sk-ant-`, so the gap was never exercised — a check that passes because it
# looks in one place (§7.10, instance 17).
_KEY_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9_\-]{19,}"),
    re.compile(r"(?i)(api[_-]?key\"?\s*[:=]\s*\"?)([A-Za-z0-9_\-]{12,})"),
]

REDACTED = "[REDACTED]"


def scrub(obj):
    """Redact secrets from anything on its way to a trace file.

    The runner process holds exactly one secret (the LLM API key). This pass runs before
    every write so it never lands in `runs/`.
    """
    if isinstance(obj, str):
        out = obj
        live = os.environ.get("ANTHROPIC_API_KEY")
        if live and len(live) > 8:
            out = out.replace(live, REDACTED)
        for pat in _KEY_PATTERNS:
            out = pat.sub(lambda m: (m.group(1) + REDACTED) if m.re.groups >= 2 else REDACTED, out)
        return out
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(scrub(v) for v in obj)
    return obj


def truncate(text: str, n: int = 4000) -> str:
    text = str(text)
    return text if len(text) <= n else text[:n] + f"… [+{len(text) - n} chars]"


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def content_digest(path) -> str:
    """SHA-256 over line-ending-normalised bytes.

    Used for the frozen-set manifest (§3.4). Hashing raw bytes made the check fail on
    any clone whose checkout rewrote CRLF to LF — the guarantee is about the scenario
    *content* not changing, not about which platform wrote the file.
    """
    import hashlib
    from pathlib import Path

    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()
