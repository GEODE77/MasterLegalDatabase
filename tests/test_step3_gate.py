"""Tests for the Step 3 readiness gate."""

from __future__ import annotations

import json
from pathlib import Path

from geode.validation.step3_gate import (
    build_step3_readiness_report,
    write_step3_readiness_report,
)


def test_step3_gate_passes_when_review_foundation_is_decision_aware(tmp_path: Path) -> None:
    """Step 3 passes when backend review evidence is ready."""

    _write_step3_fixture(tmp_path)

    report = write_step3_readiness_report(tmp_path)

    assert report.ready_for_step_3_completion
    assert not report.blockers
    assert any(item.id == "STEP3-RU-DECISIONS" for item in report.deferred_items)
    assert (tmp_path / "_CONTROL_PLANE" / "STEP3_READINESS_REPORT.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "STEP3_DEFERRED_QUEUE.json").exists()


def test_step3_gate_blocks_without_step2_report(tmp_path: Path) -> None:
    """Step 3 is blocked when Step 2 has not been marked complete."""

    _write_step3_fixture(tmp_path, step2_ready=False)

    report = build_step3_readiness_report(tmp_path)

    assert not report.ready_for_step_3_completion
    assert any("Step 2 gate" in blocker or "Step 2" in blocker for blocker in report.blockers)


def _write_step3_fixture(root: Path, *, step2_ready: bool = True) -> None:
    """Write a minimal Step 3-ready fixture."""

    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True)
    if step2_ready:
        (control / "STEP2_READINESS_REPORT.json").write_text(
            json.dumps({"ready_for_step_2_completion": True}),
            encoding="utf-8",
        )

    meta = root / "02_Regulations_CCR" / "_meta"
    meta.mkdir(parents=True)
    (meta / "rule_units_review_queue.jsonl").write_text(
        json.dumps({"review_id": "RUR-1", "rule_unit_id": "RU-1"}) + "\n",
        encoding="utf-8",
    )
    (meta / "rule_units_review_summary.json").write_text(
        json.dumps({"pending_items": 1}),
        encoding="utf-8",
    )
    (meta / "rule_units_apply_proposal.json").write_text(
        json.dumps({"ready_to_apply": True, "changes": []}),
        encoding="utf-8",
    )
