"""Tests for CCR rule history and rulemaking reconciliation backfill."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.rule_history_backfill import run_rule_history_backfill
from geode.utils.file_io import iter_jsonl


def test_rule_history_backfill_writes_version_and_reconciliation_outputs(
    project_root: Path,
) -> None:
    """Backfill applies to existing CCR records and existing Register notices."""

    records_dir = project_root / "02_Regulations_CCR" / "_normalized" / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    (records_dir / "5_CCR_1001-14.json").write_text(
        json.dumps(
            {
                "id": "5_CCR_1001-14",
                "ccr_citation": "5 CCR 1001-14",
                "title": "AIR QUALITY STANDARDS",
                "status": "active",
                "source_page_url": "https://www.sos.state.co.us/CCR/DisplayRule.do?ruleId=2347",
                "document_url": (
                    "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?"
                    "ruleVersionId=12357&fileName=5%20CCR%201001-14&type=pdf"
                ),
                "archive_raw_file_path": "_RAW_ARCHIVE/ccr/5_CCR_1001-14.pdf",
                "full_text": (
                    "Editor’s Notes\n"
                    "History\n"
                    "Rules V.A.1, VIII.II eff. 01/14/2026.\n"
                    "Rules V.A.1, VIII.GG eff. 02/14/2024.\n"
                ),
            }
        ),
        encoding="utf-8",
    )
    dataset_dir = project_root / "04_Rulemaking" / "_dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "rulemaking_notices.jsonl").write_text(
        json.dumps(
            {
                "id": "RM-2026-test",
                "notice_type": "adopted",
                "ccr_rule_affected": "5_CCR_1001-14",
                "ccr_citation": "5 CCR 1001-14",
                "publication_date": "2026-01-10",
                "effective_date": "2026-01-14",
                "source_url": (
                    "https://www.sos.state.co.us/CCR/RegisterContents.do?"
                    "publicationDay=01/10/2026"
                ),
                "source_path": "_RAW_ARCHIVE/register/register_2026-01-10.html",
                "source_evidence": "5 CCR 1001-14 adopted effective 01/14/2026",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = run_rule_history_backfill(project_root)

    versions = list(
        iter_jsonl(
            project_root
            / "02_Regulations_CCR"
            / "_history"
            / "ccr_rule_version_history.jsonl"
        )
    )
    reconciliation = list(
        iter_jsonl(
            project_root
            / "04_Rulemaking"
            / "_dataset"
            / "rulemaking_rule_version_reconciliation.jsonl"
        )
    )
    verification = list(iter_jsonl(project_root / "_CONTROL_PLANE" / "CURRENT_RULE_VERIFICATION.jsonl"))
    manifest = json.loads(
        (project_root / "_CONTROL_PLANE" / "MASTER_MANIFEST.json").read_text(encoding="utf-8")
    )
    rulemaking_layer = next(
        layer for layer in manifest["data_layers"] if layer["id"] == "04_Rulemaking"
    )

    assert summary.rules_considered == 1
    assert summary.rulemaking_notices_considered == 1
    assert summary.exact_effective_date_matches == 1
    assert any(row["version_id"] == "12357" for row in versions)
    assert any(row["event_kind"] == "editor_history" for row in versions)
    assert reconciliation[0]["match_method"] == "exact_effective_date"
    assert reconciliation[0]["matched_version_record_id"] == "5_CCR_1001-14_VER_12357"
    assert reconciliation[0]["matched_version_id"] == "12357"
    assert verification[0]["live_search_status"] == "pending_live_check"
    assert verification[0]["local_current_version_id"] == "12357"
    assert manifest["rule_history_backfill"]["reconciled_notices_total"] == 1
    assert "04_Rulemaking/_dataset/rulemaking_rule_version_reconciliation.jsonl" in rulemaking_layer[
        "derived_files"
    ]


def test_rule_history_backfill_handles_missing_local_rule_evidence(project_root: Path) -> None:
    """Existing Register notices are still represented when CCR version evidence is absent."""

    dataset_dir = project_root / "04_Rulemaking" / "_dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "rulemaking_notices.jsonl").write_text(
        json.dumps(
            {
                "id": "RM-2026-missing-rule",
                "notice_type": "proposed",
                "ccr_rule_affected": "5_CCR_1001-9",
                "ccr_citation": "5 CCR 1001-9",
                "publication_date": "2026-06-25",
                "source_url": (
                    "https://www.sos.state.co.us/CCR/RegisterContents.do?"
                    "publicationDay=06/25/2026"
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = run_rule_history_backfill(project_root)
    reconciliation = list(
        iter_jsonl(
            project_root
            / "04_Rulemaking"
            / "_dataset"
            / "rulemaking_rule_version_reconciliation.jsonl"
        )
    )

    assert summary.notices_without_rule_version_evidence == 1
    assert reconciliation[0]["status"] == "needs_version_history_source"
    assert reconciliation[0]["match_method"] == "no_local_version_evidence"
