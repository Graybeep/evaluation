"""Pressure probe corpus loader (CLAUDE.md §5, §7.4).

Public artefacts must reference payloads by id + category only. `redacted()` is the only
shape allowed to cross into a report.
"""
from __future__ import annotations

import functools
from pathlib import Path

import yaml
from pydantic import BaseModel

CORPUS_PATH = Path(__file__).with_name("pressure_corpus.yaml")

PRESSURE_LEVELS = ["P0", "P1", "P2", "P3", "P4", "P5"]


class Payload(BaseModel):
    id: str
    level: str
    category: str
    delivery: str            # instruction | tool_output | judge_selftest
    text: str
    names_tool: str | None = None

    def redacted(self) -> dict:
        """The only representation allowed in a public report (§7.4)."""
        return {"id": self.id, "level": self.level, "category": self.category}


@functools.lru_cache(maxsize=1)
def load_corpus(path: str | None = None) -> list[Payload]:
    raw = yaml.safe_load(Path(path or CORPUS_PATH).read_text(encoding="utf-8"))
    return [Payload(**p) for p in raw["payloads"]]


def by_id(pid: str) -> Payload:
    for p in load_corpus():
        if p.id == pid:
            return p
    raise KeyError(f"unknown payload id: {pid}")


def by_level(level: str, delivery: str | None = None) -> list[Payload]:
    out = [p for p in load_corpus() if p.level == level and p.category != "judge_attack"]
    if delivery:
        out = [p for p in out if p.delivery == delivery]
    return out


def judge_attacks() -> list[Payload]:
    return [p for p in load_corpus() if p.category == "judge_attack"]


def pick(level: str, seed: int, delivery: str | None = None) -> Payload | None:
    """Deterministic payload choice for a scenario seed."""
    pool = by_level(level, delivery)
    if not pool:
        return None
    return pool[seed % len(pool)]
