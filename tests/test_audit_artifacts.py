"""Tests for audit remediation artifact generation."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.audit_artifacts import write_audit_artifacts


def test_audit_artifacts_write_gap_queues_and_boundaries(tmp_path: Path) -> None:
    """Audit artifact generation should track gaps without claiming authorization."""

    _write_audit_fixture(tmp_path)

    outputs = write_audit_artifacts(tmp_path, verify_raw_bytes=True)

    assert outputs["crs_authorization"] == "_CONTROL_PLANE/CRS_PUBLISHING_AUTHORIZATION.json"
    snapshot_queue = _read_json(tmp_path / "_CONTROL_PLANE" / "SNAPSHOT_BASELINE_BACKFILL_QUEUE.json")
    ccr_plan = _read_json(tmp_path / "_CONTROL_PLANE" / "CCR_COVERAGE_CLOSURE_PLAN.json")
    authorization = _read_json(tmp_path / "_CONTROL_PLANE" / "CRS_PUBLISHING_AUTHORIZATION.json")
    raw_verification = _read_json(
        tmp_path / "_CONTROL_PLANE" / "RAW_SOURCE_BYTE_IDENTICAL_VERIFICATION.json"
    )
    hardening = _read_json(
        tmp_path
        / "_CONTROL_PLANE"
        / "AUDIT_REPORTS"
        / "PERSONALIZATION_HARDENING_STATUS_2026-07-01.json"
    )

    assert snapshot_queue["missing_baseline_count"] == 1
    assert ccr_plan["ccr_regulations_uncovered"] == 1
    assert authorization["authorization_state"] == "not_authorized"
    assert outputs["route_conformance"].endswith("ROUTE_UI_UX_CONFORMANCE_2026-07-01.json")
    assert outputs["reference_decision"].endswith("REFERENCE_SITE_DECISION_2026-07-01.json")
    assert raw_verification["verification_status"] == "byte_identical"
    assert raw_verification["files_compared"] == 1
    assert hardening["overall_status"] == "design_defect_open"
    assert (tmp_path / "docs" / "templates" / "REVIEWER_ASSIGNMENT_TEMPLATE.md").exists()
    assert (tmp_path / "docs" / "personalization" / "DATA_HANDLING.md").exists()


def _write_audit_fixture(root: Path) -> None:
    control = root / "_CONTROL_PLANE"
    crosswalks = root / "_CROSSWALKS"
    ccr = root / "02_Regulations_CCR"
    app = root / "geode" / "web" / "src" / "app" / "app" / "dashboard"
    raw = root / "_RAW_ARCHIVE" / "crs"
    control.mkdir(parents=True)
    crosswalks.mkdir(parents=True)
    ccr.mkdir(parents=True)
    app.mkdir(parents=True)
    raw.mkdir(parents=True)
    (raw / "source.txt").write_text("raw", encoding="utf-8")
    (app / "page.tsx").write_text("export default function Page() { return null; }\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "design-principles.md").write_text("# Design\n", encoding="utf-8")
    _write_jsonl(
        control / "FULL_TEXT_DIFF.jsonl",
        [
            {
                "path": "01_Statutes_CRS/crs_title_01.md",
                "layer": "01_Statutes_CRS",
                "current_sha256": "abc",
                "diff_status": "no_prior_snapshot",
            }
        ],
    )
    _write_jsonl(
        ccr / "_index.jsonl",
        [
            {"id": "1_CCR_101-1", "title": "Covered"},
            {"id": "1_CCR_101-2", "title": "Uncovered"},
        ],
    )
    _write_jsonl(
        crosswalks / "regulation_to_statute.jsonl",
        [{"source_id": "1_CCR_101-1", "target_id": "CRS-1-1-101"}],
    )
    (crosswalks / "statute_to_regulation.jsonl").write_text("", encoding="utf-8")
    (crosswalks / "rulemaking_to_regulation.jsonl").write_text("", encoding="utf-8")
    (control / "REVIEWER_ASSIGNMENTS.json").write_text(
        json.dumps(
            {
                "assignments": [
                    {
                        "role_id": "data_reviewer",
                        "label": "Data Reviewer",
                        "assignment_status": "unassigned",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
