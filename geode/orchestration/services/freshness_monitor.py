"""Freshness monitoring for cached orchestration results."""

from __future__ import annotations

from geode.orchestration.contracts import FreshnessResult


class FreshnessMonitor:
    """Detect stale cached results when corpus version changes."""

    def __init__(self, corpus_version: str = "dev") -> None:
        """Create a freshness monitor."""

        self.corpus_version = corpus_version

    def check(self, cached_version: str | None) -> FreshnessResult:
        """Return freshness status."""

        stale = cached_version is not None and cached_version != self.corpus_version
        return FreshnessResult(
            corpus_version=self.corpus_version,
            cached_version=cached_version,
            stale=stale,
            reason="corpus version changed" if stale else None,
        )
