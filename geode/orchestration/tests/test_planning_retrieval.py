"""Tests for planning and retrieval orchestration stages."""

from __future__ import annotations

from geode.orchestration.contracts import (
    AuthorityLevel,
    Citation,
    CoverageRequirement,
    CoverageStatus,
    Evidence,
    GraphLink,
    Intent,
    Provenance,
    QueryState,
)
from geode.orchestration.pipeline import Pipeline
from geode.orchestration.pipeline.base import Stage
from geode.orchestration.services import FixtureRetrievalBackend
from geode.orchestration.stages import (
    AmbiguityCheckStage,
    BuildCoverageContractStage,
    ParseIntentStage,
    PlanRetrievalStage,
    QueryNormalizationStage,
    ResolveEntitiesStage,
    ResolveJurisdictionStage,
    RetrieveStage,
    ScopeTemporalStage,
)

SAMPLE_QUERY = "What are the regulations that pertain to CO2 emissions for manufacturing?"


def test_coverage_contract_includes_required_and_conditional_authorities() -> None:
    """Sample query coverage includes federal, Colorado, and conditional local categories."""

    result = Pipeline(_planning_stages()).run(QueryState(intent=Intent(raw_query=SAMPLE_QUERY)))

    assert result.coverage_contract is not None
    categories = {item.category_id: item for item in result.coverage_contract.expected_categories}
    assert categories["federal_environmental_rules"].authority_level == AuthorityLevel.FEDERAL
    assert categories["federal_environmental_rules"].requirement == CoverageRequirement.REQUIRED
    assert categories["colorado_statutes"].authority_level == AuthorityLevel.STATE
    assert categories["colorado_regulations"].authority_level == AuthorityLevel.STATE
    assert categories["county_rules"].requirement == CoverageRequirement.CONDITIONAL
    assert categories["municipal_rules"].requirement == CoverageRequirement.CONDITIONAL

    coverage = {
        item.authority_level: item.requirement for item in result.jurisdiction_coverage
    }
    assert coverage[AuthorityLevel.FEDERAL] == CoverageRequirement.REQUIRED
    assert coverage[AuthorityLevel.STATE] == CoverageRequirement.REQUIRED
    assert coverage[AuthorityLevel.COUNTY] == CoverageRequirement.CONDITIONAL
    assert coverage[AuthorityLevel.MUNICIPAL] == CoverageRequirement.CONDITIONAL


def test_retrieval_traverses_statute_to_regulation_candidate() -> None:
    """Multi-hop retrieval follows a configured relationship from statute to regulation."""

    statute = _candidate(
        evidence_id="ev-statute",
        source_id="CRS-25-7-109",
        category_id="colorado_statutes",
        authority_level=AuthorityLevel.STATE,
        text="Colorado statute authorizes air quality rules.",
    )
    regulation = _candidate(
        evidence_id="ev-regulation",
        source_id="5_CCR_1001-9",
        category_id="colorado_regulations",
        authority_level=AuthorityLevel.STATE,
        text="Colorado regulation includes emissions control requirements.",
    )
    backend = FixtureRetrievalBackend(
        evidence=[statute, regulation],
        graph_links=[
            GraphLink(
                source_id="CRS-25-7-109",
                target_id="5_CCR_1001-9",
                relationship="enables",
            )
        ],
    )

    result = Pipeline([*_planning_stages(), RetrieveStage("retrieve", backend=backend)]).run(
        QueryState(intent=Intent(raw_query=SAMPLE_QUERY))
    )

    assert all(isinstance(item, Evidence) for item in result.evidence)
    assert {item.evidence_id for item in result.evidence} == {"ev-statute", "ev-regulation"}
    traversed = [item for item in result.evidence if item.evidence_id == "ev-regulation"]
    assert traversed
    assert traversed[0].is_candidate is True
    assert traversed[0].relationship_path == ["CRS-25-7-109", "5_CCR_1001-9"]


def test_empty_expected_categories_are_flagged_not_dropped() -> None:
    """Required categories without candidates are explicitly marked empty."""

    backend = FixtureRetrievalBackend(
        evidence=[
            _candidate(
                evidence_id="ev-statute",
                source_id="CRS-25-7-109",
                category_id="colorado_statutes",
                authority_level=AuthorityLevel.STATE,
                text="Colorado statute authorizes air quality rules.",
            )
        ]
    )

    result = Pipeline([*_planning_stages(), RetrieveStage("retrieve", backend=backend)]).run(
        QueryState(intent=Intent(raw_query=SAMPLE_QUERY))
    )

    assert result.coverage_contract is not None
    statuses = {
        item.category_id: item.status for item in result.coverage_contract.expected_categories
    }
    assert statuses["colorado_statutes"] == CoverageStatus.FOUND
    assert statuses["colorado_regulations"] == CoverageStatus.EMPTY
    assert statuses["federal_environmental_rules"] == CoverageStatus.EMPTY
    assert statuses["county_rules"] == CoverageStatus.CONDITIONAL
    assert "colorado_regulations" in result.empty_expected_categories
    assert "federal_environmental_rules" in result.empty_expected_categories
    assert "county_rules" not in result.empty_expected_categories


def _planning_stages() -> list[Stage]:
    """Return stages through retrieval planning."""

    return [
        QueryNormalizationStage("query_normalization"),
        ParseIntentStage("parse_intent"),
        ResolveEntitiesStage("resolve_entities"),
        ScopeTemporalStage("scope_temporal"),
        AmbiguityCheckStage("ambiguity_check"),
        ResolveJurisdictionStage("resolve_jurisdiction"),
        BuildCoverageContractStage("build_coverage_contract"),
        PlanRetrievalStage("plan_retrieval"),
    ]


def _candidate(
    evidence_id: str,
    source_id: str,
    category_id: str,
    authority_level: AuthorityLevel,
    text: str,
) -> Evidence:
    """Build a typed candidate evidence object."""

    return Evidence(
        evidence_id=evidence_id,
        text=text,
        citation=Citation(
            citation_text=source_id,
            canonical_id=source_id,
            authority_level=authority_level,
        ),
        provenance=Provenance(
            source_id=source_id,
            source_path=f"_fixture/{source_id}.json",
        ),
        confidence=0.9,
        category_id=category_id,
        is_candidate=True,
    )
