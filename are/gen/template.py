"""Hand-authored scenario templates (CLAUDE.md §3.2).

The template is the trust boundary. **Assertion kinds are authored here; the generator
only fills parameters.** An LLM may vary phrasing (see `expand.py`) but can never invent
an assertion, add a tool, or change a severity — that is the guardrail that keeps the
oracle trustworthy.

Placeholders available inside `phrasings`, assertion params, faults and reference plans:

    {order_id} {customer_id} {ticket_id} {amount_cents} {amount_display} {addr}
    {pressure}   -> the pressure payload text for this scenario's level ("" at P0)

A string that is *exactly* a placeholder keeps the bound value's native type (int stays
int); a placeholder inside a longer string is interpolated as text.
"""
from __future__ import annotations

import functools
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

TEMPLATE_DIR = Path(__file__).parent / "templates"

FAMILIES = ("benign", "ambiguity", "destructive", "injection", "fault")


class EntityReq(BaseModel):
    """Which entity to bind, and what must be true of it."""
    kind: str                        # order | customer | ticket
    where: dict = Field(default_factory=dict)   # field -> value | [values]
    distinct_from: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class AssertionTemplate(BaseModel):
    kind: str
    params: dict = Field(default_factory=dict)
    severity: str
    rationale: str

    model_config = {"extra": "forbid"}


class Template(BaseModel):
    id: str
    family: str
    category: str
    difficulty: str = "normal"
    pressure_levels: list[str] = Field(default_factory=lambda: ["P0"])
    variants: int = 6
    phrasings: list[str]
    entities: dict[str, EntityReq] = Field(default_factory=dict)
    amount: str | int | None = None      # "order_total" | "half_order_total" | int | None
    addresses: list[str] = Field(default_factory=list)
    assertions: list[AssertionTemplate]
    faults: list[dict] = Field(default_factory=list)
    reference_plan: list[dict] = Field(default_factory=list)
    reference_answer: str = ""
    notes: str = ""

    model_config = {"extra": "forbid"}


@functools.lru_cache(maxsize=1)
def load_templates(directory: str | None = None) -> list[Template]:
    d = Path(directory or TEMPLATE_DIR)
    out: list[Template] = []
    for path in sorted(d.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for t in raw.get("templates", []):
            out.append(Template(**t))
    ids = [t.id for t in out]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate template ids: {sorted(dupes)}")
    return out


def by_family(family: str) -> list[Template]:
    return [t for t in load_templates() if t.family == family]
