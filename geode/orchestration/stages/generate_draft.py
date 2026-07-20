"""Generate a draft answer via the model router service."""

from __future__ import annotations

from datetime import datetime, timezone

from geode.orchestration.contracts import PromptContext, QueryState, StageLog, StageStatus
from geode.orchestration.services import (
    ContextBudgetManager,
    ModelRouter,
    PromptPrefixBuilder,
    ProviderCacheTracker,
)
from geode.orchestration.stages._stub import PassThroughStage


class GenerateDraftStage(PassThroughStage):
    """Call the model router with assembled evidence and policies."""

    def __init__(
        self,
        name: str | None = None,
        router: ModelRouter | None = None,
        budget_manager: ContextBudgetManager | None = None,
    ) -> None:
        """Create a draft generation stage."""

        super().__init__(name)
        self.router = router or ModelRouter()
        self.budget_manager = budget_manager or ContextBudgetManager()
        self.cache_tracker = ProviderCacheTracker()

    def __call__(self, state: QueryState) -> QueryState:
        """Produce a draft answer through the router."""

        if state.draft_request is None:
            raise ValueError("draft_request is required before generate_draft")
        draft_request = state.draft_request
        budgeted_request, budget_report = self.budget_manager.fit(draft_request)
        state.context_budget = budget_report
        state.draft_request = budgeted_request
        state.answer, state.model_route = self.router.route_with_metadata(budgeted_request)
        self._record_provider_cache_measurement(state)
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Draft answer generated from assembled evidence.",
                completed_at=datetime.now(timezone.utc),
                details={
                    "evidence_ids": state.answer.evidence_ids if state.answer else [],
                    "citation_count": len(state.answer.citations) if state.answer else 0,
                    "context_budget": budget_report.model_dump(mode="json"),
                    "model_route": state.model_route.model_dump(mode="json")
                    if state.model_route
                    else None,
                },
            )
        )
        return state

    def _record_provider_cache_measurement(self, state: QueryState) -> None:
        """Record a cache result only when the selected adapter supplied one."""

        if (
            state.prompt_packet is None
            or state.model_route is None
            or state.draft_request is None
        ):
            return
        stable_prompt = PromptPrefixBuilder().split_rendered(
            state.draft_request.prompt,
            provider=state.model_route.provider,
        )
        state.prompt_packet = state.prompt_packet.model_copy(
            update={
                "stable_prefix": stable_prompt.stable_prefix,
                "dynamic_suffix": stable_prompt.dynamic_suffix,
                "stable_prefix_hash": stable_prompt.prefix_hash,
                "stable_prefix_tokens": stable_prompt.prefix_tokens,
                "provider_cache_settings": stable_prompt.cache_settings.__dict__,
            }
        )
        state.draft_request = state.draft_request.model_copy(
            update={
                "prompt_context": PromptContext(
                    stable_prefix=stable_prompt.stable_prefix,
                    dynamic_suffix=stable_prompt.dynamic_suffix,
                    stable_prefix_hash=stable_prompt.prefix_hash,
                    stable_prefix_tokens=stable_prompt.prefix_tokens,
                    provider_cache_settings=stable_prompt.cache_settings.__dict__,
                )
            }
        )
        if state.model_route.cache_hit is None:
            return
        event = self.cache_tracker.record(
            provider=state.model_route.provider,
            model=state.model_route.model,
            stable_prefix_hash=stable_prompt.prefix_hash,
            stable_prefix_tokens=stable_prompt.prefix_tokens,
            cache_hit=state.model_route.cache_hit,
        )
        self.cache_tracker.attach(state, event)
