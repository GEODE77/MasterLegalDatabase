"""Tests for local authority identity and pilot behavior."""

from geode.orchestration.contracts import (
    AuthorityLevel,
    Intent,
    QueryState,
    RetrievalStep,
    RetrievalStrategyType,
)
from geode.orchestration.evaluation import load_local_golden_questions
from geode.orchestration.services import LocalKnowledgeRetrievalBackend
from geode.orchestration.stages.resolve_jurisdiction import ResolveJurisdictionStage
from geode.utils.file_io import atomic_write_jsonl


def test_local_golden_questions_cover_three_counties_and_two_families() -> None:
    """The bounded pilot contains the requested local coverage cases."""

    questions = load_local_golden_questions()
    text = " ".join(question.query.casefold() for question in questions)
    assert "denver county" in text
    assert "boulder county" in text
    assert "el paso county" in text
    assert "school district" in text
    assert "water" in text


def test_district_identity_is_resolved() -> None:
    """A known district adds district authority without losing state scope."""

    state = QueryState(intent=Intent(raw_query="Which rules apply to Boulder Valley School District?"))
    result = ResolveJurisdictionStage("resolve_jurisdiction")(state)
    assert result.jurisdiction is not None
    assert result.jurisdiction.district == "Boulder Valley School District"
    assert result.jurisdiction.district_family == "school"
    assert AuthorityLevel.DISTRICT in result.jurisdiction.authority_levels
    assert any(item.authority_level == AuthorityLevel.DISTRICT for item in result.jurisdiction_coverage)


def test_local_retrieval_filters_by_district_and_preserves_passage(tmp_path) -> None:
    """Local retrieval uses geography and carries exact source location metadata."""

    catalog = tmp_path / "_CONTROL_PLANE" / "RETRIEVAL_CATALOG.jsonl"
    atomic_write_jsonl(
        catalog,
        [
            {
                "id": "LOCAL-RULE-BVSD-AC",
                "entity_type": "local_rule",
                "title": "Boulder Valley safety policy",
                "citation": "BVSD AC",
                "path": "09_District_Authorities/_rules/LOCAL-RULE-BVSD-AC.md",
                "source_url": "https://www.bvsd.org/about/board-of-education/policies",
                "authority_id": "CO-DISTRICT-BVSD",
                "authority_name": "Boulder Valley School District",
                "authority_level": "district",
                "authority_type": "school_district",
                "district_family": "school",
                "county_names": ["Boulder County"],
                "source_section": "AC",
                "section_heading": "Nondiscrimination",
                "source_page": 4,
                "source_page_end": 5,
                "source_line_start": 10,
                "source_line_end": 18,
                "retrieval_text": "LOCAL-RULE-BVSD-AC Boulder Valley School District Boulder County safety policy",
                "confidence": 0.8,
            }
        ],
        tmp_path,
    )
    state = QueryState(
        intent=Intent(raw_query="Which Boulder Valley School District safety rules apply?"),
        jurisdiction={
            "authority_level": AuthorityLevel.STATE,
            "authority_levels": [AuthorityLevel.STATE, AuthorityLevel.COUNTY, AuthorityLevel.DISTRICT],
            "county": "Boulder County",
            "district": "Boulder Valley School District",
            "district_family": "school",
        },
    )
    results = LocalKnowledgeRetrievalBackend(tmp_path).search(
        state,
        RetrievalStep(
            step_id="local-1",
            category_id="district_rules",
            strategy=RetrievalStrategyType.DISCOVERY_SWEEP,
            authority_level=AuthorityLevel.DISTRICT,
            targets=["local_rule"],
        ),
    )
    assert len(results) == 1
    assert results[0].provenance.passage is not None
    assert results[0].provenance.passage.section == "AC"
    assert results[0].provenance.passage.page == 4
    assert results[0].provenance.passage.page_end == 5
    assert results[0].provenance.passage.line_start == 10
    assert results[0].provenance.passage.line_end == 18


