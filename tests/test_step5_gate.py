"""Tests for the Step 5 readiness gate."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.reliance_policy import write_reliance_policy
from geode.validation.step5_gate import (
    build_step5_readiness_report,
    write_step5_readiness_report,
)


def test_step5_gate_passes_with_reliance_policy_api_and_ui(tmp_path: Path) -> None:
    """Step 5 passes when policy, API, and UI are present."""

    _write_step5_fixture(tmp_path)

    report = write_step5_readiness_report(tmp_path)

    assert report.ready_for_step_5_completion
    assert not report.blockers
    assert any(item.id == "STEP5-WORK-PACKETS" for item in report.deferred_items)
    assert (tmp_path / "_CONTROL_PLANE" / "STEP5_READINESS_REPORT.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "STEP5_DEFERRED_QUEUE.json").exists()


def test_step5_gate_blocks_without_policy(tmp_path: Path) -> None:
    """Step 5 blocks when the policy is missing."""

    _write_step5_fixture(tmp_path, write_policy=False)

    report = build_step5_readiness_report(tmp_path)

    assert not report.ready_for_step_5_completion
    assert any("Reliance policy" in blocker for blocker in report.blockers)


def _write_step5_fixture(root: Path, *, write_policy: bool = True) -> None:
    """Write a minimal Step 5-ready fixture."""

    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True)
    (control / "STEP4_READINESS_REPORT.json").write_text(
        json.dumps({"ready_for_step_4_completion": True}),
        encoding="utf-8",
    )
    if write_policy:
        write_reliance_policy(root)
    _write_marker_file(
        root / "geode" / "web" / "src" / "app" / "api" / "product" / "reliance-policy" / "route.ts",
        "getReliancePolicy policy",
    )
    _write_marker_file(
        root / "geode" / "web" / "src" / "app" / "app" / "reliance-policy" / "page.tsx",
        "Reliance Policy reviewerRoles external reliance",
    )


def _write_marker_file(path: Path, content: str) -> None:
    """Write one marker file for Step 5 gate tests."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
