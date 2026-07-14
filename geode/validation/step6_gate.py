"""Step 6 readiness gate for reviewer operations."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, load_json

STEP6_REPORT_NAME = "STEP6_READINESS_REPORT.json"
STEP6_QUEUE_NAME = "STEP6_DEFERRED_QUEUE.json"


class Step6Check(BaseModel):
    """One Step 6 readiness check."""

    name: str
    ready: bool
    detail: str


class Step6DeferredItem(BaseModel):
    """A Step 6 item that remains queued after operations setup is ready."""

    id: str
    title: str
    reason: str
    next_action: str


class Step6ReadinessReport(BaseModel):
    """Overall Step 6 readiness report."""

    generated_at: datetime
    ready_for_step_6_completion: bool
    checks: list[Step6Check]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    deferred_items: list[Step6DeferredItem] = Field(default_factory=list)
    next_step: str


def build_step6_readiness_report(root: Path) -> Step6ReadinessReport:
    """Build the Step 6 gate report from reviewer operations evidence."""

    resolved_root = root.resolve()
    checks = [
        _check_step5_ready(resolved_root),
        _check_assignments(resolved_root),
        _check_sop(resolved_root),
        _check_operations_summary(resolved_root),
    ]
    blockers = [check.detail for check in checks if not check.ready]
    warnings = _warnings(resolved_root)
    deferred_items = _deferred_items(resolved_root)
    ready = not blockers
    next_step = (
        "Step 6 reviewer operations setup is complete; assign named reviewers before live review."
        if ready
        else "Finish the blocking Step 6 checks, then rerun this gate."
    )
    return Step6ReadinessReport(
        generated_at=datetime.now(timezone.utc),
        ready_for_step_6_completion=ready,
        checks=checks,
        blockers=blockers,
        warnings=warnings,
        deferred_items=deferred_items,
        next_step=next_step,
    )


def write_step6_readiness_report(root: Path) -> Step6ReadinessReport:
    """Write the Step 6 report and deferred queue to the control plane."""

    resolved_root = root.resolve()
    report = build_step6_readiness_report(resolved_root)
    atomic_write_json(resolved_root / CONTROL_PLANE_DIR / STEP6_REPORT_NAME, report, resolved_root)
    atomic_write_json(
        resolved_root / CONTROL_PLANE_DIR / STEP6_QUEUE_NAME,
        {
            "generated_at": report.generated_at.isoformat(),
            "items": [item.model_dump(mode="json") for item in report.deferred_items],
        },
        resolved_root,
    )
    return report


def _check_step5_ready(root: Path) -> Step6Check:
    """Check that Step 5 passed before Step 6 is marked complete."""

    report_path = root / CONTROL_PLANE_DIR / "STEP5_READINESS_REPORT.json"
    if not report_path.exists():
        return Step6Check(
            name="Step 5 gate",
            ready=False,
            detail="Step 5 readiness report is missing.",
        )
    payload = load_json(report_path)
    ready = bool(payload.get("ready_for_step_5_completion")) if isinstance(payload, dict) else False
    return Step6Check(
        name="Step 5 gate",
        ready=ready,
        detail="Step 5 gate is clean." if ready else "Step 5 gate is not complete.",
    )


def _check_assignments(root: Path) -> Step6Check:
    """Check reviewer assignment slots."""

    assignments = _assignments(root)
    rows = assignments.get("assignments") if isinstance(assignments.get("assignments"), list) else []
    role_ids = {row.get("role_id") for row in rows if isinstance(row, dict)}
    required = {"data_reviewer", "corpus_maintainer", "legal_reviewer"}
    ready = required.issubset(role_ids)
    return Step6Check(
        name="Reviewer assignment slots",
        ready=ready,
        detail=(
            "Reviewer assignment slots exist for all required roles."
            if ready
            else "Reviewer assignment slots are missing required roles."
        ),
    )


def _check_sop(root: Path) -> Step6Check:
    """Check reviewer SOP."""

    path = root / "docs" / "GEODE_REVIEWER_SOP.md"
    if not path.exists():
        return Step6Check(name="Reviewer SOP", ready=False, detail="Reviewer SOP is missing.")
    content = path.read_text(encoding="utf-8")
    ready = (
        "Do not treat review packets as legal advice." in content
        and "Do not change canonical rule units outside the guarded apply path." in content
        and "Assign named reviewers" not in content
    )
    has_operating_flow = "## Operating Flow" in content
    ready = ready and has_operating_flow
    return Step6Check(
        name="Reviewer SOP",
        ready=ready,
        detail=(
            "Reviewer SOP exists with boundaries and operating flow."
            if ready
            else "Reviewer SOP is missing required boundaries or operating flow."
        ),
    )


def _check_operations_summary(root: Path) -> Step6Check:
    """Check reviewer operations summary."""

    summary = _summary(root)
    ready = bool(summary.get("ready_for_human_assignment")) and int(summary.get("required_roles") or 0) >= 3
    return Step6Check(
        name="Reviewer operations summary",
        ready=ready,
        detail=(
            "Reviewer operations summary is ready for human assignment."
            if ready
            else "Reviewer operations summary is missing or incomplete."
        ),
    )


def _assignments(root: Path) -> dict[str, object]:
    """Load reviewer assignments."""

    path = root / CONTROL_PLANE_DIR / "REVIEWER_ASSIGNMENTS.json"
    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _summary(root: Path) -> dict[str, object]:
    """Load reviewer operations summary."""

    path = root / CONTROL_PLANE_DIR / "REVIEWER_OPERATIONS_SUMMARY.json"
    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _warnings(root: Path) -> list[str]:
    """Return non-blocking Step 6 warnings."""

    summary = _summary(root)
    unassigned = int(summary.get("unassigned_roles") or 0)
    return [f"{unassigned} reviewer roles are prepared but unassigned."] if unassigned > 0 else []


def _deferred_items(root: Path) -> list[Step6DeferredItem]:
    """Return queued work after reviewer operations setup is ready."""

    summary = _summary(root)
    unassigned = int(summary.get("unassigned_roles") or 0)
    return [
        Step6DeferredItem(
            id="STEP6-NAME-REVIEWERS",
            title="Name real reviewers",
            reason=f"{unassigned} reviewer roles are ready but still unassigned.",
            next_action="Project owner assigns named people to data reviewer, corpus maintainer, and legal reviewer roles.",
        ),
        Step6DeferredItem(
            id="STEP6-TRAIN-REVIEWERS",
            title="Train reviewers on the SOP",
            reason="The SOP exists, but people still need to be trained before live packet review.",
            next_action="Walk reviewers through packet review, decision logging, escalation, and guarded apply.",
        ),
        Step6DeferredItem(
            id="STEP6-START-PACKET-REVIEW",
            title="Start packet review",
            reason="The system is ready, but the 532 pending packets still need actual decisions.",
            next_action="Use backend review packet and review queue artifacts after reviewers are assigned.",
        ),
    ]


def main() -> None:
    """Run the Step 6 gate."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    report = write_step6_readiness_report(root) if args.write else build_step6_readiness_report(root)
    if args.json:
        print(report.model_dump_json(indent=2))
        return
    print(f"Ready for Step 6 completion: {report.ready_for_step_6_completion}")
    for check in report.checks:
        status = "ready" if check.ready else "blocked"
        print(f"- {check.name}: {status} - {check.detail}")
    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