def test_local_retrieval_excludes_source_preservation_units(tmp_path) -> None:
    """Uninterpreted local text cannot enter answer evidence as a rule unit."""

    catalog = tmp_path / "_CONTROL_PLANE" / "RETRIEVAL_CATALOG.jsonl"
    atomic_write_jsonl(
        catalog,
        [{
            "id": "LOCAL-RULE-BVSD-UNIT-0001",
            "entity_type": "rule_unit",
            "authority_level": "district",
            "authority_id": "CO-DISTRICT-BVSD",
            "county_names": ["Boulder County"],
            "semantic_status": "source_preservation_only",
            "retrieval_text": "Boulder Valley School District source section",
            "confidence": 0.45,
        }],
        tmp_path,
    )
    state = QueryState(
        intent=Intent(raw_query="Which Boulder Valley School District rules apply?"),
        jurisdiction={
            "authority_level": AuthorityLevel.STATE,
            "authority_levels": [AuthorityLevel.STATE, AuthorityLevel.DISTRICT],
            "county": "Boulder County",
            "district": "Boulder Valley School District",
            "district_family": "school",
        },
    )
    results = LocalKnowledgeRetrievalBackend(tmp_path).search(
        state,
        RetrievalStep(
            step_id="local-2",
            category_id="district_rules",
            strategy=RetrievalStrategyType.DISCOVERY_SWEEP,
            authority_level=AuthorityLevel.DISTRICT,
            targets=["rule_unit"],
        ),
    )
    assert results == []


def test_local_retrieval_reads_source_backed_text_not_only_catalog_metadata(tmp_path) -> None:
    """A catalog hit opens the referenced metadata record for model evidence."""

    metadata = tmp_path / "08_County_Authorities" / "_meta" / "local_rules.jsonl"
    atomic_write_jsonl(
        metadata,
        [{
            "id": "LOCAL-RULE-TEST-1",
            "entity_type": "local_rule",
            "full_text": "The county requires an access permit for this facility.",
            "source_hash": "a" * 64,
        }],
        tmp_path,
    )
    catalog = tmp_path / "_CONTROL_PLANE" / "RETRIEVAL_CATALOG.jsonl"
    atomic_write_jsonl(
        catalog,
        [{
            "id": "LOCAL-RULE-TEST-1",
            "entity_type": "local_rule",
            "title": "County access rule",
            "citation": "County access rule",
            "path": "08_County_Authorities/_meta/local_rules.jsonl",
            "meta_path": "08_County_Authorities/_meta/local_rules.jsonl",
            "source_path": "_RAW_ARCHIVE/local/county/access.pdf",
            "source_url": "https://county.example.gov/access.pdf",
            "source_hash": "a" * 64,
            "authority_id": "CO-COUNTY-TEST",
            "authority_name": "Test County",
            "authority_level": "county",
            "authority_type": "county",
            "county_names": ["Test County"],
            "source_category": "county_codes",
            "semantic_status": "semantic_ready",
            "retrieval_text": "metadata-only title that must not be used",
            "confidence": 0.8,
        }],
        tmp_path,
    )
    state = QueryState(
        intent=Intent(raw_query="What access permit is required in Test County?"),
        jurisdiction={
            "authority_level": AuthorityLevel.STATE,
            "authority_levels": [AuthorityLevel.STATE, AuthorityLevel.COUNTY],
            "county": "Test County",
        },
    )
    results = LocalKnowledgeRetrievalBackend(tmp_path).search(
        state,
        RetrievalStep(
            step_id="local-3",
            category_id="county_rules",
            strategy=RetrievalStrategyType.DISCOVERY_SWEEP,
            authority_level=AuthorityLevel.COUNTY,
            targets=["local_rule"],
        ),
    )
    assert len(results) == 1
    assert "access permit" in results[0].text
    assert "metadata-only" not in results[0].text
    assert results[0].provenance.source_path.endswith("local_rules.jsonl")


def test_local_retrieval_rejects_local_record_without_matching_geography(tmp_path) -> None:
    """A local source without the requested county cannot be treated as applicable."""

    catalog = tmp_path / "_CONTROL_PLANE" / "RETRIEVAL_CATALOG.jsonl"
    atomic_write_jsonl(
        catalog,
        [{
            "id": "LOCAL-RULE-OTHER-COUNTY",
            "entity_type": "local_rule",
            "citation": "Other County Rule",
            "title": "Other County Rule",
            "authority_level": "county",
            "authority_id": "CO-COUNTY-OTHER",
            "authority_name": "Other County",
            "county_names": [],
            "semantic_status": "semantic_ready",
            "retrieval_text": "facility permit requirement",
            "confidence": 0.9,
        }],
        tmp_path,
    )
    state = QueryState(
        intent=Intent(raw_query="What facility permit requirement applies in Boulder County?"),
        jurisdiction={
            "authority_level": AuthorityLevel.STATE,
            "authority_levels": [AuthorityLevel.STATE, AuthorityLevel.COUNTY],
            "county": "Boulder County",
        },
    )
    results = LocalKnowledgeRetrievalBackend(tmp_path).search(
        state,
        RetrievalStep(
            step_id="local-4",
            category_id="county_rules",
            strategy=RetrievalStrategyType.DISCOVERY_SWEEP,
            authority_level=AuthorityLevel.COUNTY,
            targets=["local_rule"],
        ),
    )
    assert results == []
