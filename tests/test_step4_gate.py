"""Tests for the Step 4 readiness gate."""

from __future__ import annotations

import json
from pathlib import Path

from geode.validation.step4_gate import (
    build_step4_readiness_report,
    write_step4_readiness_report,
)


def test_step4_gate_passes_with_packet_handoff(tmp_path: Path) -> None:
    """Step 4 passes when backend packet data is present."""

    _write_step4_fixture(tmp_path)

    report = write_step4_readiness_report(tmp_path)

    assert report.ready_for_step_4_completion
    assert not report.blockers
    assert any(item.id == "STEP4-PACKET-REVIEW" for item in report.deferred_items)
    assert (tmp_path / "_CONTROL_PLANE" / "STEP4_READINESS_REPORT.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "STEP4_DEFERRED_QUEUE.json").exists()


def test_step4_gate_blocks_when_packets_do_not_match_queue(tmp_path: Path) -> None:
    """Step 4 blocks when review packets are missing."""

    _write_step4_fixture(tmp_path, write_packets=False)

    report = build_step4_readiness_report(tmp_path)

    assert not report.ready_for_step_4_completion
    assert any("does not match queue count" in blocker for blocker in report.blockers)


def _write_step4_fixture(root: Path, *, write_packets: bool = True) -> None:
    """Write a minimal Step 4-ready fixture."""

    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True)
    (control / "STEP3_READINESS_REPORT.json").write_text(
        json.dumps({"ready_for_step_3_completion": True}),
        encoding="utf-8",
    )
    meta = root / "02_Regulations_CCR" / "_meta"
    meta.mkdir(parents=True)
    (meta / "rule_units_review_queue.jsonl").write_text(
        json.dumps({"review_id": "RUR-1", "rule_unit_id": "RU-1"}) + "\n",
        encoding="utf-8",
    )
    if write_packets:
        (meta / "rule_units_review_packets.jsonl").write_text(
            json.dumps({"packet_id": "RUP-RUR-1", "review_id": "RUR-1"}) + "\n",
            encoding="utf-8",
        )
    (meta / "rule_units_review_packets_summary.json").write_text(
        json.dumps(
            {
                "pending": 1,
                "reliance_boundary": (
                    "This packet is not legal advice and does not change canonical law."
                ),
            }
        ),
        encoding="utf-8",
    )
