"""Build production-readiness and remaining-work reports."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, load_json

PRODUCTION_READINESS_REPORT_PATH = Path(CONTROL_PLANE_DIR) / "PRODUCTION_READINESS_REPORT.json"
REMAINING_WORK_QUEUE_PATH = Path(CONTROL_PLANE_DIR) / "REMAINING_WORK_QUEUE.json"
BLOCKED_DOWNLOAD_QUEUE_PATH = Path(CONTROL_PLANE_DIR) / "BLOCKED_DOWNLOAD_QUEUE.json"


class ProductionControl(BaseModel):
    """One production readiness control."""

    control_id: str
    title: str
    status: str
    evidence_path: str | None = None
    detail: str


class RemainingWorkItem(BaseModel):
    """One item that cannot honestly be marked complete yet."""

    id: str
    title: str
    category: str
    status: str
    reason: str
    next_action: str


class ProductionReadinessReport(BaseModel):
    """Production readiness report."""

    generated_at: datetime
    system_controls_present: bool
    controls: list[ProductionControl]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    boundary: dict[str, str]


class RemainingWorkQueue(BaseModel):
    """Queue of work that remains after buildable foundations are complete."""

    generated_at: datetime
    open_items: int = Field(ge=0)
    items: list[RemainingWorkItem]


def build_operations_readiness(root: Path) -> tuple[ProductionReadinessReport, RemainingWorkQueue]:
    """Build production-readiness and remaining-work reports."""

    resolved_root = root.resolve()
    controls = [
        _control_raw_archive(resolved_root),
        _control_manual_source_intake(resolved_root),
        _control_step9(resolved_root),
        _control_reviewers(resolved_root),
        _control_review_packets(resolved_root),
        _control_diff(resolved_root),
        _control_freshness(resolved_root),
        _control_retrieval(resolved_root),
    ]
    blockers = [control.detail for control in controls if control.status == "blocked"]
    warnings = [control.detail for control in controls if control.status == "warning"]
    report = ProductionReadinessReport(
        generated_at=datetime.now(timezone.utc),
        system_controls_present=not blockers,
        controls=controls,
        blockers=blockers,
        warnings=warnings,
        boundary={
            "meaning": "System controls are present when local gates and control artifacts exist.",
            "not_implied": (
                "This does not mean Geode is approved for legal advice, external reliance, "
                "or unsupervised use."
            ),
            "external_reliance_condition": (
                "External reliance requires named reviewer assignments, completed review packets, "
                "source-refresh checks, and explicit legal reviewer approval."
            ),
        },
    )
    queue = RemainingWorkQueue(
        generated_at=datetime.now(timezone.utc),
        open_items=len(_remaining_items(resolved_root)),
        items=_remaining_items(resolved_root),
    )
    return report, queue


def write_operations_readiness(root: Path) -> tuple[ProductionReadinessReport, RemainingWorkQueue]:
    """Write production-readiness and remaining-work reports."""

    resolved_root = root.resolve()
    report, queue = build_operations_readiness(resolved_root)
    atomic_write_json(resolved_root / PRODUCTION_READINESS_REPORT_PATH, report, resolved_root)
    atomic_write_json(resolved_root / REMAINING_WORK_QUEUE_PATH, queue, resolved_root)
    return report, queue


def _control_raw_archive(root: Path) -> ProductionControl:
    """Check raw archive protection exists in code."""

    path = root / "geode" / "utils" / "file_io.py"
    ready = path.exists() and "ensure_not_raw_archive" in path.read_text(encoding="utf-8")
    return ProductionControl(
        control_id="RAW-ARCHIVE-PROTECTION",
        title="Raw archive write protection",
        status="ready" if ready else "blocked",
        evidence_path="geode/utils/file_io.py",
        detail=(
            "Raw archive write protection exists."
            if ready
            else "Raw archive write protection was not found."
        ),
    )


def _control_manual_source_intake(root: Path) -> ProductionControl:
    """Check manual source intake controls."""

    module_path = root / "geode" / "pipeline" / "manual_source_intake.py"
    policy_path = root / CONTROL_PLANE_DIR / "MANUAL_SOURCE_INTAKE_POLICY.json"
    ready = module_path.exists() and policy_path.exists()
    return ProductionControl(
        control_id="MANUAL-SOURCE-INTAKE",
        title="Manual official source intake",
        status="ready" if ready else "warning",
        evidence_path=(
            "_CONTROL_PLANE/MANUAL_SOURCE_INTAKE_POLICY.json"
            if policy_path.exists()
            else "geode/pipeline/manual_source_intake.py"
        ),
        detail=(
            "Manual official source intake controls are present."
            if ready
            else "Manual official source intake policy has not been written."
        ),
    )


def _control_step9(root: Path) -> ProductionControl:
    """Check relationship health gate."""

    report = _load_dict(root / CONTROL_PLANE_DIR / "STEP9_READINESS_REPORT.json")
    ready = bool(report.get("ready_for_step_9_completion"))
    return ProductionControl(
        control_id="STEP9-GATE",
        title="Relationship health gate",
        status="ready" if ready else "blocked",
        evidence_path="_CONTROL_PLANE/STEP9_READINESS_REPORT.json",
        detail="Step 9 gate is clean." if ready else "Step 9 gate is not clean.",
    )


def _control_reviewers(root: Path) -> ProductionControl:
    """Check reviewer assignments."""

    summary = _load_dict(root / CONTROL_PLANE_DIR / "REVIEWER_OPERATIONS_SUMMARY.json")
    unassigned = int(summary.get("unassigned_roles") or 0)
    return ProductionControl(
        control_id="REVIEWER-ASSIGNMENTS",
        title="Reviewer assignments",
        status="warning" if unassigned else "ready",
        evidence_path="_CONTROL_PLANE/REVIEWER_OPERATIONS_SUMMARY.json",
        detail=f"{unassigned} reviewer roles remain unassigned.",
    )


def _control_review_packets(root: Path) -> ProductionControl:
    """Check review packet completion."""

    summary = _load_dict(root / "02_Regulations_CCR" / "_meta" / "rule_units_review_packets_summary.json")
    pending = int(summary.get("pending") or 0)
    return ProductionControl(
        control_id="REVIEW-PACKETS",
        title="Review packet status",
        status="warning" if pending else "ready",
        evidence_path="02_Regulations_CCR/_meta/rule_units_review_packets_summary.json",
        detail=f"{pending} review packets remain pending.",
    )


def _control_diff(root: Path) -> ProductionControl:
    """Check full text diff foundation."""

    summary = _load_dict(root / CONTROL_PLANE_DIR / "FULL_TEXT_DIFF_SUMMARY.json")
    ready = bool(summary.get("diff_ready"))
    return ProductionControl(
        control_id="TEXT-DIFF",
        title="Full text diff foundation",
        status="ready" if ready else "warning",
        evidence_path="_CONTROL_PLANE/FULL_TEXT_DIFF_SUMMARY.json",
        detail=(
            f"{int(summary.get('files_checked') or 0)} text files checked for local snapshot diff."
        ),
    )


def _control_freshness(root: Path) -> ProductionControl:
    """Check local freshness report."""

    report = _load_dict(root / CONTROL_PLANE_DIR / "SOURCE_FRESHNESS_REPORT.json")
    stale = int(report.get("stale_layers") or 0)
    unknown = int(report.get("unknown_layers") or 0)
    return ProductionControl(
        control_id="SOURCE-FRESHNESS",
        title="Source freshness report",
        status="ready" if stale == 0 and unknown == 0 else "warning",
        evidence_path="_CONTROL_PLANE/SOURCE_FRESHNESS_REPORT.json",
        detail=f"{stale} stale layers and {unknown} unknown layers in local freshness report.",
    )


def _control_retrieval(root: Path) -> ProductionControl:
    """Check retrieval catalog."""

    summary = _load_dict(root / CONTROL_PLANE_DIR / "RETRIEVAL_CATALOG_SUMMARY.json")
    records = int(summary.get("records_written") or 0)
    return ProductionControl(
        control_id="RETRIEVAL-CATALOG",
        title="Retrieval catalog",
        status="ready" if records else "blocked",
        evidence_path="_CONTROL_PLANE/RETRIEVAL_CATALOG_SUMMARY.json",
        detail=f"{records} retrieval records are available.",
    )


def _remaining_items(root: Path) -> list[RemainingWorkItem]:
    """Return remaining human or external work."""

    reviewer_summary = _load_dict(root / CONTROL_PLANE_DIR / "REVIEWER_OPERATIONS_SUMMARY.json")
    packet_summary = _load_dict(root / "02_Regulations_CCR" / "_meta" / "rule_units_review_packets_summary.json")
    unassigned = int(reviewer_summary.get("unassigned_roles") or 0)
    pending = int(packet_summary.get("pending") or 0)
    items = [
        RemainingWorkItem(
            id="HUMAN-REVIEWERS",
            title="Assign named reviewers",
            category="human_review",
            status="queued" if unassigned else "complete",
            reason=f"{unassigned} reviewer roles require real project-owner assignment.",
            next_action="Project owner names data, corpus, and legal reviewers.",
        ),
        RemainingWorkItem(
            id="HUMAN-PACKET-REVIEW",
            title="Complete packet review",
            category="human_review",
            status="queued" if pending else "complete",
            reason=f"{pending} review packets require real decisions.",
            next_action="Review, approve, revise, split, or quarantine each pending packet.",
        ),
        RemainingWorkItem(
            id="EXTERNAL-SOURCE-REFRESH",
            title="Run official-source refresh checks",
            category="external_source",
            status="queued",
            reason="Network source refresh was intentionally not performed in local freshness reporting.",
            next_action="Run official source connectors with network access under controlled refresh windows.",
        ),
        RemainingWorkItem(
            id="LEGAL-EXTERNAL-RELIANCE",
            title="Approve external reliance",
            category="legal_review",
            status="queued",
            reason="Geode has system controls, but legal reliance requires explicit legal reviewer approval.",
            next_action="Legal reviewer approves specific outputs before external reliance.",
        ),
    ]
    items.extend(_blocked_download_items(root))
    return [item for item in items if item.status != "complete"]


def _blocked_download_items(root: Path) -> list[RemainingWorkItem]:
    """Return queued blocked downloads as remaining work items."""

    queue = _load_dict(root / BLOCKED_DOWNLOAD_QUEUE_PATH)
    rows = queue.get("items", [])
    if not isinstance(rows, list):
        return []
    items: list[RemainingWorkItem] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("status") in {"complete", "resolved"}:
            continue
        record_id = str(row.get("record_id") or row.get("id") or "UNKNOWN")
        items.append(
            RemainingWorkItem(
                id=f"BLOCKED-DOWNLOAD-{record_id}",
                title=f"Resolve blocked download for {record_id}",
                category="blocked_download",
                status="queued",
                reason=str(row.get("block_reason") or "Official download is blocked."),
                next_action=str(row.get("next_action") or "Retry or replace through an official source."),
            )
        )
    return items


def _load_dict(path: Path) -> dict[str, Any]:
    """Load a JSON object, returning an empty object if absent."""

    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def main() -> None:
    """Build or write operations readiness reports."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    if args.write:
        report, queue = write_operations_readiness(root)
    else:
        report, queue = build_operations_readiness(root)
    if args.json:
        import json

        print(
            json.dumps(
                {
                    "production_readiness": report.model_dump(mode="json"),
                    "remaining_work": queue.model_dump(mode="json"),
                },
                indent=2,
            )
        )
        return
    print(f"System controls present: {report.system_controls_present}")
    print(f"Remaining open items: {queue.open_items}")


if __name__ == "__main__":
    main()
