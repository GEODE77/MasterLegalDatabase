"""Tests for input and interpretation orchestration stages."""

from __future__ import annotations

from datetime import date

import pytest

from geode.orchestration.contracts import AuthorityLevel, Intent, QueryState, QuestionType
from geode.orchestration.pipeline import Pipeline
from geode.orchestration.pipeline.base import Stage
from geode.orchestration.stages import (
    AmbiguityCheckStage,
    ParseIntentStage,
    QueryNormalizationStage,
    ResolveEntitiesStage,
    ScopeTemporalStage,
)


def test_co2_manufacturing_query_is_interpreted_with_disclosed_defaults() -> None:
    """Sample query produces the required interpretation outputs."""

    state = QueryState(
        intent=Intent(
            raw_query="What are the regulations that pertain to CO2 emissions for manufacturing?"
        )
    )

    result = Pipeline(_input_stages()).run(state)

    assert result.intent.question_type == QuestionType.COMPLIANCE_SURVEY
    assert result.intent.topic.value == "environmental"
    assert result.intent.sub_topic == "air_emissions"
    assert result.intent.industry.value == "manufacturing"
    assert result.intent.answer_shape.value == "compliance_survey"
    assert result.intent.normalized_query is not None
    assert "carbon dioxide" in result.intent.normalized_query
    assert "greenhouse gas" in result.intent.normalized_query

    assert result.jurisdiction is not None
    assert result.jurisdiction.state == "CO"
    assert result.jurisdiction.authority_levels == [AuthorityLevel.STATE, AuthorityLevel.FEDERAL]
    assert result.temporal is not None
    assert result.temporal.as_of_date == date.today()
    assert result.clarification_offered is True

    entity_ids = {entity.canonical_id for entity in result.entities}
    assert "NAICS-31-33" in entity_ids
    assert "POLLUTANT-GHG" in entity_ids

    assumptions = {(item.assumption_type.value, item.field, item.applied_value) for item in result.assumptions}
    assert ("expansion", "intent.normalized_query", "carbon dioxide, greenhouse gas") in assumptions
    assert ("default", "jurisdiction", "state, federal") in assumptions
    assert ("default", "sector", "NAICS-31-33") in assumptions


def test_expansions_and_defaults_are_recorded_in_trace() -> None:
    """Every applied expansion and default is visible in the audit trace."""

    state = QueryState(
        intent=Intent(
            raw_query="What are the regulations that pertain to CO2 emissions for manufacturing?"
        )
    )

    result = Pipeline(_input_stages()).run(state)

    expansion_logs = [
        entry
        for entry in result.trace
        if entry.stage_name == "query_normalization" and entry.details.get("expansions")
    ]
    default_logs = [
        entry
        for entry in result.trace
        if entry.stage_name in {"scope_temporal", "ambiguity_check"}
        and entry.details.get("defaults")
    ]
    assert expansion_logs
    assert default_logs
    assert "CO2" == expansion_logs[0].details["expansions"][0]["original"]
    flattened_defaults = [
        item
        for entry in default_logs
        for item in entry.details["defaults"]
    ]
    assert any(item["field"] == "jurisdiction" for item in flattened_defaults)
    assert any(item["field"] == "sector" for item in flattened_defaults)


def test_parse_intent_rejects_invalid_question_type_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configured classifier output must validate against enums before use."""

    def invalid_config() -> dict[str, object]:
        return {
            "rules": {
                "classification": {
                    "question_type_rules": [
                        {
                            "question_type": "not_allowed",
                            "answer_shape": "compliance_survey",
                            "any_terms": ["regulations"],
                        }
                    ],
                    "topic_rules": [],
                    "industry_rules": [],
                }
            }
        }

    monkeypatch.setattr("geode.orchestration.stages.parse_intent.load_orchestration_config", invalid_config)
    state = QueryState(intent=Intent(raw_query="Which regulations apply?"))

    with pytest.raises(ValueError):
        ParseIntentStage("parse_intent")(state)


def _input_stages() -> list[Stage]:
    """Return input and interpretation stages in execution order."""

    return [
        QueryNormalizationStage("query_normalization"),
        ParseIntentStage("parse_intent"),
        ResolveEntitiesStage("resolve_entities"),
        ScopeTemporalStage("scope_temporal"),
        AmbiguityCheckStage("ambiguity_check"),
    ]
