"""Execute planned retrieval through a backend interface."""

from __future__ import annotations

from datetime import datetime, timezone

from geode.orchestration.contracts import (
    CoverageRequirement,
    CoverageStatus,
    Evidence,
    ExpectedCategory,
    QueryState,
    StageLog,
    StageStatus,
)
from geode.orchestration.services import LocalKnowledgeRetrievalBackend, RetrievalBackend
from geode.orchestration.stages._stub import PassThroughStage


class RetrieveStage(PassThroughStage):
    """Retrieve candidate sources without asserting facts."""

    def __init__(
        self,
        name: str | None = None,
        backend: RetrievalBackend | None = None,
    ) -> None:
        """Create a retrieval stage."""

        super().__init__(name)
        self.backend = backend or LocalKnowledgeRetrievalBackend()

    def __call__(self, state: QueryState) -> QueryState:
        """Execute retrieval plan and update candidate evidence."""

        if state.retrieval_plan is None or state.coverage_contract is None:
            raise ValueError("retrieval_plan and coverage_contract are required before retrieve")
        candidates: list[Evidence] = []
        seen_ids: set[str] = set()
        for step in state.retrieval_plan.steps:
            step_candidates = self.backend.search(state, step)
            for candidate in step_candidates:
                _append_candidate(candidates, seen_ids, candidate)
                if state.retrieval_plan.graph_traversal_enabled:
                    for reached in self.backend.traverse(candidate, step.follow_relationships):
                        _append_candidate(candidates, seen_ids, reached)

        state.evidence = candidates
        categories = _update_category_statuses(state.coverage_contract.expected_categories, candidates)
        state.coverage_contract.expected_categories = categories
        state.empty_expected_categories = [
            category.category_id
            for category in categories
            if category.status == CoverageStatus.EMPTY
        ]
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Candidate sources retrieved by engine-selected plan.",
                completed_at=datetime.now(timezone.utc),
                details={
                    "candidate_count": len(candidates),
                    "empty_expected_categories": state.empty_expected_categories,
                    "categories": [category.model_dump(mode="json") for category in categories],
                },
            )
        )
        return state


def _append_candidate(
    candidates: list[Evidence],
    seen_ids: set[str],
    candidate: Evidence,
) -> None:
    """Append a candidate once."""

    key = candidate.evidence_id
    if key in seen_ids:
        return
    seen_ids.add(key)
    candidates.append(candidate)


def _update_category_statuses(
    categories: list[ExpectedCategory],
    candidates: list[Evidence],
) -> list[ExpectedCategory]:
    """Mark category coverage from retrieval output."""

    category_ids_with_results = {
        candidate.category_id for candidate in candidates if candidate.category_id is not None
    }
    updated: list[ExpectedCategory] = []
    for category in categories:
        if category.category_id in category_ids_with_results:
            status = CoverageStatus.FOUND
        elif category.requirement == CoverageRequirement.CONDITIONAL:
            status = CoverageStatus.CONDITIONAL
        else:
            status = CoverageStatus.EMPTY
        updated.append(category.model_copy(update={"status": status}))
    return updated
