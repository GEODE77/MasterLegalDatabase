"""Normalize query terms using configured expansions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from geode.orchestration.config import load_orchestration_config
from geode.orchestration.contracts import (
    AssumptionType,
    DisclosedAssumption,
    QueryState,
    StageLog,
    StageStatus,
)
from geode.orchestration.stages._stub import PassThroughStage


class QueryNormalizationStage(PassThroughStage):
    """Expand configured abbreviations and synonyms."""

    def __call__(self, state: QueryState) -> QueryState:
        """Apply configured query expansions and record assumptions."""

        config = load_orchestration_config()
        query = state.intent.normalized_query or state.intent.raw_query
        normalized = query
        expansions_applied: list[dict[str, Any]] = []
        for expansion in config["synonyms"].get("expansions", []):
            term = str(expansion["term"])
            if term.casefold() not in normalized.casefold():
                continue
            expanded_terms = [str(item) for item in expansion.get("expanded_terms", [])]
            addition = " ".join(item for item in expanded_terms if item.casefold() not in normalized.casefold())
            if addition:
                normalized = f"{normalized} {addition}"
            assumption = DisclosedAssumption(
                assumption_type=AssumptionType.EXPANSION,
                field="intent.normalized_query",
                original=term,
                applied_value=", ".join(expanded_terms),
                reason=str(expansion["reason"]),
            )
            state.assumptions.append(assumption)
            expansions_applied.append(assumption.model_dump(mode="json"))

        state.intent.normalized_query = " ".join(normalized.split())
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Query normalization applied configured expansions.",
                completed_at=datetime.now(timezone.utc),
                details={"expansions": expansions_applied},
            )
        )
        return state
