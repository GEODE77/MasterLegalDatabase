"""Ordered pipeline runner for orchestration stages."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from geode.orchestration.contracts import QueryState, StageLog, StageStatus
from geode.orchestration.pipeline.base import Stage
from geode.orchestration.services import (
    AccessControlService,
    FreshnessMonitor,
    OrchestrationCache,
    OrchestrationLogger,
)


class Pipeline:
    """Run an ordered list of stages with audit logging."""

    def __init__(
        self,
        stages: Sequence[Stage],
        cache: OrchestrationCache | None = None,
        logger: OrchestrationLogger | None = None,
        freshness_monitor: FreshnessMonitor | None = None,
        access_control: AccessControlService | None = None,
        corpus_version: str = "dev",
    ) -> None:
        """Create a pipeline from ordered stages."""

        self.stages = list(stages)
        self.cache = cache
        self.logger = logger
        self.freshness_monitor = freshness_monitor or FreshnessMonitor(corpus_version)
        self.access_control = access_control
        self.corpus_version = corpus_version

    def run(self, state: QueryState) -> QueryState:
        """Execute stages until completion or halt."""

        current = state
        for stage in self.stages:
            if current.halted:
                break

            cache_key = self._cache_key(current, stage.name)
            if self.cache is not None:
                cached, event = self.cache.get(cache_key, self.corpus_version)
                current.cache_events.append(event)
                freshness = self.freshness_monitor.check(
                    event.corpus_version if event.status.value == "hit" else None
                )
                current.freshness = freshness
                if cached is not None:
                    current = cached
                    current.cache_events.append(event)
                    self._log_new_entries(current, max(len(current.trace) - 1, 0))
                    continue

            started_at = datetime.now(timezone.utc)
            before_trace_count = len(current.trace)
            current = stage(current)
            status = StageStatus.HALTED if current.halted else StageStatus.PASSED
            current.trace.append(
                StageLog(
                    stage_name=stage.name,
                    status=status,
                    message=f"Stage {stage.name} completed.",
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            if self.access_control is not None:
                self.access_control.validate_state(current)
            if self.cache is not None:
                current.cache_events.append(self.cache.set(cache_key, current, self.corpus_version))
            self._log_new_entries(current, before_trace_count)
            if current.halted:
                break
        return current

    def _cache_key(self, state: QueryState, stage_name: str) -> str:
        """Build the cache key for one stage."""

        normalized_query = state.intent.normalized_query or state.intent.raw_query
        if self.cache is not None:
            return self.cache.make_key(normalized_query, self.corpus_version, stage_name)
        return f"{self.corpus_version}:{stage_name}:{normalized_query}"

    def _log_new_entries(self, state: QueryState, start_index: int) -> None:
        """Write newly appended trace entries to the audit logger."""

        if self.logger is None:
            return
        for log in state.trace[start_index:]:
            self.logger.write(log, state)
