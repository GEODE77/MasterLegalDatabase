"""Tests for the Step 1 readiness gate."""

from __future__ import annotations

import json
from pathlib import Path

from geode.constants import ALL_LAYERS
from geode.validation.step1_gate import (
    build_step1_readiness_report,
    write_step1_readiness_report,
)


def test_step1_gate_blocks_empty_layers(tmp_path: Path) -> None:
    """Step 1 is blocked when required layers have no structured records."""

    _write_manifest(tmp_path, record_count=0, status="empty")
    _write_empty_indexes(tmp_path)

    report = build_step1_readiness_report(tmp_path)

    assert not report.ready_for_step_2
    assert report.empty_layers == 7
    assert any("01_Statutes_CRS" in blocker for blocker in report.blockers)


def test_step1_gate_passes_when_all_layers_have_records_and_raw_sources(tmp_path: Path) -> None:
    """Step 1 passes only when each layer has indexed records and raw evidence."""

    _write_manifest(tmp_path, record_count=1, status="complete")
    _write_indexes(tmp_path)
    _write_raw_sources(tmp_path)

    report = write_step1_readiness_report(tmp_path)

    assert report.ready_for_step_2
    assert report.ready_layers == 7
    assert report.complete_layers == 7
    assert (tmp_path / "_CONTROL_PLANE" / "STEP1_READINESS_REPORT.json").exists()


def test_step1_gate_marks_starter_coverage_as_partial(tmp_path: Path) -> None:
    """Starter coverage is useful, but does not unlock Step 2 by itself."""

    _write_manifest(tmp_path, record_count=1, status="ready")
    _write_indexes(tmp_path)
    _write_raw_sources(tmp_path)

    report = build_step1_readiness_report(tmp_path)

    assert not report.ready_for_step_2
    assert report.ready_layers == 5
    assert report.partial_layers == 2
    assert {status.layer_id for status in report.layers if status.status_level == "partial"} == {
        "06_Session_Laws",
        "07_Supplementary",
    }


def _write_manifest(root: Path, *, record_count: int, status: str) -> None:
    """Write a minimal master manifest for Step 1 tests."""

    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True, exist_ok=True)
    layers = [
        {
            "id": layer,
            "record_count": record_count,
            "status": status,
        }
        for layer in ALL_LAYERS
    ]
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps({"data_layers": layers}),
        encoding="utf-8",
    )


def _write_empty_indexes(root: Path) -> None:
    """Create empty layer indexes."""

    for layer in ALL_LAYERS:
        layer_root = root / layer
        layer_root.mkdir(parents=True, exist_ok=True)
        (layer_root / "_index.jsonl").write_text("", encoding="utf-8")


def _write_indexes(root: Path) -> None:
    """Create one indexed record per layer."""

    for layer in ALL_LAYERS:
        layer_root = root / layer
        layer_root.mkdir(parents=True, exist_ok=True)
        (layer_root / "_index.jsonl").write_text(
            json.dumps({"id": f"{layer}-fixture"}) + "\n",
            encoding="utf-8",
        )


def _write_raw_sources(root: Path) -> None:
    """Create one source-like file in each raw archive area."""

    raw_dirs = [
        "_RAW_ARCHIVE/ccr",
        "_RAW_ARCHIVE/crs",
        "_RAW_ARCHIVE/edocket",
        "_RAW_ARCHIVE/exec_orders",
        "_RAW_ARCHIVE/legiscan",
        "_RAW_ARCHIVE/legiscan_documents",
        "_RAW_ARCHIVE/register",
        "_RAW_ARCHIVE/supplementary",
    ]
    for index, raw_dir in enumerate(raw_dirs, start=1):
        path = root / raw_dir
        path.mkdir(parents=True, exist_ok=True)
        (path / f"source_{index}.txt").write_text("source", encoding="utf-8")
