"""Resolve configured entity terms to canonical identifiers."""

from datetime import datetime, timezone
from typing import Any

from geode.orchestration.config import load_orchestration_config
from geode.orchestration.contracts import Entity, EntityStatus, QueryState, StageLog, StageStatus
from geode.orchestration.stages._stub import PassThroughStage


class ResolveEntitiesStage(PassThroughStage):
    """Normalize sectors, pollutants, agencies, and statutes."""

    def __call__(self, state: QueryState) -> QueryState:
        """Populate canonical entities from configured term maps."""

        config = load_orchestration_config()["entities"]
        query = (state.intent.normalized_query or state.intent.raw_query).casefold()
        entities: list[Entity] = []
        for entity_type, records in (
            ("sector", config.get("sectors", [])),
            ("pollutant", config.get("pollutants", [])),
            ("agency", config.get("agencies", [])),
            ("statute", config.get("statutes", [])),
        ):
            for record in records:
                matched = _matched_terms(record, query)
                if not matched:
                    continue
                entities.append(
                    Entity(
                        name=matched[0],
                        entity_type=entity_type,
                        geode_id=str(record["canonical_id"]),
                        canonical_id=str(record["canonical_id"]),
                        canonical_label=str(record["canonical_label"]),
                        normalized_terms=[str(term) for term in record.get("normalized_terms", [])],
                        status=EntityStatus.RESOLVED,
                        confidence=float(record.get("confidence", 0.8)),
                    )
                )

        state.entities = _dedupe_entities([*state.entities, *entities])
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Entities resolved with configured canonical maps.",
                completed_at=datetime.now(timezone.utc),
                details={
                    "entities": [
                        {
                            "entity_type": entity.entity_type,
                            "canonical_id": entity.canonical_id,
                            "canonical_label": entity.canonical_label,
                        }
                        for entity in state.entities
                    ]
                },
            )
        )
        return state


def _matched_terms(record: dict[str, Any], query: str) -> list[str]:
    """Return configured terms present in the query."""

    return [str(term) for term in record.get("terms", []) if str(term).casefold() in query]


def _dedupe_entities(entities: list[Entity]) -> list[Entity]:
    """Keep one entity per canonical ID."""

    seen: set[str] = set()
    deduped: list[Entity] = []
    for entity in entities:
        key = entity.canonical_id or entity.name
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entity)
    return deduped
