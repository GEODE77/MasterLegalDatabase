"""Detect the query's temporal scope."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from geode.orchestration.config import load_orchestration_config
from geode.orchestration.contracts import (
    AssumptionType,
    DisclosedAssumption,
    QueryState,
    StageLog,
    StageStatus,
    TemporalScope,
)
from geode.orchestration.stages._stub import PassThroughStage

AS_OF_DATE_PATTERN = re.compile(r"\bas of\s+(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)


class ScopeTemporalStage(PassThroughStage):
    """Populate temporal scope from explicit dates or configured defaults."""

    def __call__(self, state: QueryState) -> QueryState:
        """Detect as-of dates and current-vs-historical intent."""

        query = state.intent.normalized_query or state.intent.raw_query
        defaults = load_orchestration_config()["defaults"]["temporal"]
        match = AS_OF_DATE_PATTERN.search(query)
        if match:
            as_of_date = date.fromisoformat(match.group(1))
            temporal = TemporalScope(
                as_of_date=as_of_date,
                mode="as_of",
                description=f"Law as of {as_of_date.isoformat()}",
            )
            details: dict[str, Any] = {
                "mode": "as_of",
                "as_of_date": as_of_date.isoformat(),
                "defaults": [],
            }
        elif _is_historical(query):
            temporal = TemporalScope(mode="historical", description="Historical legal development")
            details = {"mode": "historical", "defaults": []}
        else:
            today = date.today()
            temporal = TemporalScope(
                as_of_date=today,
                mode=str(defaults["mode"]),
                description="Current law",
            )
            assumption = DisclosedAssumption(
                assumption_type=AssumptionType.DEFAULT,
                field="temporal.as_of_date",
                applied_value=today.isoformat(),
                reason=str(defaults["reason"]),
            )
            state.assumptions.append(assumption)
            details = {
                "mode": temporal.mode,
                "as_of_date": today.isoformat(),
                "defaults": [assumption.model_dump(mode="json")],
            }
        state.temporal = temporal
        state.temporal_scope = temporal
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Temporal scope detected.",
                completed_at=datetime.now(timezone.utc),
                details=details,
            )
        )
        return state


def _is_historical(query: str) -> bool:
    """Return whether the query asks for historical treatment."""

    lowered = query.casefold()
    return any(term in lowered for term in ("historical", "history", "since", "changed"))
