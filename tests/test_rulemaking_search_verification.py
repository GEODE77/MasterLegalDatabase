"""Tests for Colorado Rulemaking Search verification readiness."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.rulemaking_search_verification import run_rulemaking_search_verification
from geode.utils.file_io import iter_jsonl


def test_rulemaking_search_verification_prepares_without_official_snapshot(
    project_root: Path,
) -> None:
    """The workflow writes comparison scaffolding before an official export exists."""

    _write_geode_rule(project_root)

    summary = run_rulemaking_search_verification(project_root)
    comparisons = list(
        iter_jsonl(
            project_root
            / "04_Rulemaking"
            / "_verification"
            / "rulemaking_search_comparison.jsonl"
        )
    )

    assert summary.official_snapshot_loaded is False
    assert summary.awaiting_official_snapshot == 1
    assert comparisons[0]["status"] == "awaiting_official_snapshot"
    assert (
        project_root / "04_Rulemaking" / "_verification" / "rulemaking_search_snapshot_template.csv"
    ).exists()
    assert (
        project_root / "_CONTROL_PLANE" / "COLORADO_RULEMAKING_SEARCH_VERIFICATION.json"
    ).exists()


def test_rulemaking_search_verification_matches_official_snapshot(
    project_root: Path,
) -> None:
    """Official snapshot rows are matched to local CCR and rulemaking records."""

    _write_geode_rule(project_root)
    dataset_dir = project_root / "04_Rulemaking" / "_dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "rulemaking_notices.jsonl").write_text(
        json.dumps(
            {
                "id": "RM-2026-test",
                "notice_type": "adopted",
                "ccr_rule_affected": "5_CCR_1001-14",
                "ccr_citation": "5 CCR 1001-14",
                "effective_date": "2026-01-14",
                "publication_date": "2026-01-10",
                "edocket_tracking_number": "2025-00999",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    snapshot_path = project_root / "official_rulemaking_search.jsonl"
    snapshot_path.write_text(
        json.dumps(
            {
                "ccr_citation": "5 CCR 1001-14",
                "rule_title": "Air Quality Standards",
                "agency": "Air Quality Control Commission",
                "rulemaking_status": "Adopted",
                "effective_date": "2026-01-14",
                "publication_date": "2026-01-10",
                "edocket_tracking_number": "2025-00999",
                "source_url": "https://rulemaking.colorado.gov/rulemaking-search",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = run_rulemaking_search_verification(project_root, snapshot_path)
    comparisons = list(
        iter_jsonl(
            project_root
            / "04_Rulemaking"
            / "_verification"
            / "rulemaking_search_comparison.jsonl"
        )
    )
    normalized = list(
        iter_jsonl(
            project_root
            / "04_Rulemaking"
            / "_verification"
            / "colorado_rulemaking_search_snapshot_normalized.jsonl"
        )
    )

    assert summary.official_snapshot_loaded is True
    assert summary.official_match_found == 1
    assert comparisons[0]["status"] == "official_match_found"
    assert comparisons[0]["strongest_match_method"] == "exact_tracking_number"
    assert normalized[0]["parent_regulation_id"] == "5_CCR_1001-14"


def test_rulemaking_search_verification_flags_official_rule_missing_from_geode(
    project_root: Path,
) -> None:
    """Official records outside the local CCR index are sent to review."""

    snapshot_path = project_root / "official_rulemaking_search.csv"
    snapshot_path.write_text(
        (
            "ccr_citation,rule_title,agency,rulemaking_status,effective_date\n"
            "5 CCR 1001-99,Missing Rule,Air Quality Control Commission,Adopted,2026-01-14\n"
        ),
        encoding="utf-8",
    )

    summary = run_rulemaking_search_verification(project_root, snapshot_path)
    comparisons = list(
        iter_jsonl(
            project_root
            / "04_Rulemaking"
            / "_verification"
            / "rulemaking_search_comparison.jsonl"
        )
    )

    assert summary.missing_geode_rule == 1
    assert comparisons[0]["status"] == "missing_geode_rule"
    assert "manual_review" in comparisons[0]["status_flags"]


def _write_geode_rule(project_root: Path) -> None:
    """Write one local CCR index row."""

    (project_root / "02_Regulations_CCR" / "_index.jsonl").write_text(
        json.dumps(
            {
                "id": "5_CCR_1001-14",
                "layer": "02_Regulations_CCR",
                "entity_type": "regulation_rule",
                "title": "Air Quality Standards",
                "citation": "5 CCR 1001-14",
                "path": "02_Regulations_CCR/_normalized/records/5_CCR_1001-14.json",
                "source_url": "https://www.sos.state.co.us/CCR/DisplayRule.do?ruleId=2347",
            }
        )
        + "\n",
        encoding="utf-8",
    )
