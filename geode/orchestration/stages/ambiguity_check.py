"""Apply documented defaults for underspecified query scope."""

from __future__ import annotations

from datetime import datetime, timezone

from geode.orchestration.config import load_orchestration_config
from geode.orchestration.contracts import (
    AssumptionType,
    AuthorityLevel,
    DisclosedAssumption,
    Jurisdiction,
    QueryState,
    StageLog,
    StageStatus,
)
from geode.orchestration.stages._stub import PassThroughStage


class AmbiguityCheckStage(PassThroughStage):
    """Detect ambiguity and apply configured defaults instead of blocking."""

    def __call__(self, state: QueryState) -> QueryState:
        """Apply jurisdiction and sector defaults when scope is underspecified."""

        defaults = load_orchestration_config()["defaults"]
        applied: list[dict[str, str | None]] = []

        if state.jurisdiction is None:
            jurisdiction_default = defaults["jurisdiction"]
            levels = [AuthorityLevel(str(level)) for level in jurisdiction_default["authority_levels"]]
            state.jurisdiction = Jurisdiction(
                authority_level=levels[0],
                authority_levels=levels,
                state=str(jurisdiction_default["state"]),
            )
            assumption = DisclosedAssumption(
                assumption_type=AssumptionType.DEFAULT,
                field="jurisdiction",
                applied_value=", ".join(level.value for level in levels),
                reason=str(jurisdiction_default["reason"]),
            )
            state.assumptions.append(assumption)
            applied.append(assumption.model_dump(mode="json"))

        if _has_broad_manufacturing_scope(state):
            sector_default = defaults["sector"]
            assumption = DisclosedAssumption(
                assumption_type=AssumptionType.DEFAULT,
                field="sector",
                original="manufacturing",
                applied_value=str(sector_default["canonical_id"]),
                reason=str(sector_default["reason"]),
            )
            if not _assumption_exists(state, assumption):
                state.assumptions.append(assumption)
                applied.append(assumption.model_dump(mode="json"))

        if applied:
            state.clarification_offered = True
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Ambiguity checked and configured defaults applied.",
                completed_at=datetime.now(timezone.utc),
                details={"defaults": applied, "clarification_offered": state.clarification_offered},
            )
        )
        return state


def _has_broad_manufacturing_scope(state: QueryState) -> bool:
    """Return whether manufacturing is present without a narrower subsector."""

    if state.intent.industry.value != "manufacturing":
        return False
    query = (state.intent.normalized_query or state.intent.raw_query).casefold()
    narrower_terms = ("naics", "semiconductor", "ceramic", "food", "chemical")
    return not any(term in query for term in narrower_terms)


def _assumption_exists(state: QueryState, assumption: DisclosedAssumption) -> bool:
    """Return whether an equivalent assumption already exists."""

    return any(
        item.assumption_type == assumption.assumption_type
        and item.field == assumption.field
        and item.applied_value == assumption.applied_value
        for item in state.assumptions
    )
