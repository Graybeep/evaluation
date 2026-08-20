"""Calibration agent registry (CLAUDE.md §5).

Four deliberately-defective agents with known failure signatures, plus the neutral
`simple` adapter for evaluating an ordinary agent, plus `pushover@v2` for the paired
regression demo (§14.4).

The platform is not told which agent is which — `build()` takes a name and returns an
adapter, and nothing downstream of the runner reads the name except to label the report.
"""
from __future__ import annotations

from are.calib import clean, confabulator, looper, pushover, quitter
from are.runner.adapter import CallableAdapter, SimpleLoopAdapter
from are.runner.llm import LLMClient

# name -> (version, policy callable, expected-defect note for the report)
REGISTRY = {
    "clean":         (clean.VERSION,        clean.policy,        "none (control)"),
    "looper":        (looper.VERSION,       looper.policy,       "re-searches instead of concluding"),
    "pushover":      (pushover.VERSION,     pushover.policy,     "complies with authority/urgency framing"),
    "confabulator":  (confabulator.VERSION, confabulator.policy, "answers from priors when a tool errors"),
    "pushover_v2":   ("pushover@v2",        pushover.policy_v2,  "partial fix: resists authority, not urgency"),
    # Added AFTER the taxonomy was frozen, to test whether it generalises (§V3).
    "quitter":       (quitter.VERSION,      quitter.policy,      "declares success without performing the change"),
}

SYSTEMS = {
    "clean": clean.SYSTEM,
    "looper": looper.SYSTEM,
    "pushover": pushover.SYSTEM,
    "confabulator": confabulator.SYSTEM,
    "pushover_v2": pushover.SYSTEM_V2,
    "quitter": quitter.SYSTEM,
}


def agent_names() -> list[str]:
    return list(REGISTRY) + ["simple"]


def build(name: str, client: LLMClient | None = None):
    """Return an AgentAdapter for `name`. `client=None` selects the scripted policy."""
    if name == "simple":
        return SimpleLoopAdapter(client=client or LLMClient(role="agent"))
    if name not in REGISTRY:
        raise KeyError(f"unknown agent '{name}'. known: {', '.join(agent_names())}")
    version, policy, _ = REGISTRY[name]
    return CallableAdapter(fn=policy, version=version, client=client)


def defect_note(name: str) -> str:
    return REGISTRY.get(name, ("", None, "n/a"))[2]
