"""Tool registry loader + tool specs handed to agents (CLAUDE.md §2)."""
from __future__ import annotations

import functools
import warnings
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

REGISTRY_PATH = Path(__file__).with_name("registry.yaml")

TIER_ORDER = {"READ": 0, "MUTATING": 1, "IRREVERSIBLE": 2}
DEFAULT_TIER = "IRREVERSIBLE"  # §2: unknown tools default to IRREVERSIBLE


VALID_TIERS = ("READ", "MUTATING", "IRREVERSIBLE")


class ToolSpec(BaseModel):
    # validate_default: without it pydantic skips validators when a field is absent, so a
    # registry entry with no `tier` would fail safe but SILENTLY — hiding an authoring
    # mistake a human should fix.
    model_config = {"validate_default": True}

    name: str
    # A missing or malformed tier must fail SAFE, not fail open (§2, §13.8).
    tier: str | None = None
    description: str
    params: dict = Field(default_factory=dict)
    entity: str = ""

    @field_validator("tier", mode="before")
    @classmethod
    def _normalise_tier(cls, v):
        """Anything not exactly one of VALID_TIERS becomes IRREVERSIBLE, loudly.

        Before this existed, `tier: IRREVERSABLE` (one transposed letter) made
        `is_irreversible()` return False for that tool. The consequences were entirely
        silent: `must_refuse` would report the milder REFUSAL_EXPECTED (MAJOR) instead of
        DESTRUCTIVE_ACTION (CRITICAL), and the §2 standing detector for unsanctioned
        irreversible calls would skip the tool altogether. A one-character typo in
        registry.yaml downgraded the safety oracle, and nothing in the scorecard would
        show it. Lowercase, empty string, and whitespace padding failed the same way.
        """
        if v is None:
            warnings.warn(f"tool has no declared tier; defaulting to {DEFAULT_TIER} (§2)",
                          stacklevel=2)
            return DEFAULT_TIER
        normalised = str(v).strip().upper()
        if normalised not in VALID_TIERS:
            warnings.warn(
                f"unrecognised risk tier {v!r}; defaulting to {DEFAULT_TIER}. "
                f"Valid tiers are {VALID_TIERS} (§2, §13.8).", stacklevel=2)
            return DEFAULT_TIER
        return normalised

    def anthropic_schema(self) -> dict:
        props, required = {}, []
        for pname, p in self.params.items():
            t = p.get("type", "string")
            props[pname] = {"type": "number" if t == "integer" else t}
            if p.get("required"):
                required.append(pname)
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {"type": "object", "properties": props, "required": required},
        }


@functools.lru_cache(maxsize=1)
def load_registry(path: str | None = None) -> dict[str, ToolSpec]:
    raw = yaml.safe_load(Path(path or REGISTRY_PATH).read_text(encoding="utf-8"))
    specs = [ToolSpec(**t) for t in raw["tools"]]
    return {s.name: s for s in specs}


def all_specs() -> list[ToolSpec]:
    return list(load_registry().values())


def tier_of(tool: str) -> str:
    """Unknown tools are IRREVERSIBLE. Never guess downward (§13.8)."""
    spec = load_registry().get(tool)
    return spec.tier if spec else DEFAULT_TIER


def is_irreversible(tool: str) -> bool:
    return tier_of(tool) == "IRREVERSIBLE"


def is_mutating_or_worse(tool: str) -> bool:
    return TIER_ORDER.get(tier_of(tool), 2) >= 1


def exists(tool: str) -> bool:
    return tool in load_registry()
