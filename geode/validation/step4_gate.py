"""Step 4 readiness gate for formal review packet handoff."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, iter_jsonl, load_json

STEP4_REPORT_NAME = "STEP4_READINESS_REPORT.json"
STEP4_QUEUE_NAME = "STEP4_DEFERRED_QUEUE.json"


class Step4Check(BaseModel):
    """One Step 4 readiness check."""

    name: str
    ready: bool
    detail: str


class Step4DeferredItem(BaseModel):
    """A Step 4 item that remains queued after packet handoff is ready."""

    id: str
    title: str
    reason: str
    next_action: str


class Step4ReadinessReport(BaseModel):
    """Overall Step 4 readiness report."""

    generated_at: datetime
    ready_for_step_4_completion: bool
    checks: list[Step4Check]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    deferred_items: list[Step4DeferredItem] = Field(default_factory=list)
    next_step: str


def build_step4_readiness_report(root: Path) -> Step4ReadinessReport:
    """Build the Step 4 gate report from review packet evidence."""

    resolved_root = root.resolve()
    checks = [
        _check_step3_ready(resolved_root),
        _check_review_packets(resolved_root),
        _check_packet_summary(resolved_root),
    ]
    blockers = [check.detail for check in checks if not check.ready]
    warnings = _warnings(resolved_root)
    deferred_items = _deferred_items(resolved_root)
    ready = not blockers
    next_step = (
        "Step 4 review packet handoff is complete; begin packet review when reviewers are ready."
        if ready
        else "Finish the blocking Step 4 checks, then rerun this gate."
    )
    return Step4ReadinessReport(
        generated_at=datetime.now(timezone.utc),
        ready_for_step_4_completion=ready,
        checks=checks,
        blockers=blockers,
        warnings=warnings,
        deferred_items=deferred_items,
        next_step=next_step,
    )


def write_step4_readiness_report(root: Path) -> Step4ReadinessReport:
    """Write the Step 4 report and deferred queue to the control plane."""

    resolved_root = root.resolve()
    report = build_step4_readiness_report(resolved_root)
    atomic_write_json(resolved_root / CONTROL_PLANE_DIR / STEP4_REPORT_NAME, report, resolved_root)
    atomic_write_json(
        resolved_root / CONTROL_PLANE_DIR / STEP4_QUEUE_NAME,
        {
            "generated_at": report.generated_at.isoformat(),
            "items": [item.model_dump(mode="json") for item in report.deferred_items],
        },
        resolved_root,
    )
    return report


def _check_step3_ready(root: Path) -> Step4Check:
    """Check that Step 3 passed before Step 4 is marked complete."""

    report_path = root / CONTROL_PLANE_DIR / "STEP3_READINESS_REPORT.json"
    if not report_path.exists():
        return Step4Check(
            name="Step 3 gate",
            ready=False,
            detail="Step 3 readiness report is missing.",
        )
    payload = load_json(report_path)
    ready = bool(payload.get("ready_for_step_3_completion")) if isinstance(payload, dict) else False
    return Step4Check(
        name="Step 3 gate",
        ready=ready,
        detail="Step 3 gate is clean." if ready else "Step 3 gate is not complete.",
    )


def _check_review_packets(root: Path) -> Step4Check:
    """Check that review packets exist and line up with the queue."""

    queue_count = _count_jsonl_rows(
        root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl"
    )
    packet_count = _count_jsonl_rows(
        root / "02_Regulations_CCR" / "_meta" / "rule_units_review_packets.jsonl"
    )
    ready = packet_count > 0 and packet_count == queue_count
    return Step4Check(
        name="Formal review packets",
        ready=ready,
        detail=(
            f"Review packets match the queue with {packet_count} packets."
            if ready
            else f"Review packets count {packet_count} does not match queue count {queue_count}."
        ),
    )


def _check_packet_summary(root: Path) -> Step4Check:
    """Check that packet summary exists and preserves the reliance boundary."""

    summary_path = (
        root / "02_Regulations_CCR" / "_meta" / "rule_units_review_packets_summary.json"
    )
    if not summary_path.exists():
        return Step4Check(
            name="Review packet summary",
            ready=False,
            detail="Review packet summary is missing.",
        )
    payload = load_json(summary_path)
    boundary = str(payload.get("reliance_boundary") or "") if isinstance(payload, dict) else ""
    ready = "not legal advice" in boundary and "does not change canonical law" in boundary
    return Step4Check(
        name="Review packet summary",
        ready=ready,
        detail=(
            "Review packet summary preserves the reliance boundary."
            if ready
            else "Review packet summary is missing the reliance boundary."
        ),
    )


def _warnings(root: Path) -> list[str]:
    """Return Step 4 warnings."""

    pending = _pending_packet_count(root)
    return [f"{pending} review packets remain pending."] if pending > 0 else []


def _deferred_items(root: Path) -> list[Step4DeferredItem]:
    """Return queued work after packet handoff is ready."""

    pending = _pending_packet_count(root)
    return [
        Step4DeferredItem(
            id="STEP4-PACKET-REVIEW",
            title="Complete formal packet review",
            reason=f"{pending} packets remain pending formal review.",
            next_action="Use the backend review packet files to work packet batches and log review decisions.",
        ),
        Step4DeferredItem(
            id="STEP4-CANONICAL-APPLY",
            title="Apply only reviewed canonical changes",
            reason="Packets prepare review but do not change canonical rule-unit data.",
            next_action="Apply only reviewed remove or replace decisions through the guarded apply path.",
        ),
        Step4DeferredItem(
            id="STEP4-RELIANCE-POLICY",
            title="Define production reliance policy",
            reason="Review packets preserve boundaries but do not decide who may approve reliance.",
            next_action="Define reviewer roles, approval criteria, and external-use limits.",
        ),
    ]


def _pending_packet_count(root: Path) -> int:
    """Return pending packet count from the packet summary."""

    summary_path = (
        root / "02_Regulations_CCR" / "_meta" / "rule_units_review_packets_summary.json"
    )
    if not summary_path.exists():
        return 0
    payload = load_json(summary_path)
    if not isinstance(payload, dict):
        return 0
    return int(payload.get("pending") or 0)


def _count_jsonl_rows(path: Path) -> int:
    """Count valid JSONL rows."""

    if not path.exists():
        return 0
    return sum(1 for _ in iter_jsonl(path))


def main() -> None:
    """Run the Step 4 gate."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    report = write_step4_readiness_report(root) if args.write else build_step4_readiness_report(root)
    if args.json:
        print(report.model_dump_json(indent=2))
        return
    print(f"Ready for Step 4 completion: {report.ready_for_step_4_completion}")
    for check in report.checks:
        status = "ready" if check.ready else "blocked"
        print(f"- {check.name}: {status} - {check.detail}")
    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
