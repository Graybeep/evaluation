"""Tool registry loader + tool specs handed to agents (CLAUDE.md §2)."""
from __future__ import annotations

import functools
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

REGISTRY_PATH = Path(__file__).with_name("registry.yaml")

TIER_ORDER = {"READ": 0, "MUTATING": 1, "IRREVERSIBLE": 2}
DEFAULT_TIER = "IRREVERSIBLE"  # §2: unknown tools default to IRREVERSIBLE


class ToolSpec(BaseModel):
    name: str
    tier: str
    description: str
    params: dict = Field(default_factory=dict)
    entity: str = ""

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
