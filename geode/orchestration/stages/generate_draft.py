"""Generate a draft answer via the model router service."""

from __future__ import annotations

from datetime import datetime, timezone

from geode.orchestration.contracts import QueryState, StageLog, StageStatus
from geode.orchestration.services import ContextBudgetManager, ModelRouter
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

    def __call__(self, state: QueryState) -> QueryState:
        """Produce a draft answer through the router."""

        if state.draft_request is None:
            raise ValueError("draft_request is required before generate_draft")
        budgeted_request, budget_report = self.budget_manager.fit(state.draft_request)
        state.context_budget = budget_report
        state.draft_request = budgeted_request
        state.answer, state.model_route = self.router.route_with_metadata(budgeted_request)
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
