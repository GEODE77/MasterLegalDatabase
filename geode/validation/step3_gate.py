"""Step 3 readiness gate for Project Geode review intelligence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, iter_jsonl, load_json

STEP3_REPORT_NAME = "STEP3_READINESS_REPORT.json"
STEP3_QUEUE_NAME = "STEP3_DEFERRED_QUEUE.json"


class Step3Check(BaseModel):
    """One Step 3 readiness check."""

    name: str
    ready: bool
    detail: str


class Step3DeferredItem(BaseModel):
    """A Step 3 item that remains queued after the review foundation is ready."""

    id: str
    title: str
    reason: str
    next_action: str


class Step3ReadinessReport(BaseModel):
    """Overall Step 3 readiness report."""

    generated_at: datetime
    ready_for_step_3_completion: bool
    checks: list[Step3Check]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    deferred_items: list[Step3DeferredItem] = Field(default_factory=list)
    next_step: str


def build_step3_readiness_report(root: Path) -> Step3ReadinessReport:
    """Build the Step 3 gate report from review evidence and product files."""

    resolved_root = root.resolve()
    checks = [
        _check_step2_ready(resolved_root),
        _check_review_queue(resolved_root),
        _check_apply_proposal(resolved_root),
        _check_decision_aware_backend(resolved_root),
        _check_decision_aware_api(resolved_root),
        _check_decision_aware_ui(resolved_root),
    ]
    blockers = [check.detail for check in checks if not check.ready]
    warnings = _warnings(resolved_root)
    deferred_items = _deferred_items(resolved_root)
    ready = not blockers
    next_step = (
        "Step 3 review foundation is complete; continue queued review and precision work."
        if ready
        else "Finish the blocking Step 3 checks, then rerun this gate."
    )
    return Step3ReadinessReport(
        generated_at=datetime.now(timezone.utc),
        ready_for_step_3_completion=ready,
        checks=checks,
        blockers=blockers,
        warnings=warnings,
        deferred_items=deferred_items,
        next_step=next_step,
    )


def write_step3_readiness_report(root: Path) -> Step3ReadinessReport:
    """Write the Step 3 report and deferred queue to the control plane."""

    resolved_root = root.resolve()
    report = build_step3_readiness_report(resolved_root)
    atomic_write_json(resolved_root / CONTROL_PLANE_DIR / STEP3_REPORT_NAME, report, resolved_root)
    atomic_write_json(
        resolved_root / CONTROL_PLANE_DIR / STEP3_QUEUE_NAME,
        {
            "generated_at": report.generated_at.isoformat(),
            "items": [item.model_dump(mode="json") for item in report.deferred_items],
        },
        resolved_root,
    )
    return report


def _check_step2_ready(root: Path) -> Step3Check:
    """Check that Step 2 passed before Step 3 is marked complete."""

    report_path = root / CONTROL_PLANE_DIR / "STEP2_READINESS_REPORT.json"
    if not report_path.exists():
        return Step3Check(
            name="Step 2 gate",
            ready=False,
            detail="Step 2 readiness report is missing.",
        )
    payload = load_json(report_path)
    ready = bool(payload.get("ready_for_step_2_completion")) if isinstance(payload, dict) else False
    return Step3Check(
        name="Step 2 gate",
        ready=ready,
        detail="Step 2 gate is clean." if ready else "Step 2 gate is not complete.",
    )


def _check_review_queue(root: Path) -> Step3Check:
    """Check that the review queue exists and has review work."""

    queue_path = root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl"
    queue_count = _count_jsonl_rows(queue_path)
    return Step3Check(
        name="Review queue",
        ready=queue_count > 0,
        detail=(
            f"Review queue contains {queue_count} items."
            if queue_count > 0
            else "Review queue is missing or empty."
        ),
    )


def _check_apply_proposal(root: Path) -> Step3Check:
    """Check that guarded apply proposal evidence exists."""

    proposal_path = root / "02_Regulations_CCR" / "_meta" / "rule_units_apply_proposal.json"
    if not proposal_path.exists():
        return Step3Check(
            name="Guarded apply proposal",
            ready=False,
            detail="Rule-unit apply proposal is missing.",
        )
    payload = load_json(proposal_path)
    ready = isinstance(payload, dict) and "ready_to_apply" in payload
    return Step3Check(
        name="Guarded apply proposal",
        ready=ready,
        detail=(
            "Guarded apply proposal exists and records apply readiness."
            if ready
            else "Rule-unit apply proposal does not record apply readiness."
        ),
    )


def _check_decision_aware_backend(root: Path) -> Step3Check:
    """Check that the product index exposes decision-aware queue state."""

    target = root / "geode" / "web" / "src" / "lib" / "product" / "productIndex.ts"
    return _check_file_markers(
        "Decision-aware backend",
        target,
        ("getRuleUnitReviewStatusSummary", "canonicalChangeReady", "change_ready"),
    )


def _check_decision_aware_api(root: Path) -> Step3Check:
    """Check that the review API exposes status filters and counts."""

    target = (
        root
        / "geode"
        / "web"
        / "src"
        / "app"
        / "api"
        / "product"
        / "rule-units"
        / "review"
        / "route.ts"
    )
    return _check_file_markers(
        "Decision-aware API",
        target,
        ("statusSummary", "normalizeStatus", "change_ready"),
    )


def _check_decision_aware_ui(root: Path) -> Step3Check:
    """Check that the review UI exposes decision-aware filters."""

    page = root / "geode" / "web" / "src" / "app" / "app" / "review" / "page.tsx"
    panel = (
        root / "geode" / "web" / "src" / "app" / "app" / "review" / "ReviewDecisionPanel.tsx"
    )
    page_ready = _file_has_markers(page, ("reviewFilters", "change_ready"))
    panel_ready = _file_has_markers(panel, ("statusLabel", "Decision Logged"))
    ready = page_ready and panel_ready
    return Step3Check(
        name="Decision-aware UI",
        ready=ready,
        detail=(
            "Review UI exposes queue filters and already-decided item state."
            if ready
            else "Review UI is missing decision-aware filters or decided-item state."
        ),
    )


def _check_file_markers(name: str, path: Path, markers: tuple[str, ...]) -> Step3Check:
    """Check that a file exists and contains required implementation markers."""

    ready = _file_has_markers(path, markers)
    return Step3Check(
        name=name,
        ready=ready,
        detail=(
            f"{name} implementation markers are present."
            if ready
            else f"{name} implementation markers are missing."
        ),
    )


def _file_has_markers(path: Path, markers: tuple[str, ...]) -> bool:
    """Return whether a file contains all required markers."""

    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return all(marker in content for marker in markers)


def _warnings(root: Path) -> list[str]:
    """Return non-blocking warnings for Step 3."""

    pending = _pending_review_count(root)
    return [f"{pending} review items still require decisions."] if pending > 0 else []


def _deferred_items(root: Path) -> list[Step3DeferredItem]:
    """Return queued work after the Step 3 foundation is complete."""

    pending = _pending_review_count(root)
    return [
        Step3DeferredItem(
            id="STEP3-RU-DECISIONS",
            title="Work the remaining rule-unit review decisions",
            reason=f"{pending} queue items still need approve, revise, split, or quarantine decisions.",
            next_action="Use /app/review filters to work pending items and rebuild the apply proposal.",
        ),
        Step3DeferredItem(
            id="STEP3-CANONICAL-APPLY",
            title="Apply reviewed canonical changes only after decisions exist",
            reason="The guarded apply path is ready, but no canonical changes should be applied without real decisions.",
            next_action="Apply only batches with valid replacement records and the confirmation phrase.",
        ),
        Step3DeferredItem(
            id="STEP3-LEGAL-REVIEW",
            title="Add formal legal review before reliance",
            reason="Reviewed rule units improve data quality but do not replace legal review.",
            next_action="Define who can approve production-ready legal guidance.",
        ),
    ]


def _pending_review_count(root: Path) -> int:
    """Return the current pending review count."""

    summary_path = root / "02_Regulations_CCR" / "_meta" / "rule_units_review_summary.json"
    if not summary_path.exists():
        return 0
    payload = load_json(summary_path)
    if not isinstance(payload, dict):
        return 0
    return int(payload.get("pending_items") or payload.get("pendingItems") or 0)


def _count_jsonl_rows(path: Path) -> int:
    """Count valid JSONL rows."""

    if not path.exists():
        return 0
    return sum(1 for _ in iter_jsonl(path))


def main() -> None:
    """Run the Step 3 gate."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    report = write_step3_readiness_report(root) if args.write else build_step3_readiness_report(root)
    if args.json:
        print(report.model_dump_json(indent=2))
        return
    print(f"Ready for Step 3 completion: {report.ready_for_step_3_completion}")
    for check in report.checks:
        status = "ready" if check.ready else "blocked"
        print(f"- {check.name}: {status} - {check.detail}")
    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
