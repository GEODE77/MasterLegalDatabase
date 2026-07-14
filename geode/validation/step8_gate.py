"""Step 8 readiness gate for update tracking before full text diff."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, iter_jsonl, load_json

STEP8_REPORT_NAME = "STEP8_READINESS_REPORT.json"
STEP8_QUEUE_NAME = "STEP8_DEFERRED_QUEUE.json"


class Step8Check(BaseModel):
    """One Step 8 readiness check."""

    name: str
    ready: bool
    detail: str


class Step8DeferredItem(BaseModel):
    """A Step 8 item that remains queued after update tracking exists."""

    id: str
    title: str
    reason: str
    next_action: str


class Step8ReadinessReport(BaseModel):
    """Overall Step 8 readiness report."""

    generated_at: datetime
    ready_for_step_8_completion: bool
    checks: list[Step8Check]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    deferred_items: list[Step8DeferredItem] = Field(default_factory=list)
    next_step: str


def build_step8_readiness_report(root: Path) -> Step8ReadinessReport:
    """Build the Step 8 gate report from update ledger evidence."""

    resolved_root = root.resolve()
    checks = [
        _check_step6_ready(resolved_root),
        _check_ledger_exists(resolved_root),
        _check_summary_matches_ledger(resolved_root),
        _check_diff_boundary(resolved_root),
    ]
    blockers = [check.detail for check in checks if not check.ready]
    warnings = _warnings(resolved_root)
    deferred_items = _deferred_items()
    ready = not blockers
    next_step = (
        "Step 8 update tracking is complete; full text diff remains queued."
        if ready
        else "Finish the blocking Step 8 checks, then rerun this gate."
    )
    return Step8ReadinessReport(
        generated_at=datetime.now(timezone.utc),
        ready_for_step_8_completion=ready,
        checks=checks,
        blockers=blockers,
        warnings=warnings,
        deferred_items=deferred_items,
        next_step=next_step,
    )


def write_step8_readiness_report(root: Path) -> Step8ReadinessReport:
    """Write the Step 8 report and deferred queue to the control plane."""

    resolved_root = root.resolve()
    report = build_step8_readiness_report(resolved_root)
    atomic_write_json(resolved_root / CONTROL_PLANE_DIR / STEP8_REPORT_NAME, report, resolved_root)
    atomic_write_json(
        resolved_root / CONTROL_PLANE_DIR / STEP8_QUEUE_NAME,
        {
            "generated_at": report.generated_at.isoformat(),
            "items": [item.model_dump(mode="json") for item in report.deferred_items],
        },
        resolved_root,
    )
    return report


def _check_step6_ready(root: Path) -> Step8Check:
    """Check that the prior buildable operations step is complete."""

    report_path = root / CONTROL_PLANE_DIR / "STEP6_READINESS_REPORT.json"
    if not report_path.exists():
        return Step8Check(
            name="Step 6 gate",
            ready=False,
            detail="Step 6 readiness report is missing.",
        )
    payload = load_json(report_path)
    ready = bool(payload.get("ready_for_step_6_completion")) if isinstance(payload, dict) else False
    return Step8Check(
        name="Step 6 gate",
        ready=ready,
        detail="Step 6 gate is clean." if ready else "Step 6 gate is not complete.",
    )


def _check_ledger_exists(root: Path) -> Step8Check:
    """Check that the update ledger exists and contains rows."""

    path = root / CONTROL_PLANE_DIR / "UPDATE_LEDGER.jsonl"
    rows = _ledger_rows(path)
    ready = len(rows) > 0
    return Step8Check(
        name="Update ledger",
        ready=ready,
        detail=(
            f"Update ledger contains {len(rows)} events."
            if ready
            else "Update ledger is missing or empty."
        ),
    )


def _check_summary_matches_ledger(root: Path) -> Step8Check:
    """Check that the ledger summary count matches the ledger rows."""

    ledger_path = root / CONTROL_PLANE_DIR / "UPDATE_LEDGER.jsonl"
    summary_path = root / CONTROL_PLANE_DIR / "UPDATE_LEDGER_SUMMARY.json"
    rows = _ledger_rows(ledger_path)
    summary = _load_dict(summary_path)
    expected = int(summary.get("events_written") or -1)
    ready = bool(rows) and expected == len(rows)
    return Step8Check(
        name="Ledger summary",
        ready=ready,
        detail=(
            "Update ledger summary matches the ledger row count."
            if ready
            else "Update ledger summary is missing or does not match the ledger."
        ),
    )


def _check_diff_boundary(root: Path) -> Step8Check:
    """Check that full diff status is honestly represented."""

    summary = _load_dict(root / CONTROL_PLANE_DIR / "UPDATE_LEDGER_SUMMARY.json")
    ready = summary.get("full_diff_ready") is False and summary.get("diff_status") == "not_started"
    return Step8Check(
        name="Diff boundary",
        ready=ready,
        detail=(
            "Full text diff is clearly marked as not started."
            if ready
            else "Full text diff boundary is unclear."
        ),
    )


def _warnings(root: Path) -> list[str]:
    """Return non-blocking Step 8 warnings."""

    summary = _load_dict(root / CONTROL_PLANE_DIR / "UPDATE_LEDGER_SUMMARY.json")
    if summary.get("full_diff_ready") is False:
        return ["Full legal text diff remains queued after the update ledger foundation."]
    return []


def _deferred_items() -> list[Step8DeferredItem]:
    """Return queued work after the update ledger foundation."""

    return [
        Step8DeferredItem(
            id="STEP8-FULL-TEXT-DIFF",
            title="Add full legal text diff",
            reason="The update ledger tracks source-backed events, but not exact text-level changes.",
            next_action="Create source snapshots and compare prior and current canonical text.",
        ),
        Step8DeferredItem(
            id="STEP8-SNAPSHOT-COMPARISON",
            title="Add stable snapshot comparison",
            reason="Reliable full diff needs stable prior snapshots for each corpus layer.",
            next_action="Define snapshot retention and comparison policy before computing diffs.",
        ),
        Step8DeferredItem(
            id="STEP8-HUMAN-REVIEW-DEPENDENCY",
            title="Complete human review dependency",
            reason="Step 7 packet decisions and reviewer assignments still require real people.",
            next_action="Assign reviewers and process the pending review packet queue.",
        ),
    ]


def _ledger_rows(path: Path) -> list[dict[str, object]]:
    """Read ledger rows if the ledger exists."""

    if not path.exists():
        return []
    return list(iter_jsonl(path))


def _load_dict(path: Path) -> dict[str, object]:
    """Load a JSON object, returning an empty object if absent."""

    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def main() -> None:
    """Run the Step 8 gate."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    report = write_step8_readiness_report(root) if args.write else build_step8_readiness_report(root)
    if args.json:
        print(report.model_dump_json(indent=2))
        return
    print(f"Ready for Step 8 completion: {report.ready_for_step_8_completion}")
    for check in report.checks:
        status = "ready" if check.ready else "blocked"
        print(f"- {check.name}: {status} - {check.detail}")
    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
