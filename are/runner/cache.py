"""Response cache for bit-identical replay (CLAUDE.md §4.5).

This is ONE of two determinism mechanisms and must not be confused with the other:

  * Response cache (here)  -> bit-identical replay for debugging. `--replay`.
  * Repeated sampling      -> statistics. Cache OFF, temperature as configured, N runs.

Key = sha256(model_version, system, messages, temperature, seed). Values are stored as
one JSON file per key under `runs/_cache/`.

Modes:
  off     — no reads, no writes (the default for anything that produces statistics)
  record  — miss -> call the API and write the response
  replay  — miss -> raise. Guarantees the replay really is a replay.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

# ARE_CACHE_DIR lets a replay run point at a recorded cache elsewhere (and lets tests use a
# tmpdir instead of polluting runs/).
DEFAULT_CACHE_DIR = Path(os.environ.get("ARE_CACHE_DIR", "runs/_cache"))


class CacheMiss(Exception):
    pass


class ResponseCache:
    def __init__(self, mode: str = "off", cache_dir: Path | str | None = None):
        if mode not in ("off", "record", "replay"):
            raise ValueError(f"bad cache mode: {mode}")
        self.mode = mode
        # resolved at call time, not import time, so ARE_CACHE_DIR set by a caller applies
        self.dir = Path(cache_dir if cache_dir is not None
                        else os.environ.get("ARE_CACHE_DIR", "runs/_cache"))
        self.hits = 0
        self.misses = 0
        if mode != "off":
            self.dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(model_version: str, system: str, messages: list, temperature: float,
            seed: int) -> str:
        blob = json.dumps(
            {"model": model_version, "system": system, "messages": messages,
             "temperature": temperature, "seed": seed},
            sort_keys=True, ensure_ascii=False, default=str,
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def get(self, key: str):
        if self.mode == "off":
            raise CacheMiss(key)
        path = self.dir / f"{key}.json"
        if path.exists():
            self.hits += 1
            return json.loads(path.read_text(encoding="utf-8"))
        self.misses += 1
        if self.mode == "replay":
            raise CacheMiss(
                f"replay mode: no cached response for {key[:12]}… — "
                "record the run first (`--cache record`)")
        raise CacheMiss(key)

    def put(self, key: str, value: dict) -> None:
        if self.mode == "off":
            return
        (self.dir / f"{key}.json").write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, default=str),
            encoding="utf-8")
