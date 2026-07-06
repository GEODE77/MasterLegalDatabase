"""Build a progress dashboard for modern LegiScan repair work."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.pipeline.modern_legiscan_repair_queue import (
    QUEUE_PATH,
    ModernLegiScanRepairItem,
    build_modern_legiscan_repair_queue,
)
from geode.utils.file_io import atomic_write_json, atomic_write_text

LEDGER_PATH = Path(CONTROL_PLANE_DIR) / "LEGISCAN_REPAIR_INTAKE_LEDGER.jsonl"
DASHBOARD_PATH = Path(CONTROL_PLANE_DIR) / "LEGISCAN_REPAIR_PROGRESS_DASHBOARD.json"
DOCS_DASHBOARD_PATH = (
    Path("docs") / "audits" / "LEGISCAN_REPAIR_PROGRESS_DASHBOARD_2026-07-06.md"
)


class RepairedLegiScanProgressItem(BaseModel):
    """One repaired modern LegiScan item."""

    queue_id: str
    document_id: str
    bill_id: str
    session: str
    category: str
    reviewer_name: str
    repaired_at: datetime
    official_source_url: str
    archive_path: str


class OpenLegiScanProgressItem(BaseModel):
    """One open modern LegiScan repair item."""

    queue_id: str
    bill_id: str
    session: str
    category: str
    title: str
    document_type: str | None = None
    failure_reason: str
    preferred_url: str
    archive_path: str
    needed_action: str


class LegiScanRepairProgressDashboard(BaseModel):
    """Progress dashboard for modern LegiScan repair work."""

    generated_at: datetime
    status: str
    purpose: str
    queue_path: str
    ledger_path: str
    original_scope_items: int = Field(ge=0)
    repaired_count: int = Field(ge=0)
    open_count: int = Field(ge=0)
    percent_repaired: float = Field(ge=0.0, le=100.0)
    reviewers: dict[str, int]
    open_by_year: dict[str, int]
    open_by_category: dict[str, int]
    repaired_items: list[RepairedLegiScanProgressItem]
    open_items: list[OpenLegiScanProgressItem]
    next_action: str
    boundary: str


def build_legiscan_repair_progress_dashboard(root: Path) -> LegiScanRepairProgressDashboard:
    """Build the LegiScan repair progress dashboard from queue and ledger artifacts."""

    resolved_root = root.resolve()
    queue = build_modern_legiscan_repair_queue(resolved_root)
    repaired_items = _repaired_items(resolved_root / LEDGER_PATH)
    open_items = [_open_item(item) for item in queue.items]
    unique_ids = {item.queue_id for item in open_items}
    unique_ids.update(item.queue_id for item in repaired_items)
    original_scope = len(unique_ids)
    repaired_count = len({item.queue_id for item in repaired_items})
    open_count = len(open_items)
    percent_repaired = round((repaired_count / original_scope) * 100, 1) if original_scope else 100.0
    status = "complete" if open_count == 0 else "active"
    return LegiScanRepairProgressDashboard(
        generated_at=datetime.now(timezone.utc),
        status=status,
        purpose=(
            "Track modern LegiScan repair progress by combining the open repair queue "
            "with completed guarded intake records."
        ),
        queue_path=QUEUE_PATH.as_posix(),
        ledger_path=LEDGER_PATH.as_posix(),
        original_scope_items=original_scope,
        repaired_count=repaired_count,
        open_count=open_count,
        percent_repaired=percent_repaired,
        reviewers=dict(sorted(Counter(item.reviewer_name for item in repaired_items).items())),
        open_by_year=dict(sorted(Counter(item.session for item in open_items).items())),
        open_by_category=dict(sorted(Counter(item.category for item in open_items).items())),
        repaired_items=repaired_items,
        open_items=open_items,
        next_action=(
            "For each open item, locate a verified official replacement file and run "
            "python -m geode.pipeline.legiscan_repair_intake."
        ),
        boundary=(
            "This dashboard tracks source-repair operations only. It does not certify "
            "legal correctness, source interpretation, or public reliance."
        ),
    )


def write_legiscan_repair_progress_dashboard(root: Path) -> LegiScanRepairProgressDashboard:
    """Write machine and human-readable LegiScan repair progress dashboards."""

    resolved_root = root.resolve()
    dashboard = build_legiscan_repair_progress_dashboard(resolved_root)
    atomic_write_json(resolved_root / DASHBOARD_PATH, dashboard, resolved_root)
    atomic_write_text(resolved_root / DOCS_DASHBOARD_PATH, _docs_report(dashboard), resolved_root)
    return dashboard


def _repaired_items(path: Path) -> list[RepairedLegiScanProgressItem]:
    if not path.exists():
        return []
    items: list[RepairedLegiScanProgressItem] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        queue_id = str(payload.get("queue_id") or "")
        if not queue_id or queue_id in seen:
            continue
        seen.add(queue_id)
        items.append(
            RepairedLegiScanProgressItem(
                queue_id=queue_id,
                document_id=str(payload.get("document_id") or ""),
                bill_id=str(payload.get("bill_id") or ""),
                session=str(payload.get("session") or ""),
                category=str(payload.get("category") or ""),
                reviewer_name=str(payload.get("reviewer_name") or "unknown"),
                repaired_at=datetime.fromisoformat(str(payload.get("repaired_at"))),
                official_source_url=str(payload.get("official_source_url") or ""),
                archive_path=str(payload.get("archive_path") or ""),
            )
        )
    return items


def _open_item(item: ModernLegiScanRepairItem) -> OpenLegiScanProgressItem:
    return OpenLegiScanProgressItem(
        queue_id=item.queue_id,
        bill_id=item.bill_id,
        session=item.session,
        category=item.category,
        title=item.title,
        document_type=item.document_type,
        failure_reason=item.failure_reason,
        preferred_url=item.preferred_url,
        archive_path=item.archive_path,
        needed_action="needs verified official replacement file",
    )


def _docs_report(dashboard: LegiScanRepairProgressDashboard) -> str:
    lines = [
        "# LegiScan Repair Progress Dashboard",
        "",
        f"Generated: {dashboard.generated_at.isoformat()}",
        "",
        "## Summary",
        "",
        f"- Status: {dashboard.status}",
        f"- Original modern scope: {dashboard.original_scope_items}",
        f"- Repaired: {dashboard.repaired_count}",
        f"- Still open: {dashboard.open_count}",
        f"- Percent repaired: {dashboard.percent_repaired}%",
        f"- Reviewers: {_format_counts(dashboard.reviewers)}",
        f"- Open by year: {_format_counts(dashboard.open_by_year)}",
        f"- Open by category: {_format_counts(dashboard.open_by_category)}",
        "",
        "## Open Items",
        "",
        "| Queue ID | Bill | Year | Category | Needed Action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in dashboard.open_items:
        lines.append(
            f"| {item.queue_id} | {item.bill_id} | {item.session} | "
            f"{item.category} | {item.needed_action} |"
        )
    lines.extend(["", "## Repaired Items", ""])
    if dashboard.repaired_items:
        lines.extend(
            [
                "| Queue ID | Bill | Reviewer | Repaired At |",
                "| --- | --- | --- | --- |",
            ]
        )
        for item in dashboard.repaired_items:
            lines.append(
                f"| {item.queue_id} | {item.bill_id} | {item.reviewer_name} | "
                f"{item.repaired_at.isoformat()} |"
            )
    else:
        lines.append("No modern LegiScan repair intakes have been recorded yet.")
    lines.extend(["", "## Next Action", "", dashboard.next_action, "", "## Boundary", "", dashboard.boundary, ""])
    return "\n".join(lines)


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}: {value}" for key, value in counts.items())


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--write", action="store_true", help="Write dashboard artifacts.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the LegiScan repair progress dashboard builder."""

    parser = build_parser()
    args = parser.parse_args(argv)
    dashboard = (
        write_legiscan_repair_progress_dashboard(args.root)
        if args.write
        else build_legiscan_repair_progress_dashboard(args.root)
    )
    if args.json:
        print(dashboard.model_dump_json(indent=2))
    else:
        print(
            "LegiScan repair progress: "
            f"{dashboard.repaired_count} repaired, {dashboard.open_count} open."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
