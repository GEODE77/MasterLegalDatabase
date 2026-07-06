"""Build formal review packets for rule-unit quality review."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl, load_json

REVIEW_QUEUE_PATH = Path("02_Regulations_CCR/_meta/rule_units_review_queue.jsonl")
REVIEW_DECISIONS_PATH = Path("02_Regulations_CCR/_meta/rule_units_review_decisions.jsonl")
APPLY_PROPOSAL_PATH = Path("02_Regulations_CCR/_meta/rule_units_apply_proposal.json")
REVIEW_PACKETS_PATH = Path("02_Regulations_CCR/_meta/rule_units_review_packets.jsonl")
REVIEW_PACKETS_SUMMARY_PATH = Path("02_Regulations_CCR/_meta/rule_units_review_packets_summary.json")

PacketStatus = Literal["pending", "approved", "revised", "split", "quarantined"]


class ReviewPacket(BaseModel):
    """One formal review packet for a needs-review rule unit."""

    packet_id: str
    review_id: str
    rule_unit_id: str
    parent_regulation_id: str
    priority: str
    status: PacketStatus
    canonical_change_ready: bool
    source_section: str
    source_sentence: str
    source_context: str | None = None
    review_reason: str
    issues: list[str] = Field(default_factory=list)
    quality: dict[str, Any] = Field(default_factory=dict)
    allowed_outcomes: list[str] = Field(default_factory=list)
    suggested_outcomes: list[str] = Field(default_factory=list)
    current_rule_unit: dict[str, Any] = Field(default_factory=dict)
    logged_decision: dict[str, Any] | None = None
    reviewer_instruction: str
    reliance_boundary: str


class ReviewPacketsSummary(BaseModel):
    """Summary of the formal review packet build."""

    generated_at: datetime
    packet_path: str
    packets_written: int = Field(ge=0)
    pending: int = Field(ge=0)
    approved: int = Field(ge=0)
    revised: int = Field(ge=0)
    split: int = Field(ge=0)
    quarantined: int = Field(ge=0)
    canonical_change_ready: int = Field(ge=0)
    reliance_boundary: str


def build_review_packets(root: Path) -> tuple[list[ReviewPacket], ReviewPacketsSummary]:
    """Build formal review packets from the queue, decisions, and apply proposal."""

    resolved_root = root.resolve()
    queue_path = resolved_root / REVIEW_QUEUE_PATH
    decisions = _latest_decisions_by_review_id(resolved_root / REVIEW_DECISIONS_PATH)
    change_ready_ids = _canonical_change_ready_rule_unit_ids(resolved_root / APPLY_PROPOSAL_PATH)
    packets = [
        _packet_from_queue_row(row, decisions, change_ready_ids)
        for row in _read_jsonl_if_exists(queue_path)
    ]
    counts = Counter(packet.status for packet in packets)
    summary = ReviewPacketsSummary(
        generated_at=datetime.now(timezone.utc),
        packet_path=REVIEW_PACKETS_PATH.as_posix(),
        packets_written=len(packets),
        pending=counts["pending"],
        approved=counts["approved"],
        revised=counts["revised"],
        split=counts["split"],
        quarantined=counts["quarantined"],
        canonical_change_ready=sum(packet.canonical_change_ready for packet in packets),
        reliance_boundary=_reliance_boundary(),
    )
    return packets, summary


def write_review_packets(root: Path) -> ReviewPacketsSummary:
    """Write formal review packets and their summary."""

    resolved_root = root.resolve()
    packets, summary = build_review_packets(resolved_root)
    atomic_write_jsonl(resolved_root / REVIEW_PACKETS_PATH, packets, resolved_root)
    atomic_write_json(resolved_root / REVIEW_PACKETS_SUMMARY_PATH, summary, resolved_root)
    return summary


def _packet_from_queue_row(
    row: dict[str, Any],
    decisions: dict[str, dict[str, Any]],
    change_ready_ids: set[str],
) -> ReviewPacket:
    """Convert one queue row into a formal review packet."""

    review_id = str(row.get("review_id") or "unknown")
    rule_unit_id = str(row.get("rule_unit_id") or "unknown")
    decision = decisions.get(review_id)
    status = _status_from_decision(decision)
    return ReviewPacket(
        packet_id=f"RUP-{review_id}",
        review_id=review_id,
        rule_unit_id=rule_unit_id,
        parent_regulation_id=str(row.get("parent_regulation_id") or "unknown"),
        priority=str(row.get("priority") or "medium"),
        status=status,
        canonical_change_ready=bool(decision and rule_unit_id in change_ready_ids),
        source_section=str(row.get("source_section") or "Source text"),
        source_sentence=str(row.get("source_sentence") or ""),
        source_context=_optional_string(row.get("source_context")),
        review_reason=str(row.get("review_reason") or "Review required."),
        issues=_string_list(row.get("issues")),
        quality=row.get("quality") if isinstance(row.get("quality"), dict) else {},
        allowed_outcomes=_string_list(row.get("allowed_outcomes")),
        suggested_outcomes=_string_list(row.get("suggested_outcomes")),
        current_rule_unit=(
            row.get("current_rule_unit") if isinstance(row.get("current_rule_unit"), dict) else {}
        ),
        logged_decision=decision,
        reviewer_instruction=_reviewer_instruction(status),
        reliance_boundary=_reliance_boundary(),
    )


def _latest_decisions_by_review_id(path: Path) -> dict[str, dict[str, Any]]:
    """Return the latest logged decision for each review ID."""

    decisions: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl_if_exists(path):
        review_id = str(row.get("review_id") or "")
        if review_id:
            decisions[review_id] = row
    return decisions


def _canonical_change_ready_rule_unit_ids(path: Path) -> set[str]:
    """Return rule-unit IDs with valid canonical remove or replace proposal changes."""

    if not path.exists():
        return set()
    payload = load_json(path)
    if not isinstance(payload, dict) or not payload.get("ready_to_apply"):
        return set()
    ready_ids: set[str] = set()
    for change in payload.get("changes") or []:
        if not isinstance(change, dict):
            continue
        action = change.get("action")
        errors = change.get("validation_errors") or []
        rule_unit_id = change.get("rule_unit_id")
        if action in {"remove", "replace"} and not errors and rule_unit_id:
            ready_ids.add(str(rule_unit_id))
    return ready_ids


def _status_from_decision(decision: dict[str, Any] | None) -> PacketStatus:
    """Map a decision record to packet status."""

    if not decision:
        return "pending"
    outcome = decision.get("outcome")
    if outcome == "approve":
        return "approved"
    if outcome == "revise":
        return "revised"
    if outcome == "split":
        return "split"
    if outcome == "quarantine":
        return "quarantined"
    return "pending"


def _reviewer_instruction(status: PacketStatus) -> str:
    """Return a concise reviewer instruction for one packet state."""

    if status == "pending":
        return "Review the source sentence and choose approve, revise, split, or quarantine."
    if status == "approved":
        return "Confirm that the logged approval is supported by the source sentence."
    if status in {"revised", "split"}:
        return "Review the proposed replacement rule units before canonical apply."
    return "Confirm quarantine only if the extracted rule unit is not source-faithful."


def _reliance_boundary() -> str:
    """Return the common reliance boundary for all review packets."""

    return (
        "This packet supports review of extracted rule-unit data. It is not legal advice, "
        "does not change canonical law, and should not be externally relied on until reviewed."
    )


def _read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
    """Read JSONL rows when a file exists."""

    if not path.exists():
        return []
    return list(iter_jsonl(path))


def _string_list(value: Any) -> list[str]:
    """Return a list of strings from an arbitrary JSON value."""

    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _optional_string(value: Any) -> str | None:
    """Return an optional string."""

    if value is None:
        return None
    return str(value)


def main() -> None:
    """Build and optionally write review packets."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    summary = write_review_packets(root) if args.write else build_review_packets(root)[1]
    if args.json:
        print(summary.model_dump_json(indent=2))
        return
    print(f"Review packets written: {summary.packets_written}")


if __name__ == "__main__":
    main()
