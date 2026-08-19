"""Small shared helpers. `scrub` is a guardrail, not a convenience (CLAUDE.md §7.1)."""
from __future__ import annotations

import os
import re

# API-key shapes. Applied to every string that reaches disk.
_KEY_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
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
