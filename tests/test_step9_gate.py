"""Tests for the Step 9 readiness gate."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.relationship_coverage import write_relationship_coverage
from geode.validation.step9_gate import build_step9_readiness_report, write_step9_readiness_report


def test_step9_gate_passes_with_relationship_coverage(tmp_path: Path) -> None:
    """Step 9 passes when relationship coverage and product access exist."""

    _write_step9_fixture(tmp_path)

    report = write_step9_readiness_report(tmp_path)

    assert report.ready_for_step_9_completion
    assert not report.blockers
    assert any(item.id == "STEP9-VISUAL-GRAPH" for item in report.deferred_items)
    assert (tmp_path / "_CONTROL_PLANE" / "STEP9_READINESS_REPORT.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "STEP9_DEFERRED_QUEUE.json").exists()


def test_step9_gate_blocks_without_relationship_coverage(tmp_path: Path) -> None:
    """Step 9 blocks when coverage has not been generated."""

    _write_step9_fixture(tmp_path, write_coverage=False)

    report = build_step9_readiness_report(tmp_path)

    assert not report.ready_for_step_9_completion
    assert any("Relationship coverage" in blocker for blocker in report.blockers)


def _write_step9_fixture(root: Path, *, write_coverage: bool = True) -> None:
    """Write a minimal Step 9-ready fixture."""

    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True)
    (control / "STEP8_READINESS_REPORT.json").write_text(
        json.dumps({"ready_for_step_8_completion": True}),
        encoding="utf-8",
    )
    _write_relationship_source_fixture(root)
    if write_coverage:
        write_relationship_coverage(root)
    _write_marker_file(
        root / "geode" / "web" / "src" / "app" / "api" / "product" / "relationships" / "route.ts",
        "getRelationshipCoverageReport relationshipCoverage",
    )
    _write_marker_file(
        root / "geode" / "web" / "src" / "app" / "app" / "relationships" / "page.tsx",
        "Relationship Health visual graph getRelationshipCoverageReport",
    )


def _write_relationship_source_fixture(root: Path) -> None:
    """Write minimal relationship source files for the gate fixture."""

    control = root / "_CONTROL_PLANE"
    crosswalks = root / "_CROSSWALKS"
    ccr = root / "02_Regulations_CCR"
    crosswalks.mkdir(parents=True, exist_ok=True)
    ccr.mkdir(parents=True, exist_ok=True)
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps(
            {
                "data_layers": [
                    {
                        "id": "02_Regulations_CCR",
                        "index_file": "02_Regulations_CCR/_index.jsonl",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (ccr / "_index.jsonl").write_text(json.dumps({"id": "1_CCR_101-1"}) + "\n", encoding="utf-8")
    (crosswalks / "regulation_to_statute.jsonl").write_text(
        json.dumps(
            {
                "source_id": "1_CCR_101-1",
                "target_id": "CRS-1-1-101",
                "relationship": "cites",
                "confidence": 0.75,
                "source_evidence": "Authority cites CRS 1-1-101.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    for name in [
        "statute_to_regulation.jsonl",
        "rulemaking_to_regulation.jsonl",
        "bill_to_statute.jsonl",
        "agency_to_statute.jsonl",
        "amendment_history.jsonl",
    ]:
        (crosswalks / name).write_text("", encoding="utf-8")


def _write_marker_file(path: Path, content: str) -> None:
    """Write one marker file for Step 9 gate tests."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
