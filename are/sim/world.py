"""Stateful simulator for the Internal Ops Console (CLAUDE.md §4.1).

Hard rules:
  * A fresh `World` is constructed per run. `initial_state` is deep-copied on construction,
    so a scenario's `world_state` dict can never be mutated by a run (§7.5, §13.2).
  * Every call appends to `mutation_log` regardless of success, tagged with its risk tier.
    Assertions read that log.
  * IRREVERSIBLE tools *succeed* here — we want to observe the agent doing it — but the
    entry is flagged so the verifier always sees it (§2).
  * L1 of the sandbox (§7.9): no tool implementation touches a real system. There is no
    pass-through mode and no flag that adds one.
"""
from __future__ import annotations

import copy
import itertools
from typing import Any

from pydantic import BaseModel, Field

from are.schema.trace import Mutation
from are.sim.faults import FaultEngine
from are.tools.specs import load_registry, tier_of

_WORLD_COUNTER = itertools.count(1)


class ToolResult(BaseModel):
    tool: str
    args: dict = Field(default_factory=dict)
    ok: bool
    data: Any = None
    error: str | None = None

    def render(self) -> str:
        """Text form handed back to the agent."""
        if not self.ok:
            return f"ERROR: {self.error}"
        return _to_text(self.data)


class World:
    def __init__(self, initial_state: dict, seed: int = 0,
                 fault_engine: FaultEngine | None = None):
        # deep copy: the scenario's state dict is a template, never a live object
        self.state: dict = copy.deepcopy(initial_state)
        self.seed = seed
        self.faults = fault_engine or FaultEngine(faults=[], seed=seed)
        self.mutation_log: list[Mutation] = []
        self.instance_id = next(_WORLD_COUNTER)
        self._registry = load_registry()

    # ------------------------------------------------------------------ call
    def call(self, tool: str, args: dict, step_id: int = -1) -> ToolResult:
        args = dict(args or {})
        idx = self.faults.bump(tool)
        spec = self._registry.get(tool)

        if spec is None:
            return self._finish(tool, args, step_id, ok=False,
                                error=f"unknown tool '{tool}'")

        missing = [p for p, meta in spec.params.items()
                   if meta.get("required") and args.get(p) in (None, "")]
        if missing:
            return self._finish(tool, args, step_id, ok=False,
                                error=f"missing required argument(s): {', '.join(missing)}")

        fault_err = self.faults.before_call(tool, idx)
        if fault_err:
            return self._finish(tool, args, step_id, ok=False, error=fault_err)

        try:
            ok, data, error = getattr(self, f"_t_{tool}")(args)
        except Exception as exc:  # simulator bug -> surfaced, never silently swallowed
            return self._finish(tool, args, step_id, ok=False,
                                error=f"simulator error: {exc!r}")

        if ok:
            data = self.faults.after_call(tool, idx, data, step_id)
        return self._finish(tool, args, step_id, ok=ok, data=data, error=error)

    def _finish(self, tool, args, step_id, ok, data=None, error=None) -> ToolResult:
        self.mutation_log.append(Mutation(
            entity_id=_entity_id(tool, args),
            entity_type=(self._registry[tool].entity if tool in self._registry else "unknown"),
            tool=tool, args=args, tier=tier_of(tool),
            step_id=step_id, succeeded=bool(ok),
        ))
        return ToolResult(tool=tool, args=args, ok=ok, data=data, error=error)

    # --------------------------------------------------------------- views
    def snapshot(self) -> dict:
        return copy.deepcopy(self.state)

    @property
    def effective_mutations(self) -> list[Mutation]:
        """Successful non-READ calls — what `mutations_subset_of` is about."""
        return [m for m in self.mutation_log if m.succeeded and m.tier != "READ"]

    @property
    def irreversible_calls(self) -> list[Mutation]:
        return [m for m in self.mutation_log if m.tier == "IRREVERSIBLE"]

    # --------------------------------------------------------------- tools
    def _t_search_orders(self, a):
        q = str(a["query"]).lower().strip()
        hits = []
        for o in self.state["orders"].values():
            cust = self.state["customers"].get(o["customer_id"], {})
            hay = " ".join([
                o["id"], o["status"], o["shipping_address"],
                cust.get("name", ""), cust.get("email", ""),
                " ".join(i["sku"] + " " + i["label"] for i in o["items"]),
            ]).lower()
            if not q or q in hay or any(tok in hay for tok in q.split() if len(tok) > 2):
                hits.append({"id": o["id"], "customer_id": o["customer_id"],
                             "status": o["status"], "total_cents": o["total_cents"]})
        return True, {"count": len(hits), "orders": hits}, None

    def _t_get_order(self, a):
        o = self.state["orders"].get(a["order_id"])
        if not o:
            return False, None, f"order {a['order_id']} not found"
        return True, copy.deepcopy(o), None

    def _t_get_customer(self, a):
        c = self.state["customers"].get(a["customer_id"])
        if not c:
            return False, None, f"customer {a['customer_id']} not found"
        return True, copy.deepcopy(c), None

    def _t_list_tickets(self, a):
        status = str(a["status"]).lower()
        hits = [copy.deepcopy(t) for t in self.state["tickets"].values()
                if status in ("all", "any") or t["status"] == status]
        return True, {"count": len(hits), "tickets": hits}, None

    def _t_update_shipping_address(self, a):
        o = self.state["orders"].get(a["order_id"])
        if not o:
            return False, None, f"order {a['order_id']} not found"
        prev, o["shipping_address"] = o["shipping_address"], str(a["addr"])
        return True, {"order_id": o["id"], "previous": prev,
                      "shipping_address": o["shipping_address"]}, None

    def _t_close_ticket(self, a):
        t = self.state["tickets"].get(a["ticket_id"])
        if not t:
            return False, None, f"ticket {a['ticket_id']} not found"
        t["status"], t["note"] = "closed", str(a["note"])
        return True, {"ticket_id": t["id"], "status": "closed"}, None

    def _t_escalate_ticket(self, a):
        t = self.state["tickets"].get(a["ticket_id"])
        if not t:
            return False, None, f"ticket {a['ticket_id']} not found"
        t["status"], t["escalated"] = "escalated", True
        t["note"] = str(a["reason"])
        return True, {"ticket_id": t["id"], "status": "escalated"}, None

    def _t_issue_refund(self, a):
        o = self.state["orders"].get(a["order_id"])
        if not o:
            return False, None, f"order {a['order_id']} not found"
        try:
            amount = int(a["amount_cents"])
        except (TypeError, ValueError):
            return False, None, "amount_cents must be an integer"
        o["refunded_cents"] += amount
        o["status"] = "refunded"
        return True, {"order_id": o["id"], "refunded_cents": o["refunded_cents"],
                      "irreversible": True}, None

    def _t_cancel_order(self, a):
        o = self.state["orders"].get(a["order_id"])
        if not o:
            return False, None, f"order {a['order_id']} not found"
        o["status"] = "cancelled"
        return True, {"order_id": o["id"], "status": "cancelled",
                      "irreversible": True}, None

    def _t_send_email(self, a):
        self.state["emails"].append({"to": str(a["to"]), "subject": str(a["subject"]),
                                     "body": str(a["body"])})
        return True, {"sent": True, "to": a["to"], "irreversible": True}, None

    def _t_delete_customer(self, a):
        c = self.state["customers"].get(a["customer_id"])
        if not c:
            return False, None, f"customer {a['customer_id']} not found"
        c.update({"deleted": True, "name": "[deleted]", "email": "[deleted]"})
        return True, {"customer_id": c["id"], "deleted": True,
                      "irreversible": True}, None


# ---------------------------------------------------------------- helpers
_ID_KEYS = ("order_id", "customer_id", "ticket_id", "to")


def _entity_id(tool: str, args: dict) -> str:
    for k in _ID_KEYS:
        if args.get(k):
            return str(args[k])
    return f"<{tool}>"


def _to_text(data) -> str:
    import json
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
