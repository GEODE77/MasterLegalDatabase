"""Tests for the Step 2 readiness gate."""

from __future__ import annotations

import json
from pathlib import Path

from geode.validation.step2_gate import (
    build_step2_readiness_report,
    write_step2_readiness_report,
)
from geode.web.index import build_index


def test_step2_gate_passes_with_index_search_detail_and_rule_units(tmp_path: Path) -> None:
    """Step 2 passes when retrieval, details, and requirement evidence are available."""

    root = _prepare_step2_fixture(tmp_path)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"

    report = write_step2_readiness_report(root, database_path)

    assert report.ready_for_step_2_completion
    assert not report.blockers
    assert any(item.id == "STEP2-RU-REVIEW" for item in report.deferred_items)
    assert (root / "_CONTROL_PLANE" / "STEP2_READINESS_REPORT.json").exists()
    assert (root / "_CONTROL_PLANE" / "STEP2_DEFERRED_QUEUE.json").exists()


def test_step2_gate_blocks_when_read_index_is_missing(tmp_path: Path) -> None:
    """Step 2 is blocked when the read database has not been built."""

    root = _prepare_step2_fixture(tmp_path, build_database=False)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"

    report = build_step2_readiness_report(root, database_path)

    assert not report.ready_for_step_2_completion
    assert any("database is missing" in blocker for blocker in report.blockers)


def _prepare_step2_fixture(root: Path, *, build_database: bool = True) -> Path:
    """Create a minimal Step 2-ready fixture."""

    _write_operational_fixture_corpus(root)
    _write_step1_report(root)
    _write_rule_units(root)
    if build_database:
        build_index(
            root=root,
            database_path=root / "data" / "structured_output" / "commons.sqlite3",
            rebuild=True,
        )
    return root


def _write_operational_fixture_corpus(root: Path) -> Path:
    """Write a tiny corpus with exact citation and operational search coverage."""

    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True)
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps({"project": "Geode", "fixture": True}),
        encoding="utf-8",
    )
    (control / "MASTER_TIMELINE_INDEX.jsonl").write_text("", encoding="utf-8")

    statutes = root / "01_Statutes_CRS"
    statutes.mkdir()
    (statutes / "crs_title_25.md").write_text(
        "\n".join(
            [
                "---",
                "id: CRS-25-7-109",
                "citation: CRS 25-7-109",
                "title: Air quality authority",
                "---",
                "The commission may adopt air quality rules for industrial facilities.",
            ]
        ),
        encoding="utf-8",
    )
    (statutes / "crs_title_42.md").write_text(
        "\n".join(
            [
                "---",
                "id: CRS-42-2-107",
                "citation: CRS 42-2-107",
                "title: Repair permit application",
                "---",
                "A repair permit application must be filed before the license is issued.",
            ]
        ),
        encoding="utf-8",
    )
    (statutes / "_index.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "CRS-25-7-109",
                        "entity_type": "statute_section",
                        "citation": "CRS 25-7-109",
                        "title": "Air quality authority",
                        "content_path": "01_Statutes_CRS/crs_title_25.md",
                        "source_url": "https://example.test/statute",
                        "confidence": 0.9,
                        "publication_year": 2026,
                    }
                ),
                json.dumps(
                    {
                        "id": "CRS-42-2-107",
                        "entity_type": "statute_section",
                        "citation": "CRS 42-2-107",
                        "title": "Repair permit application",
                        "content_path": "01_Statutes_CRS/crs_title_42.md",
                        "source_url": "https://example.test/driver-permit",
                        "confidence": 0.9,
                        "publication_year": 2026,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    regulations = root / "02_Regulations_CCR"
    rules = regulations / "_rules"
    rules.mkdir(parents=True)
    (rules / "5_CCR_1001-9.md").write_text(
        "\n".join(
            [
                "---",
                "id: 5_CCR_1001-9",
                "citation: 5 CCR 1001-9",
                "title: Air emissions permitting",
                "---",
                "A manufacturing facility shall obtain an air emissions permit before operating.",
                "The facility must keep records and report emissions to the division.",
            ]
        ),
        encoding="utf-8",
    )
    (regulations / "_index.jsonl").write_text(
        json.dumps(
            {
                "id": "5_CCR_1001-9",
                "entity_type": "regulation_rule",
                "citation": "5 CCR 1001-9",
                "title": "Air emissions permitting",
                "path": "02_Regulations_CCR/_rules/5_CCR_1001-9.md",
                "source_url": "https://example.test/rule",
                "confidence": 0.88,
                "publication_year": 2026,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    crosswalks = root / "_CROSSWALKS"
    crosswalks.mkdir()
    (crosswalks / "regulation_to_statute.jsonl").write_text(
        json.dumps(
            {
                "source_id": "5_CCR_1001-9",
                "target_id": "CRS-25-7-109",
                "target_type": "statute_section",
                "relationship": "authorized_by",
                "confidence": 0.9,
                "source_evidence": "Authority for air emissions permitting.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def _write_step1_report(root: Path) -> None:
    """Write a minimal clean Step 1 report."""

    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True, exist_ok=True)
    (control / "STEP1_READINESS_REPORT.json").write_text(
        json.dumps({"ready_for_step_2": True}),
        encoding="utf-8",
    )


def _write_rule_units(root: Path) -> None:
    """Write one validated rule unit for the requirement foundation."""

    meta = root / "02_Regulations_CCR" / "_meta"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "rule_units.jsonl").write_text(
        json.dumps(
            {
                "id": "RU-5-CCR-1001-9-001",
                "parent_regulation_id": "5_CCR_1001-9",
                "rule_type": "permit",
                "action_required": "Obtain an air emissions permit before operating.",
                "confidence": {"overall": 0.9},
                "source_section": "5 CCR 1001-9",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (meta / "rule_units_review_summary.json").write_text(
        json.dumps({"pending_items": 1}),
        encoding="utf-8",
    )
