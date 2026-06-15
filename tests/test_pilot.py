"""Phase 4 pilot readiness helper tests."""

from __future__ import annotations

from pathlib import Path

from geode.pipeline.pilot import (
    generate_quality_report,
    load_pilot_test_set,
    pilot_rules_to_ccr_entries,
    select_pilot_set,
    summarize_pilot_test_set,
    validate_pilot_test_set,
)

EXPECTED_CCR_NUMBERS = [
    "5 CCR 1001-5",
    "5 CCR 1001-9",
    "6 CCR 1007-2",
    "1 CCR 201-2",
    "1 CCR 201-4",
    "7 CCR 1103-1",
    "7 CCR 1103-7",
    "2 CCR 502-1",
    "12 CCR 2509-2",
    "3 CCR 716-1",
    "4 CCR 801-1",
    "2 CCR 404-1",
    "8 CCR 1202-10",
    "1 CCR 301-39",
    "8 CCR 1507-1",
]


def test_load_canonical_pilot_test_set(project_root: Path) -> None:
    """Canonical pilot data contains the 15 source CCR numbers."""

    rules = load_pilot_test_set(project_root)
    assert len(rules) == 15
    assert [rule.ccr_number for rule in rules] == EXPECTED_CCR_NUMBERS


def test_validate_canonical_pilot_tags_and_urls(project_root: Path) -> None:
    """Pilot URLs and controlled ontology hints validate cleanly."""

    rules = load_pilot_test_set(project_root)
    result = validate_pilot_test_set(rules, root=project_root)
    assert result.valid, [issue.message for issue in result.issues]
    for rule in rules:
        url = str(rule.sos_rule_info_url)
        assert url.startswith("https://www.sos.state.co.us/CCR/DisplayRule.do")
        assert rule.canonical_id == rule.ccr_number.replace(" ", "_")


def test_summarize_pilot_test_set_counts(project_root: Path) -> None:
    """Pilot summary counts match the canonical Phase 4A distribution."""

    rules = load_pilot_test_set(project_root)
    summary = summarize_pilot_test_set(rules)
    assert summary["by_department"]["Department of Public Health and Environment"] == 3
    assert summary["by_format_status"] == {
        "confirmed_docx_pdf": 8,
        "expected_docx_pdf": 7,
    }
    assert summary["by_size_label"] == {
        "large": 6,
        "medium": 6,
        "short": 2,
        "very_large": 1,
    }


def test_pilot_rules_to_ccr_entries(project_root: Path) -> None:
    """Pilot rules convert to CCR downloader handoff dictionaries."""

    rules = load_pilot_test_set(project_root)
    entries = pilot_rules_to_ccr_entries(rules)
    assert len(entries) == 15
    assert entries[0]["ccr_number"] == "5 CCR 1001-5"
    assert entries[0]["canonical_id"] == "5_CCR_1001-5"
    assert entries[0]["docx_url"] is None
    assert entries[0]["pdf_url"] is None
    assert entries[0]["source_page_url"].endswith("action=ruleinfo&ruleId=2337")


def test_select_pilot_set_balances_departments_and_formats() -> None:
    """Pilot selection returns 10-15 records across target departments."""

    departments = [
        "Department of Public Health and Environment",
        "Department of Labor and Employment",
        "Department of Natural Resources",
        "Department of Regulatory Agencies",
        "Department of Revenue",
    ]
    rules = []
    for index, department in enumerate(departments * 3, start=1):
        rules.append(
            {
                "ccr_number": f"5 CCR 1001-{index}",
                "department": department,
                "agency": department,
                "docx_url": "https://example.test/rule.docx" if index % 2 else None,
                "pdf_url": "https://example.test/rule.pdf",
            }
        )
    report = select_pilot_set(rules)
    assert 10 <= len(report.selected) <= 15
    assert report.has_docx
    assert report.has_pdf
    assert len(report.by_bucket) == 5


def test_generate_quality_report_flags_low_auto_accept_rate() -> None:
    """Quality report computes Phase 4E metrics and recommendations."""

    records = [
        {
            "route": "auto_accept",
            "confidence": 0.9,
            "conversion_path": "path_1_docx",
            "seconds": 10,
            "api_cost_usd": 0.01,
        },
        {
            "route": "quarantine",
            "confidence": 0.4,
            "conversion_path": "path_2_pdf_markitdown",
            "seconds": 20,
            "api_cost_usd": 0.02,
            "errors": ["citation_miss"],
        },
    ]
    report = generate_quality_report(records)
    assert report.processed == 2
    assert report.auto_accept_rate == 0.5
    assert report.common_errors == {"citation_miss": 1}
    assert report.recommendations
