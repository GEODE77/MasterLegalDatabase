"""Shared pytest fixtures for Project Geode tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from geode.pipeline.writer import ensure_project_structure
from scripts.generate_sample_data import (
    SAMPLE_BILLS,
    add_line_numbers,
    build_unnumbered_bill_lines,
    ensure_realistic_length,
)

SECTION_SYMBOL = "\u00a7"


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """Create an isolated Geode project root for tests."""

    ensure_project_structure(tmp_path)
    control = tmp_path / "_CONTROL_PLANE"
    control.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).parents[1]
    for name in (
        "MASTER_SCHEMA.json",
        "ONTOLOGY.json",
        "AGENCY_REGISTRY.json",
        "SOURCE_REGISTRY.json",
        "MASTER_MANIFEST.json",
        "PILOT_TEST_SET.json",
    ):
        shutil.copyfile(repo_root / "_CONTROL_PLANE" / name, control / name)
    (control / "UPDATE_LOG.jsonl").write_text("", encoding="utf-8")
    (control / "MASTER_TIMELINE_INDEX.jsonl").write_text("", encoding="utf-8")
    for layer in (
        "01_Statutes_CRS",
        "02_Regulations_CCR",
        "03_Legislation",
        "04_Rulemaking",
        "05_Executive_Orders",
        "06_Session_Laws",
        "07_Supplementary",
    ):
        (tmp_path / layer).mkdir(parents=True, exist_ok=True)
        (tmp_path / layer / "_index.jsonl").write_text("", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def crs_fixture_path() -> Path:
    """Return the CRS fixture path."""

    return Path(__file__).parent / "fixtures" / "crs" / "crs_title_25_fixture.txt"


@pytest.fixture()
def legiscan_fixture_path() -> Path:
    """Return the LegiScan bill fixture path."""

    return Path(__file__).parent / "fixtures" / "legiscan" / "sb23_016.json"


def _sample_bill_config(bill_number: str) -> dict:
    """Return one generated sample bill configuration by bill number."""

    for config in SAMPLE_BILLS:
        if config["bill_number"] == bill_number:
            return config
    raise KeyError(f"unknown sample bill: {bill_number}")


def _sample_bill_text(bill_number: str, numbered: bool = False) -> str:
    """Build sample bill text from the canonical sample-data definitions."""

    config = _sample_bill_config(bill_number)
    lines = ensure_realistic_length(build_unnumbered_bill_lines(config), config)
    if numbered:
        return add_line_numbers(lines)
    return "\n".join(lines).rstrip()


@pytest.fixture(name="SAMPLE_BILL_HEADER")
def fixture_sample_bill_header() -> str:
    """Return a realistic HB25-1001 header with sponsors and title."""

    return """
HOUSE BILL 25-1001

BY REPRESENTATIVE(S) Smith, Garcia, and Thompson;
also SENATOR(S) Williams.

CONCERNING THE REGULATION OF EMISSIONS FROM INDUSTRIAL FACILITIES.

Bill Summary
The bill requires industrial facilities to monitor air emissions.
"""


@pytest.fixture(name="SAMPLE_ENACTING_CLAUSE")
def fixture_sample_enacting_clause() -> str:
    """Return the standard Colorado bill enacting clause."""

    return "BE IT ENACTED BY THE GENERAL ASSEMBLY OF THE STATE OF COLORADO:"


@pytest.fixture(name="SAMPLE_SECTIONS")
def fixture_sample_sections() -> str:
    """Return four HB25-1001 sections covering amend, add, and effective date."""

    return f"""
SECTION 1.
{SECTION_SYMBOL} 25-7-114.7, C.R.S., is amended to read:
(1) The division shall establish emission monitoring requirements.
(2) Each covered industrial facility shall report emissions quarterly.
(3) As used in this section:
(a) 'stationary source' means a building, structure, facility, or installation.

SECTION 2.
{SECTION_SYMBOL} 25-7-114.8, C.R.S., is amended to read:
(1) The industrial emissions compliance fund is created in the state treasury.
(2) The fund consists of fees, gifts, grants, and $2,500,000 transferred for the
2025-26 fiscal year.

SECTION 3.
{SECTION_SYMBOL} 25-8-205, C.R.S., is amended BY THE ADDITION OF A NEW
SUBSECTION to read:
(7) A permit for an industrial discharge must include monitoring conditions.
(8) The division shall coordinate air quality and water quality inspections.

SECTION 4. Effective date.
This act takes effect July 1, 2025.
"""


@pytest.fixture(name="SAMPLE_EFFECTIVE_DATE")
def fixture_sample_effective_date() -> str:
    """Return the HB25-1001 effective-date section."""

    return "SECTION 4. Effective date. This act takes effect July 1, 2025."


@pytest.fixture(name="SAMPLE_APPROPRIATION")
def fixture_sample_appropriation() -> str:
    """Return an HB25-1001 appropriation section."""

    return """
SECTION 5. Appropriation.
For the 2025-26 state fiscal year, $500,000 is appropriated from the General
Fund to the department of public health and environment for implementation of
this act and related information technology costs.
"""


@pytest.fixture(name="SAMPLE_FULL_BILL")
def fixture_sample_full_bill() -> str:
    """Return the complete unnumbered HB25-1001 sample bill text."""

    return _sample_bill_text("HB25-1001")


@pytest.fixture(name="SAMPLE_LABOR_BILL")
def fixture_sample_labor_bill() -> str:
    """Return the complete unnumbered SB25-0055 sample labor bill text."""

    return _sample_bill_text("SB25-0055")


@pytest.fixture(name="SAMPLE_TAX_BILL")
def fixture_sample_tax_bill() -> str:
    """Return the complete unnumbered HB25-1099 sample tax bill text."""

    return _sample_bill_text("HB25-1099")


@pytest.fixture(name="SAMPLE_WITH_LINE_NUMBERS")
def fixture_sample_with_line_numbers() -> str:
    """Return the HB25-1001 sample bill with sequential margin line numbers."""

    return _sample_bill_text("HB25-1001", numbered=True)


@pytest.fixture(name="SAMPLE_BILL_TEXTS")
def fixture_sample_bill_texts() -> dict[str, str]:
    """Return all five canonical sample bills as unnumbered bill text."""

    return {
        str(config["bill_number"]): _sample_bill_text(str(config["bill_number"]))
        for config in SAMPLE_BILLS
    }
