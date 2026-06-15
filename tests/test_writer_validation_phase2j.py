"""Phase 2J-2K writer and validation contract tests."""

from __future__ import annotations

from pathlib import Path

from geode.pipeline.writer import write_record, write_to_quarantine
from geode.utils.file_io import iter_jsonl
from geode.validation.checks import check_text_integrity, run_all_checks
from geode.validation.integrity import (
    check_crosswalk_completeness,
    check_dead_crosswalks,
    check_orphan_regulations,
    check_summary_coverage,
    check_tag_coverage,
    run_integrity_check,
)


def _regulation_record() -> dict:
    """Return a valid regulation-style fixture record."""

    return {
        "entity_type": "regulation_rule",
        "id": "5_CCR_1001-9",
        "ccr_number": "5 CCR 1001-9",
        "title": "Air Quality Control Commission Regulation 9",
        "department": "Public Health and Environment",
        "department_code": "5",
        "agency": "Colorado Department of Public Health and Environment",
        "agency_code": "CDPHE_DEPT",
        "enabling_statutes": ["CRS-25-7-109"],
        "effective_date": "2024-01-01",
        "status": "active",
        "full_text": "The commission may issue permits under 25-7-109, C.R.S.",
        "chunk_level_3_summary": "The commission may issue permits.",
        "subject_tags": ["air_quality"],
        "industry_tags": ["manufacturing"],
        "compliance_keywords": ["permit_required"],
        "source_url": "https://www.sos.state.co.us/CCR/Welcome.do",
        "source_format": "docx",
        "extraction_method": "fixture",
        "confidence": {"overall": 0.91},
        "source_path": "_RAW_ARCHIVE/ccr/5_CCR_1001-9.docx",
        "crosswalks": [
            {
                "file": "regulation_to_statute.jsonl",
                "record": {
                    "entity_type": "crosswalk_entry",
                    "source_id": "5_CCR_1001-9",
                    "source_type": "regulation_rule",
                    "target_id": "CRS-25-7-109",
                    "target_type": "statute_section",
                    "relationship": "authorized_by",
                    "confidence": 0.9,
                    "source_evidence": "25-7-109, C.R.S.",
                    "data_retrieved": "2026-06-12",
                },
            }
        ],
        "timeline_events": [
            {
                "id": "TE-2024-01-01-001",
                "date": "2024-01-01",
                "event_type": "rule_effective",
                "entity_id": "5_CCR_1001-9",
                "entity_type": "regulation_rule",
                "description": "Regulation 9 effective.",
                "affects": ["CRS-25-7-109"],
                "layer": "02_Regulations_CCR",
                "file_path": "02_Regulations_CCR/_index.jsonl",
            }
        ],
    }


def _layer_config(project_root: Path) -> dict:
    """Return generic writer config for a CCR department file."""

    return {
        "root": project_root,
        "layer": "02_Regulations_CCR",
        "content_path": "02_Regulations_CCR/ccr_dept_public_health.md",
        "meta_path": "02_Regulations_CCR/_meta/ccr_dept_public_health_meta.jsonl",
    }


def test_run_all_checks_accepts_valid_record(project_root: Path) -> None:
    """All six ingestion checks pass for a valid fixture record."""

    result = run_all_checks(_regulation_record(), project_root)
    assert result.valid, result.issues


def test_text_integrity_hallucination_canary(project_root: Path) -> None:
    """The hallucination canary rejects summary citations absent from full text."""

    record = _regulation_record()
    record["chunk_level_3_summary"] = "The rule is required by CRS-99-1-1."
    result = check_text_integrity(record)
    assert not result.valid
    assert "summary cites absent statute" in result.issues[0].message


def test_write_record_creates_all_seven_outputs(project_root: Path) -> None:
    """Generic writer creates content, metadata, index, crosswalk, timeline, log, manifest."""

    result = write_record(_regulation_record(), _layer_config(project_root))
    assert result.success
    assert len(result.output_paths) == 7
    for output_path in result.output_paths:
        assert (project_root / output_path).exists()
    assert len(list(iter_jsonl(project_root / "02_Regulations_CCR" / "_index.jsonl"))) == 1
    assert len(list(iter_jsonl(project_root / "_CONTROL_PLANE" / "UPDATE_LOG.jsonl"))) == 1


def test_write_record_rolls_back_on_failure(project_root: Path) -> None:
    """A forced failure restores files written earlier in the transaction."""

    config = _layer_config(project_root)
    config["fail_after_step"] = 3
    try:
        write_record(_regulation_record(), config)
    except RuntimeError:
        pass
    else:
        raise AssertionError("forced writer failure did not raise")
    assert not (project_root / "02_Regulations_CCR" / "ccr_dept_public_health.md").exists()
    assert not list(iter_jsonl(project_root / "02_Regulations_CCR" / "_index.jsonl"))


def test_write_to_quarantine_records_failed_payload(project_root: Path) -> None:
    """Quarantine writer appends failed records without touching raw archive."""

    path = write_to_quarantine(
        {"id": "bad", "layer": "02_Regulations_CCR", "source_path": "fixture"},
        "schema failure",
        project_root,
    )
    rows = list(iter_jsonl(path))
    assert rows[0]["reason"] == "schema failure"


def test_named_integrity_checks_run_on_empty_project(project_root: Path) -> None:
    """Monthly integrity check entry points run without special setup."""

    checks = [
        check_orphan_regulations,
        check_dead_crosswalks,
        check_tag_coverage,
        check_summary_coverage,
        check_crosswalk_completeness,
    ]
    for check in checks:
        assert check(project_root).valid
    assert run_integrity_check(project_root).valid
