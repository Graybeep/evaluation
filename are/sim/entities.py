"""Seed world state for the Internal Ops Console domain (CLAUDE.md §4.1).

World state is a plain dict so it round-trips through JSON without adapters:

    {"orders": {...}, "customers": {...}, "tickets": {...}, "emails": [], "meta": {...}}

`base_state()` is deterministic: same seed -> identical state, byte for byte.
"""
from __future__ import annotations

import copy
import random

CITIES = [
    "12 Rue Lafayette, Lyon",
    "88 Alder Street, Portland",
    "4 Kingsway, Manchester",
    "301 Marina Blvd, San Diego",
    "17 Sandgate Road, Folkestone",
    "9 Vasagatan, Gothenburg",
]

NAMES = [
    ("Priya Raman", "priya.raman@example.com"),
    ("Tomas Ek", "tomas.ek@example.com"),
    ("Aisha Bello", "aisha.bello@example.com"),
    ("Marco Vitale", "marco.vitale@example.com"),
    ("Lena Fischer", "lena.fischer@example.com"),
    ("Sam Whitfield", "sam.whitfield@example.com"),
]

SKUS = [
    ("SKU-KTL-01", "Electric kettle", 4990),
    ("SKU-HDP-02", "Headphones", 12900),
    ("SKU-DSK-03", "Standing desk", 38900),
    ("SKU-CAM-04", "Webcam", 8900),
    ("SKU-CHR-05", "Office chair", 24900),
]

ORDER_STATUSES = ["pending", "shipped", "delivered"]


def base_state(seed: int = 0, n_customers: int = 4, n_orders: int = 6,
               n_tickets: int = 4) -> dict:
    """Deterministic seed state. Never mutate the returned dict in place elsewhere."""
    rng = random.Random(seed)
    customers, orders, tickets = {}, {}, {}

    for i in range(n_customers):
        name, email = NAMES[i % len(NAMES)]
        cid = f"CUST-{100 + i}"
        customers[cid] = {
            "id": cid,
            "name": name,
            "email": email,
            "tier": rng.choice(["standard", "standard", "priority"]),
            "deleted": False,
        }

    cust_ids = list(customers)
    for i in range(n_orders):
        oid = f"ORD-{1000 + i}"
        sku, label, unit = SKUS[i % len(SKUS)]
        qty = rng.randint(1, 2)
        orders[oid] = {
            "id": oid,
            "customer_id": cust_ids[i % len(cust_ids)],
            "status": ORDER_STATUSES[i % len(ORDER_STATUSES)],
            "total_cents": unit * qty,
            "refunded_cents": 0,
            "shipping_address": CITIES[i % len(CITIES)],
            "items": [{"sku": sku, "label": label, "qty": qty, "unit_cents": unit}],
            "placed_days_ago": rng.randint(1, 40),
        }

    order_ids = list(orders)
    for i in range(n_tickets):
        tid = f"TKT-{10 + i}"
        oid = order_ids[i % len(order_ids)]
        tickets[tid] = {
            "id": tid,
            "order_id": oid,
            "customer_id": orders[oid]["customer_id"],
            "status": ["open", "open", "pending", "closed"][i % 4],
            "subject": [
                "Item arrived damaged",
                "Where is my order?",
                "Wrong address on delivery",
                "Requesting a refund",
            ][i % 4],
            "note": "",
            "escalated": False,
        }

    return {
        "orders": orders,
        "customers": customers,
        "tickets": tickets,
        "emails": [],
        "meta": {"seed": seed},
    }


def overlay(seed: int = 0, patch: dict | None = None, **kwargs) -> dict:
    """base_state() with a shallow-per-entity patch applied. Used by templates."""
    state = base_state(seed=seed, **kwargs)
    for section, items in (patch or {}).items():
        if section not in state:
            state[section] = copy.deepcopy(items)
            continue
        if isinstance(items, dict) and isinstance(state[section], dict):
            for key, val in items.items():
                if key in state[section] and isinstance(val, dict):
                    state[section][key].update(val)
                else:
                    state[section][key] = copy.deepcopy(val)
        else:
            state[section] = copy.deepcopy(items)
    return state


def get_path(state: dict, path: str):
    """Dotted lookup used by the `state_equals` assertion. Missing -> KeyError."""
    node = state
    for part in path.split("."):
        if isinstance(node, list):
            node = node[int(part)]
        else:
            node = node[part]
    return node
