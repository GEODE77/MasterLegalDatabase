"""Extractor and parser tests."""

from __future__ import annotations

from pathlib import Path

from geode.connectors.crs_parser import parse_crs_fixture
from geode.extractors.citation_extractor import (
    extract_ccr_references,
    extract_crs_citations,
    extract_defined_terms,
    extract_federal_references,
)
from geode.extractors.regex_patterns import PATTERNS
from geode.extractors.structure_parser import extract_metadata, parse_structure


def test_extract_crs_citations_returns_canonical_ids() -> None:
    """Citation extraction returns canonical CRS IDs."""

    text = "See 25-7-109 and section 025-07-00114, C.R.S."
    citations = extract_crs_citations(text)
    assert [citation.canonical_form for citation in citations] == [
        "CRS-25-7-109",
        "CRS-25-7-114",
    ]


def test_parse_crs_fixture(crs_fixture_path: Path) -> None:
    """The CRS fixture parser returns validated sections."""

    document = parse_crs_fixture(crs_fixture_path, "25", 2025)
    assert document.entity_id == "CRS-TITLE-25"
    assert len(document.sections) == 2
    assert document.sections[0].entity_id == "CRS-25-7-109"
    assert "CRS-25-7-114" in document.sections[0].citations


def test_extract_ccr_and_federal_references() -> None:
    """CCR, CFR, and USC references are extracted as structured citations."""

    text = "See 5 CCR 1001-9, 40 C.F.R. 70.2, and 42 U.S.C. § 7401."
    ccr = extract_ccr_references(text)
    federal = extract_federal_references(text)
    assert ccr[0].canonical_form == "5_CCR_1001-9"
    assert [citation.canonical_form for citation in federal] == [
        "40 C.F.R. 70.2",
        "42 U.S.C. § 7401",
    ]


def test_extract_defined_terms() -> None:
    """Quoted terms followed by means are extracted."""

    text = '"Stationary source" means a building or facility.'
    assert extract_defined_terms(text) == ["Stationary source"]


def test_regex_patterns_positive_and_negative_cases() -> None:
    """Core deterministic regexes match positives and ignore negatives."""

    positives = {
        "ccr_number": "5 CCR 1001-9",
        "crs_citation": "section 25-7-109, C.R.S.",
        "crs_citation_alt": "C.R.S. § 25-7-109",
        "part_boundary": "PART A. General",
        "section_number": "1.2 Applicability",
        "subsection_number": "(12) text",
        "subsection_letter": "(aa) text",
        "subsection_roman": "(IV) text",
        "subsubsection_letter": "(A) text",
        "defined_term": '"Facility" means a building.',
        "effective_date": "Effective January 1, 2024",
        "adopted_date": "Adopted December 10, 2023",
        "cfr_citation": "40 C.F.R. 70.2",
        "usc_citation": "42 U.S.C. § 7401",
        "department": "Department of Public Health and Environment",
        "agency": "Air Quality Control Commission",
    }
    negatives = {
        "ccr_number": "CCR 1001",
        "crs_citation": "section twenty-five",
        "defined_term": '"Facility" includes a building.',
    }
    for name, text in positives.items():
        assert PATTERNS[name].search(text), name
    for name, text in negatives.items():
        assert not PATTERNS[name].search(text), name


def test_parse_structure_builds_hierarchy() -> None:
    """Structure parser builds part, section, and subsection nodes."""

    tree = parse_structure(
        """
### Part 1 - General Provisions
#### 25-7-109. Commission - powers and duties.
(1) The commission shall promulgate rules.
(a) The rules must be public.
"""
    )
    assert tree.parts[0].label == "1"
    assert tree.parts[0].sections[0].number == "25-7-109"
    assert tree.parts[0].sections[0].subsections[0].label == "(1)"


def test_extract_metadata_flags_regex_misses_for_llm() -> None:
    """Metadata extraction marks matches deterministic and misses needs_llm."""

    metadata = extract_metadata("Effective January 1, 2024")
    flags = metadata["confidence_flags"]
    assert isinstance(flags, dict)
    assert flags["effective_date"] == "deterministic"
    assert flags["ccr_number"] == "needs_llm"
