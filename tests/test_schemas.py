"""Schema tests for core Geode models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from geode.constants import CRS_LAYER
from geode.schemas import (
    AGOpinion,
    Agency,
    Bill,
    COPRRRReview,
    CrosswalkEntry,
    ExecutiveOrder,
    RegulationRule,
    RuleUnit,
    RulemakingNotice,
    SessionLaw,
    SourceDocument,
    Sponsor,
    StatuteSection,
    TimelineEvent,
)
from geode.schemas.validators import canonical_crs_id
from geode.schemas.validators import validate_record


def test_canonical_crs_id_normalizes_segments() -> None:
    """CRS IDs use normalized numeric segments."""

    assert canonical_crs_id("025", "07", "00109") == "CRS-25-7-109"


def test_source_document_rejects_unofficial_source_url() -> None:
    """Source URLs must be official or authorized hosts."""

    with pytest.raises(ValidationError):
        SourceDocument(
            source_id="bad",
            layer=CRS_LAYER,
            source_owner="Unknown",
            source_url="https://example.com/source",
            source_format="fixture",
            retrieved_at=datetime.now(timezone.utc),
            raw_path="_RAW_ARCHIVE/crs/bad.txt",
            sha256="a" * 64,
            confidence=1.0,
        )


def test_missing_fields_require_zero_confidence() -> None:
    """Null extracted fields retain explicit zero field confidence."""

    section = StatuteSection(
        entity_id="CRS-25-7-109",
        title_number="25",
        title_name="Public Health and Environment",
        article_number="7",
        article_name="Air Quality Control",
        part_number="1",
        part_name="General Provisions",
        section_number="109",
        heading="Commission - powers and duties.",
        text="The commission shall promulgate rules.",
        citations=["CRS-25-7-109"],
        regulated_entities=None,
        regulated_entities_confidence=0.0,
        effective_date=None,
        effective_date_confidence=0.0,
        source_url=(
            "https://content.leg.colorado.gov/agencies/office-legislative-legal-services/"
            "2025-crs-titles-download"
        ),
        source_path="_RAW_ARCHIVE/crs/title25.txt",
        publication_year=2025,
        data_retrieved="2026-06-15",
        data_version="2025_fixture",
        confidence=1.0,
    )
    assert section.entity_id == "CRS-25-7-109"
    assert section.model_dump()["id"] == "CRS-25-7-109"
    assert section.model_dump()["full_text"] == "The commission shall promulgate rules."


def test_all_design_entity_models_accept_valid_minimal_records() -> None:
    """The 12 master-design entity schemas validate their ID and vocabulary contracts."""

    confidence = {"overall": 0.95}
    crs_source_url = (
        "https://content.leg.colorado.gov/agencies/office-legislative-legal-services/"
        "2025-crs-titles-download"
    )
    StatuteSection(
        id="CRS-25-7-109",
        title_num="25",
        title_name="Public Health and Environment",
        article_num="7",
        article_name="Air Quality Control",
        section_num="25-7-109",
        section_heading="Commission - powers and duties.",
        full_text="The commission shall promulgate rules.",
        subject_tags=["air_quality"],
        industry_tags=["manufacturing"],
        cross_references_outbound=["CRS-25-7-109"],
        source_url=crs_source_url,
        data_retrieved="2026-06-15",
        data_version="2025_fixture",
        confidence=confidence,
    )
    RegulationRule(
        id="5_CCR_1001-9",
        ccr_number="5 CCR 1001-9",
        title="Regulation 3 - Stationary Source Permitting",
        department="Public Health and Environment",
        department_code="1000",
        agency="Air Quality Control Commission",
        agency_code="CDPHE_AQCC",
        enabling_statutes=["CRS-25-7-109"],
        effective_date="2024-01-15",
        status="active",
        full_text="PART A",
        chunk_level_3_summary="Establishes permitting for stationary sources.",
        subject_tags=["air_quality", "permitting"],
        industry_tags=["manufacturing"],
        compliance_keywords=["permit_required"],
        source_url="https://www.sos.state.co.us/CCR/Welcome.do",
        source_format="docx",
        extraction_method="fixture_parse",
        confidence=confidence,
    )
    Bill(
        id="SB23-016",
        session="2023",
        chamber="Senate",
        bill_number="016",
        title="Air Quality Control Amendments",
        sponsors=[Sponsor(name="Doe, Jane", party="D", chamber="Senate", role="primary")],
        status="signed",
        status_date="2023-06-02",
        introduced_date="2023-01-15",
        statutes_amended=["CRS-25-7-109"],
        subject_tags=["air_quality"],
        source_url="https://legiscan.com/CO",
        confidence=confidence,
    )
    RulemakingNotice(
        id="RM-2023-00847",
        notice_type="adopted",
        ccr_rule_affected="5_CCR_1001-9",
        agency_code="CDPHE_AQCC",
        summary="Amendments to Regulation 3.",
        effective_date="2024-01-15",
        publication_date="2023-12-10",
        subject_tags=["air_quality"],
        source_url="https://www.sos.state.co.us/CCR/eDocketPublic.do",
        confidence=confidence,
    )
    ExecutiveOrder(
        id="EO-2025-003",
        order_number="D 2025 003",
        title="State Agency Use of AI",
        governor="Polis, Jared",
        signed_date="2025-03-01",
        status="active",
        full_text="WHEREAS...",
        summary="Directs state agencies to develop AI use policies.",
        statutes_cited=["CRS-24-37.5-101"],
        subject_tags=["ai_governance"],
        source_url="https://www.colorado.gov/governor/executive-orders",
        confidence=confidence,
    )
    SessionLaw(
        id="SL-2023-142",
        session_year="2023",
        chapter="142",
        bill_id="SB23-016",
        title="Air Quality Amendments",
        effective_date="2023-07-01",
        statutes_affected=["CRS-25-7-109"],
        summary="Amends CRS 25-7-109.",
        subject_tags=["air_quality"],
        source_url="https://leg.colorado.gov/session-laws",
        confidence=confidence,
    )
    AGOpinion(
        id="AGO-2024-001",
        opinion_number="24-01",
        title="Municipal Authority",
        attorney_general="Weiser, Phil",
        issued_date="2024-03-15",
        statutes_interpreted=["CRS-29-20-104"],
        summary="Discusses municipal authority.",
        subject_tags=["housing"],
        source_url="https://coag.gov/opinions/",
        confidence=confidence,
    )
    COPRRRReview(
        id="COPRRR-2023-AUD",
        review_type="sunset",
        program_reviewed="State Board of Accountancy",
        agency_code="DORA_DPO",
        publication_date="2023-10-15",
        recommendation="continue with modifications",
        summary="Continue accountancy licensing with modifications.",
        subject_tags=["accountancy"],
        source_url="https://coprrr.colorado.gov/",
        confidence=confidence,
    )
    RuleUnit(
        id="6_CCR_1007-2_2.2_1",
        parent_regulation_id="6_CCR_1007-2",
        source_section="Part 2, Section 2.2(1)",
        rule_type="prohibition",
        regulated_entity="Any person seeking to operate a solid waste facility",
        action_required="Must obtain certificate before operating",
        enabling_statute=["CRS-30-20-102"],
        plain_english_summary="Cannot operate without a certificate.",
        subject_tags=["solid_waste", "permitting"],
        confidence=confidence,
    )
    CrosswalkEntry(
        source_id="5_CCR_1001-9",
        source_type="regulation_rule",
        target_id="CRS-25-7-109",
        target_type="statute_section",
        relationship="authorized_by",
        confidence=0.95,
        source_evidence="Promulgated pursuant to section 25-7-109, C.R.S.",
        data_retrieved="2026-06-12",
    )
    TimelineEvent(
        id="TE-2023-07-01-001",
        date="2023-07-01",
        event_type="bill_signed",
        entity_id="SB23-016",
        entity_type="bill",
        description="SB23-016 signed.",
        affects=["CRS-25-7-109"],
        layer="03_Legislation",
        file_path="03_Legislation/2023/bills_2023.jsonl",
    )
    Agency(
        id="CDPHE_AQCC",
        agency_name="Air Quality Control Commission",
        agency_abbreviation="AQCC",
        department="Public Health and Environment",
        department_code="CDPHE",
        enabling_statutes=["CRS-25-7-104"],
        ccr_prefix="5 CCR 1001-",
        website_url="https://cdphe.colorado.gov/aqcc",
    )


def test_invalid_ontology_tag_is_rejected() -> None:
    """Corpus models reject invented ontology tags."""

    with pytest.raises(ValidationError):
        RuleUnit(
            id="bad",
            parent_regulation_id="6_CCR_1007-2",
            source_section="Part 2",
            rule_type="obligation",
            regulated_entity="Any person",
            action_required="Must comply",
            plain_english_summary="Must comply.",
            subject_tags=["invented_tag"],
            confidence={"overall": 0.9},
        )


def test_validate_record_reports_missing_required_fields() -> None:
    """validate_record returns errors for missing required schema fields."""

    valid, errors = validate_record({"entity_type": "bill", "id": "SB23-016"})
    assert not valid
    assert errors


def test_invalid_id_fails_validation() -> None:
    """Entity ID patterns are enforced."""

    with pytest.raises(ValidationError):
        Bill(
            id="BAD",
            session="2023",
            chamber="Senate",
            bill_number="016",
            title="Air Quality Control Amendments",
            sponsors=[Sponsor(name="Doe, Jane", party="D", chamber="Senate", role="primary")],
            status="signed",
            status_date="2023-06-02",
            introduced_date="2023-01-15",
            subject_tags=["air_quality"],
            source_url="https://legiscan.com/CO",
            confidence={"overall": 0.98},
        )


def test_future_date_fails_validation() -> None:
    """Impossible future dates are rejected."""

    with pytest.raises(ValidationError):
        ExecutiveOrder(
            id="EO-2099-003",
            order_number="D 2099 003",
            title="Future Order",
            governor="Future Governor",
            signed_date="2099-03-01",
            status="active",
            full_text="WHEREAS...",
            summary="Future order.",
            subject_tags=["state_operations"],
            source_url="https://www.colorado.gov/governor/executive-orders",
            confidence={"overall": 0.9},
        )
