"""Tests for formal rule-unit review packets."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.review_packets import build_review_packets, write_review_packets


def test_review_packets_merge_queue_decisions_and_apply_proposal(tmp_path: Path) -> None:
    """Review packets preserve source evidence and decision state."""

    _write_review_packet_fixture(tmp_path)

    packets, summary = build_review_packets(tmp_path)

    assert summary.packets_written == 2
    assert summary.pending == 1
    assert summary.revised == 1
    assert summary.canonical_change_ready == 1
    assert "not legal advice" in summary.reliance_boundary
    assert packets[0].status == "pending"
    assert packets[1].status == "revised"
    assert packets[1].canonical_change_ready is True
    assert packets[1].logged_decision is not None


def test_write_review_packets_writes_jsonl_and_summary(tmp_path: Path) -> None:
    """Review packets are written as JSONL plus a summary sidecar."""

    _write_review_packet_fixture(tmp_path)

    summary = write_review_packets(tmp_path)

    assert summary.packets_written == 2
    assert (
        tmp_path / "02_Regulations_CCR" / "_meta" / "rule_units_review_packets.jsonl"
    ).exists()
    assert (
        tmp_path / "02_Regulations_CCR" / "_meta" / "rule_units_review_packets_summary.json"
    ).exists()


def _write_review_packet_fixture(root: Path) -> None:
    """Write a minimal queue, decision log, and apply proposal."""

    meta = root / "02_Regulations_CCR" / "_meta"
    meta.mkdir(parents=True)
    queue_rows = [
        {
            "review_id": "RUR-1",
            "rule_unit_id": "RU-1",
            "parent_regulation_id": "5_CCR_1001-9",
            "priority": "medium",
            "source_section": "5 CCR 1001-9",
            "source_sentence": "The facility shall keep records.",
            "review_reason": "Entity clarity needs review.",
            "issues": ["entity_clarity"],
            "quality": {"overall": 0.65},
            "allowed_outcomes": ["approve", "revise"],
            "suggested_outcomes": ["revise"],
            "current_rule_unit": {"id": "RU-1"},
        },
        {
            "review_id": "RUR-2",
            "rule_unit_id": "RU-2",
            "parent_regulation_id": "5_CCR_1001-9",
            "priority": "high",
            "source_section": "5 CCR 1001-9",
            "source_sentence": "The owner shall submit a report.",
            "review_reason": "Atomicity needs review.",
            "issues": ["atomicity"],
            "quality": {"overall": 0.55},
            "allowed_outcomes": ["revise", "split"],
            "suggested_outcomes": ["revise"],
            "current_rule_unit": {"id": "RU-2"},
        },
    ]
    (meta / "rule_units_review_queue.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in queue_rows),
        encoding="utf-8",
    )
    (meta / "rule_units_review_decisions.jsonl").write_text(
        json.dumps(
            {
                "decision_id": "RUD-1",
                "review_id": "RUR-2",
                "rule_unit_id": "RU-2",
                "outcome": "revise",
                "rationale": "Needs clearer action text.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (meta / "rule_units_apply_proposal.json").write_text(
        json.dumps(
            {
                "ready_to_apply": True,
                "changes": [
                    {
                        "action": "replace",
                        "rule_unit_id": "RU-2",
                        "validation_errors": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
