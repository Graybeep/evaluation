"""Precision/recall for the two lexicon heuristics (fix.md L6).

Why this exists. The project's thesis is "machine-checkable assertions, not a
judge" (§1). But `must_refuse` and `must_request_clarification` are decided by
**substring lexicons over the agent's final answer** — which is neither a
verifiable state check nor an LLM judge, but a third thing that was never named
or measured. It is load-bearing: `MISSING_CLARIFICATION` is the whole `quitter`
external-validity story, and `REFUSAL_EXPECTED` gates the softer half of the
safety taxonomy.

So it gets measured against hand labels, and the numbers are published whatever
they say. The lexicon is **not** tuned to the labels — doing so would convert a
measurement into a fit, and the number would stop meaning anything.

Honesty about the labels themselves: they were produced by the model that wrote
this repository, not by an independent annotator. That is a real weakness and it
is recorded in the fixture file. It is not the same circularity as judging an
LLM judge with LLM labels, because the lexicon is a fixed list of strings that
could not have been fitted to labels written afterwards — but a reader should
discount accordingly.
"""
from __future__ import annotations

import json
from pathlib import Path

from are.verify.rules import CLARIFY_LEXICON, REFUSAL_LEXICON, _has_any

FIXTURES = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / \
    "refusal_clarify_labels.json"


def predict_refuse(text: str) -> bool:
    """Exactly what `check_assertion` does for `must_refuse`."""
    return _has_any(text, REFUSAL_LEXICON)


def predict_clarify(text: str) -> bool:
    """Exactly what `check_assertion` does for `must_request_clarification`."""
    return "?" in (text or "") or _has_any(text, CLARIFY_LEXICON)


def load_labels(path: Path | None = None) -> list[dict]:
    data = json.loads((path or FIXTURES).read_text(encoding="utf-8"))
    return data["items"]


def score(items: list[dict], axis: str) -> dict:
    """Confusion matrix + P/R/F1 for one axis.

    A rate whose denominator is zero is `None`, not 0.0: precision is undefined
    when nothing was predicted positive, and reporting 0.0 there would read as
    "it got everything wrong" rather than "it never fired" (§7.10).
    """
    predict = predict_refuse if axis == "refuse" else predict_clarify
    key = f"label_{axis}"

    tp = fp = tn = fn = 0
    errors = []
    for it in items:
        pred, truth = predict(it["text"]), bool(it[key])
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
            errors.append({"id": it["id"], "kind": "false_positive",
                           "text": it["text"][:120], "note": it.get("note", "")})
        elif not pred and truth:
            fn += 1
            errors.append({"id": it["id"], "kind": "false_negative",
                           "text": it["text"][:120], "note": it.get("note", "")})
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall else None)

    return {
        "axis": axis, "n": len(items),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "positives_in_set": tp + fn,
        "errors": errors,
    }


def evaluate(path: Path | None = None) -> dict:
    items = load_labels(path)
    observed = [i for i in items if i["source"] == "observed"]
    challenge = [i for i in items if i["source"] == "challenge"]
    return {
        "overall": {a: score(items, a) for a in ("refuse", "clarify")},
        "observed": {a: score(observed, a) for a in ("refuse", "clarify")},
        "challenge": {a: score(challenge, a) for a in ("refuse", "clarify")},
        "n_items": len(items),
        "n_observed": len(observed),
        "n_challenge": len(challenge),
        "note": ("`observed` is real trace text from the frozen set, but the "
                 "offline policies emit ~41 distinct templated strings, so it "
                 "cannot exercise a lexicon the way model prose would. "
                 "`challenge` is hand-written natural language covering the "
                 "phrasings the lexicon must get right. Read both."),
    }
