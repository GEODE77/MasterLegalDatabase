"""Provider prompt-cache measurements and savings reporting."""

from __future__ import annotations

from uuid import uuid4

from geode.orchestration.contracts import ProviderCacheEvent, ProviderCacheMetrics, QueryState


class ProviderCacheTracker:
    """Track measured prompt-cache hits without guessing provider behavior."""

    def record(
        self,
        *,
        provider: str,
        model: str,
        stable_prefix_hash: str,
        stable_prefix_tokens: int,
        cache_hit: bool,
        reason: str | None = None,
    ) -> ProviderCacheEvent:
        """Create one provider cache event for attachment to query state."""

        return ProviderCacheEvent(
            event_id=f"PCE-{uuid4().hex}",
            provider=provider,
            model=model,
            stable_prefix_hash=stable_prefix_hash,
            stable_prefix_tokens=stable_prefix_tokens,
            cache_hit=cache_hit,
            reason=reason,
        )

    def metrics(self, events: list[ProviderCacheEvent]) -> ProviderCacheMetrics:
        """Aggregate measured cache events into a report."""

        eligible = len(events)
        hits = sum(1 for event in events if event.cache_hit)
        misses = eligible - hits
        return ProviderCacheMetrics(
            eligible_requests=eligible,
            hits=hits,
            misses=misses,
            hit_rate_percent=round((hits / eligible) * 100, 2) if eligible else 0.0,
        )

    def attach(self, state: QueryState, event: ProviderCacheEvent) -> None:
        """Attach one measured provider result to query state."""

        state.provider_cache_events.append(event)
        state.provider_cache_metrics = self.metrics(state.provider_cache_events)
