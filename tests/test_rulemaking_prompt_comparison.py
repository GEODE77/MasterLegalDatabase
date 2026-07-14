"""Tests for Geode vs Colorado Rulemaking Search prompt comparison helpers."""

from __future__ import annotations

from pathlib import Path

from geode.pipeline.rulemaking_prompt_comparison import (
    _citation_overlap,
    _official_flags,
    _official_result,
    _output_paths,
    _performance_status,
    _read_prompts,
)


def test_citation_overlap_matches_part_level_official_citations() -> None:
    """Base CCR citations overlap official part-level citations."""

    assert _citation_overlap(["6 CCR 1007-3"], ["6 CCR 1007-3 Part 262"]) == [
        "6 CCR 1007-3"
    ]


def test_official_result_captures_current_status_flags() -> None:
    """Official result rows preserve rule history and draft-rule signals."""

    result = _official_result(
        {
            "doc_CCR": "5 CCR 1001-5",
            "doc_simple_name": "REGULATION NUMBER 3",
            "doc_version": "123",
            "doc_effective_date": "01/14/2026",
            "doc_filing_type": "Permanent Rule",
            "doc_additional_versions": [{"doc_version": "124"}],
            "doc_draft_rules": [{"RuleName": "REGULATION NUMBER 3"}],
        }
    )

    assert result.ccr_citation == "5 CCR 1001-5"
    assert result.has_rule_history is True
    assert result.has_draft_rules is True
    assert result.has_newer_version_warning is True
    assert _official_flags([result]) == [
        "newer_version_available",
        "proposed_rule_change",
        "rule_history_available",
    ]


def test_performance_status_marks_geode_broader_when_official_is_empty() -> None:
    """Broad Geode results are not treated as failures when official search is empty."""

    status, issue, recommendation = _performance_status(
        geode_results=[object()],  # type: ignore[list-item]
        official_results=[],
        official_attempted=True,
        shared=[],
        geode_domains=["Air", "Water", "Waste"],
    )

    assert status == "geode_broader_than_official"
    assert issue is not None
    assert "narrower" in recommendation


def test_read_prompts_keeps_prompt_set_and_drops_feedback_footer(tmp_path: Path) -> None:
    """Prompt files are parsed as test prompts, not as instructions to the runner."""

    prompt_file = tmp_path / "prompts.txt"
    prompt_file.write_text(
        "\n\n".join(
            [
                "50 More Complex Colorado-Specific Geode Search Prompts",
                "A facility says it already has approval.",
                "Which current CCR rule controls the permit?",
                "Provide your feedback after each prompt.",
            ]
        ),
        encoding="utf-8",
    )

    assert _read_prompts(prompt_file) == [
        "A facility says it already has approval.",
        "Which current CCR rule controls the permit?",
    ]


def test_output_paths_allow_separate_pressure_test_reports() -> None:
    """Separate prompt sets can be saved without replacing earlier audits."""

    detail_name, summary_name, report_path = _output_paths("Complex 2026-07-09")

    assert detail_name == "rulemaking_search_prompt_comparison_complex_2026-07-09.jsonl"
    assert summary_name == "rulemaking_search_prompt_comparison_summary_complex_2026-07-09.json"
    assert report_path.as_posix() == (
        "docs/audits/RULEMAKING_SEARCH_PROMPT_COMPARISON_COMPLEX_2026-07-09.md"
    )
