"""Deterministic orchestration cache."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from geode.orchestration.contracts import CacheEvent, CacheStatus, QueryState


@dataclass
class CacheEntry:
    """One cached query-state snapshot."""

    corpus_version: str
    state: QueryState


class OrchestrationCache:
    """Cache deterministic stage outputs and retrieval results."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Create an in-memory cache with optional JSONL-compatible persistence."""

        self.cache_dir = cache_dir
        self._entries: dict[str, CacheEntry] = {}
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def make_key(
        self,
        normalized_query: str,
        corpus_version: str,
        scope: str,
    ) -> str:
        """Build a stable cache key."""

        raw = json.dumps(
            {
                "normalized_query": normalized_query,
                "corpus_version": corpus_version,
                "scope": scope,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str, corpus_version: str) -> tuple[QueryState | None, CacheEvent]:
        """Return cached state when present and fresh."""

        entry = self._entries.get(key) or self._read_entry(key)
        if entry is None:
            return None, CacheEvent(key=key, status=CacheStatus.MISS, corpus_version=corpus_version)
        if entry.corpus_version != corpus_version:
            return (
                None,
                CacheEvent(
                    key=key,
                    status=CacheStatus.STALE,
                    corpus_version=corpus_version,
                    reason=f"cached corpus version {entry.corpus_version} is stale",
                ),
            )
        return entry.state, CacheEvent(key=key, status=CacheStatus.HIT, corpus_version=corpus_version)

    def set(self, key: str, state: QueryState, corpus_version: str) -> CacheEvent:
        """Store a state snapshot."""

        entry = CacheEntry(corpus_version=corpus_version, state=state.model_copy(deep=True))
        self._entries[key] = entry
        if self.cache_dir is not None:
            path = self.cache_dir / f"{key}.json"
            path.write_text(
                json.dumps(
                    {
                        "corpus_version": corpus_version,
                        "state": json.loads(state.model_dump_json()),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        return CacheEvent(key=key, status=CacheStatus.MISS, corpus_version=corpus_version)

    def _read_entry(self, key: str) -> CacheEntry | None:
        """Read a persisted cache entry if present."""

        if self.cache_dir is None:
            return None
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CacheEntry(
            corpus_version=str(payload["corpus_version"]),
            state=QueryState.model_validate(payload["state"]),
        )
