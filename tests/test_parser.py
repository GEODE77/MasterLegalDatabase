"""Unit tests for deterministic Colorado bill parsing logic."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import bill_parser

SECTION_SYMBOL = "\u00a7"


def _write_extracted_json(tmp_path: Path, stem: str, full_text: str) -> Path:
    """Write a minimal extractor payload for parse_bill tests."""

    payload = {
        "source_file": f"{stem}.pdf",
        "page_count": 3,
        "full_text": full_text,
    }
    path = tmp_path / f"{stem}_extracted.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestBillNumberParsing:
    """Tests for extracting canonical Colorado bill numbers."""

    def test_standard_house_bill(self) -> None:
        """Validate that a standard House bill number is extracted."""

        assert bill_parser.parse_bill_number("Introduced as HB25-1001.") == "HB25-1001"

    def test_standard_senate_bill(self, SAMPLE_LABOR_BILL: str) -> None:
        """Validate that a standard Senate bill number is extracted."""

        assert bill_parser.parse_bill_number(SAMPLE_LABOR_BILL) == "SB25-0055"

    def test_no_bill_number(self) -> None:
        """Validate that missing bill numbers return None."""

        assert bill_parser.parse_bill_number("No bill identifier appears here.") is None

    def test_multiple_bill_numbers(self) -> None:
        """Validate that the first bill number in text is returned."""

        text = "HB25-1001 relates to SB25-0055 in one fiscal note."
        assert bill_parser.parse_bill_number(text) == "HB25-1001"


class TestTitleParsing:
    """Tests for parsing and cleaning the CONCERNING title clause."""

    def test_concerning_title(self, SAMPLE_BILL_HEADER: str) -> None:
        """Validate extraction of the HB25-1001 CONCERNING title."""

        title = bill_parser.parse_title(SAMPLE_BILL_HEADER)
        assert title == "Concerning The Regulation Of Emissions From Industrial Facilities."

    def test_title_cleanup(self) -> None:
        """Validate whitespace cleanup and title-case normalization."""

        text = """
        HB25-1002
        A BILL FOR AN ACT
        CONCERNING     ACCESS
        TO    SCHOOL   RECORDS
        BY REPRESENTATIVE(S) Garcia
        """
        assert bill_parser.parse_title(text) == "Concerning Access To School Records."

    def test_no_title(self) -> None:
        """Validate that text without a CONCERNING clause returns None."""

        text = "HB25-1003\nA BILL FOR AN ACT\nREGARDING A LOCAL MATTER."
        assert bill_parser.parse_title(text) is None

    def test_labor_bill_title(self, SAMPLE_LABOR_BILL: str) -> None:
        """Validate extraction of the SB25-0055 labor bill title."""

        assert bill_parser.parse_title(SAMPLE_LABOR_BILL) == (
            "Concerning Modifications To The Colorado Wage Equity Act."
        )


class TestSponsorParsing:
    """Tests for House and Senate sponsor extraction."""

    def test_house_sponsors(self, SAMPLE_FULL_BILL: str) -> None:
        """Validate extraction of HB25-1001 House sponsors."""

        sponsors = bill_parser.parse_sponsors(SAMPLE_FULL_BILL)
        assert sponsors["house_sponsors"] == ["Smith", "Garcia", "Thompson"]

    def test_senate_sponsors(self, SAMPLE_FULL_BILL: str) -> None:
        """Validate extraction of the HB25-1001 Senate sponsor."""

        sponsors = bill_parser.parse_sponsors(SAMPLE_FULL_BILL)
        assert sponsors["senate_sponsors"] == ["Williams"]

    def test_multiple_sponsors(self, SAMPLE_TAX_BILL: str) -> None:
        """Validate comma-separated sponsor lists from HB25-1099."""

        sponsors = bill_parser.parse_sponsors(SAMPLE_TAX_BILL)
        assert sponsors["house_sponsors"] == ["Nguyen", "Davis", "Clark"]
        assert sponsors["senate_sponsors"] == ["Robinson", "Taylor"]

    def test_no_sponsors(self) -> None:
        """Validate that missing sponsor blocks produce empty lists."""

        sponsors = bill_parser.parse_sponsors("HB25-1001\nCONCERNING RECORDS.")
        assert sponsors == {"house_sponsors": [], "senate_sponsors": []}


class TestSectionParsing:
    """Tests for splitting bill text into numbered sections."""

    def test_section_count(self, SAMPLE_SECTIONS: str) -> None:
        """Validate that HB25-1001 sample text has four sections."""

        sections = bill_parser.parse_sections(SAMPLE_SECTIONS)
        assert len(sections) == 4

    def test_section_text(self, SAMPLE_SECTIONS: str) -> None:
        """Validate that each parsed section keeps its full body text."""

        sections = bill_parser.parse_sections(SAMPLE_SECTIONS)
        assert "stationary source" in sections[0]["text"]
        assert "industrial emissions compliance fund" in sections[1]["text"]
        assert "industrial discharge" in sections[2]["text"]
        assert "takes effect July 1, 2025" in sections[3]["text"]

    def test_crs_references_per_section(self, SAMPLE_SECTIONS: str) -> None:
        """Validate CRS references are assigned to their containing sections."""

        sections = bill_parser.parse_sections(SAMPLE_SECTIONS)
        assert sections[0]["crs_references"] == [
            f"{SECTION_SYMBOL} 25-7-114.7, C.R.S."
        ]
        assert sections[1]["crs_references"] == [
            f"{SECTION_SYMBOL} 25-7-114.8, C.R.S."
        ]

    def test_action_detection(self, SAMPLE_SECTIONS: str) -> None:
        """Validate amend and add action detection for HB25-1001 sections."""

        sections = bill_parser.parse_sections(SAMPLE_SECTIONS)
        assert sections[0]["action"] == "amend"
        assert sections[2]["action"] == "add"


class TestCRSReferenceParsing:
    """Tests for Colorado Revised Statutes reference extraction."""

    def test_standard_crs_ref(self) -> None:
        """Validate extraction of a standard CRS reference."""

        refs = bill_parser.parse_crs_references(
            f"See {SECTION_SYMBOL} 25-7-114.7, C.R.S."
        )
        assert refs == [f"{SECTION_SYMBOL} 25-7-114.7, C.R.S."]

    def test_crs_with_subsection(self) -> None:
        """Validate that subsection citations normalize to their CRS section."""

        text = f"See {SECTION_SYMBOL} 39-22-104 (3)(a), C.R.S. for the tax rule."
        assert bill_parser.parse_crs_references(text) == [
            f"{SECTION_SYMBOL} 39-22-104, C.R.S."
        ]

    def test_multiple_refs(self) -> None:
        """Validate that multiple CRS references are found and deduplicated."""

        text = (
            f"{SECTION_SYMBOL} 25-7-114.7, C.R.S.; "
            f"{SECTION_SYMBOL} 25-7-114.8, C.R.S.; "
            f"{SECTION_SYMBOL} 25-7-114.7 (3)(a), C.R.S."
        )
        assert bill_parser.parse_crs_references(text) == [
            f"{SECTION_SYMBOL} 25-7-114.7, C.R.S.",
            f"{SECTION_SYMBOL} 25-7-114.8, C.R.S.",
        ]

    def test_no_refs(self) -> None:
        """Validate that text without CRS references returns an empty list."""

        assert bill_parser.parse_crs_references("No statute citation here.") == []

    def test_all_sample_bills_have_refs(
        self,
        SAMPLE_BILL_TEXTS: dict[str, str],
    ) -> None:
        """Validate every generated sample bill contains at least one CRS ref."""

        for bill_number, text in SAMPLE_BILL_TEXTS.items():
            assert bill_parser.parse_crs_references(text), bill_number


class TestEffectiveDateParsing:
    """Tests for effective-date clause extraction."""

    def test_specific_date(self, SAMPLE_EFFECTIVE_DATE: str) -> None:
        """Validate extraction of the HB25-1001 specific effective date."""

        assert bill_parser.parse_effective_date(SAMPLE_EFFECTIVE_DATE) == (
            "Effective date. This act takes effect July 1, 2025."
        )

    def test_upon_passage(self, SAMPLE_LABOR_BILL: str) -> None:
        """Validate extraction of the SB25-0055 upon-passage clause."""

        clause = bill_parser.parse_effective_date(SAMPLE_LABOR_BILL)
        assert clause is not None
        assert "takes effect upon passage" in clause

    def test_conditional_date(self, SAMPLE_TAX_BILL: str) -> None:
        """Validate extraction of the HB25-1099 tax-year effective clause."""

        clause = bill_parser.parse_effective_date(SAMPLE_TAX_BILL)
        assert clause is not None
        assert "tax years starting on or after January 1, 2026" in clause

    def test_no_date(self) -> None:
        """Validate that missing effective-date text returns None."""

        assert bill_parser.parse_effective_date("The bill has no timing clause.") is None


class TestLineNumberStripping:
    """Tests for removing legislative line numbers."""

    def test_strips_line_numbers(self, SAMPLE_WITH_LINE_NUMBERS: str) -> None:
        """Validate that sequential left-margin line numbers are stripped."""

        stripped = bill_parser.strip_line_numbers(SAMPLE_WITH_LINE_NUMBERS)
        assert stripped.startswith("HB25-1001\nA BILL FOR AN ACT")
        assert not stripped.splitlines()[0].startswith("1 ")

    def test_preserves_non_numbered(self, SAMPLE_FULL_BILL: str) -> None:
        """Validate that ordinary text without line numbers is unchanged."""

        assert bill_parser.strip_line_numbers(SAMPLE_FULL_BILL) == SAMPLE_FULL_BILL

    def test_stripped_text_still_parses(self, SAMPLE_WITH_LINE_NUMBERS: str) -> None:
        """Validate parser functions still work after line numbers are stripped."""

        stripped = bill_parser.strip_line_numbers(SAMPLE_WITH_LINE_NUMBERS)
        assert bill_parser.parse_bill_number(stripped) == "HB25-1001"
        assert bill_parser.parse_title(stripped) == (
            "Concerning The Regulation Of Emissions From Industrial Facilities."
        )


class TestFullBillParsing:
    """Tests for the full parse_bill orchestrator."""

    def test_parse_full_bill(self, tmp_path: Path, SAMPLE_FULL_BILL: str) -> None:
        """Validate that parse_bill returns a complete structured bill record."""

        extracted_path = _write_extracted_json(tmp_path, "HB25-1001", SAMPLE_FULL_BILL)
        parsed = bill_parser.parse_bill(str(extracted_path))

        assert set(parsed) == {
            "bill_number",
            "title",
            "sponsors",
            "sections",
            "crs_references",
            "effective_date",
            "appropriations",
            "metadata",
        }
        assert parsed["bill_number"] == "HB25-1001"
        assert parsed["title"].startswith("Concerning The Regulation Of Emissions")
        assert len(parsed["sections"]) == 4
        assert parsed["appropriations"]["has_appropriation"] is True
        assert parsed["metadata"]["source_file"] == "HB25-1001.pdf"

    def test_parse_full_bill_no_crash(self, tmp_path: Path) -> None:
        """Validate that parse_bill handles an empty extracted text payload."""

        extracted_path = _write_extracted_json(tmp_path, "empty", "")
        parsed = bill_parser.parse_bill(str(extracted_path))

        assert parsed["bill_number"] == "EMPTY"
        assert parsed["title"] == ""
        assert parsed["sections"] == []
        assert parsed["crs_references"] == []

    def test_parse_full_bill_garbage(self, tmp_path: Path) -> None:
        """Validate that parse_bill handles random non-bill text without crashing."""

        extracted_path = _write_extracted_json(
            tmp_path,
            "garbage",
            "random text with no legislative structure at all",
        )
        parsed = bill_parser.parse_bill(str(extracted_path))

        assert parsed["bill_number"] == "GARBAGE"
        assert parsed["title"] == ""
        assert parsed["sections"] == []
        assert parsed["effective_date"] is None

    def test_parse_produces_valid_structure(
        self,
        tmp_path: Path,
        SAMPLE_FULL_BILL: str,
    ) -> None:
        """Validate parsed output contains all required structural keys."""

        extracted_path = _write_extracted_json(tmp_path, "HB25-1001", SAMPLE_FULL_BILL)
        parsed = bill_parser.parse_bill(str(extracted_path))

        assert parsed["bill_number"]
        assert parsed["title"]
        assert isinstance(parsed["sponsors"], dict)
        assert isinstance(parsed["sections"], list)
        assert isinstance(parsed["crs_references"], list)
        assert {"source_file", "page_count", "parse_timestamp", "parser_version"} <= set(
            parsed["metadata"]
        )


class TestCrossReferenceConsistency:
    """Tests for consistency between section-level and bill-level CRS refs."""

    def test_section_refs_in_global_refs(
        self,
        tmp_path: Path,
        SAMPLE_FULL_BILL: str,
    ) -> None:
        """Validate every section CRS ref appears in top-level crs_references."""

        extracted_path = _write_extracted_json(tmp_path, "HB25-1001", SAMPLE_FULL_BILL)
        parsed = bill_parser.parse_bill(str(extracted_path))
        global_refs = set(parsed["crs_references"])

        for section in parsed["sections"]:
            for ref in section["crs_references"]:
                assert ref in global_refs

    def test_no_duplicate_refs(self, tmp_path: Path, SAMPLE_FULL_BILL: str) -> None:
        """Validate top-level CRS references are deduplicated."""

        extracted_path = _write_extracted_json(tmp_path, "HB25-1001", SAMPLE_FULL_BILL)
        parsed = bill_parser.parse_bill(str(extracted_path))

        assert len(parsed["crs_references"]) == len(set(parsed["crs_references"]))
