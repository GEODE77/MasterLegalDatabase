"""Build official-source finder checklists for modern LegiScan repair items."""

from __future__ import annotations

import argparse
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

CHECKLIST_PATH = Path(CONTROL_PLANE_DIR) / "LEGISCAN_SOURCE_FINDER_CHECKLIST.json"
DOCS_CHECKLIST_PATH = Path("docs") / "audits" / "LEGISCAN_SOURCE_FINDER_CHECKLIST_2026-07-06.md"


class SourceFinderChecklistItem(BaseModel):
    """Checklist for finding one official replacement source."""

    queue_id: str
    bill_id: str
    session: str
    category: str
    title: str
    document_type: str | None = None
    failed_url: str
    source_url: str | None = None
    archive_path: str
    official_source_hosts: list[str] = Field(min_length=1)
    search_start_points: list[str] = Field(min_length=1)
    confirmation_checklist: list[str] = Field(min_length=1)
    intake_command_shape: str
    status: str


class SourceFinderChecklist(BaseModel):
    """Machine-readable checklist bundle for modern LegiScan source repair."""

    generated_at: datetime
    status: str
    purpose: str
    queue_path: str
    item_count: int = Field(ge=0)
    open_by_year: dict[str, int]
    open_by_category: dict[str, int]
    items: list[SourceFinderChecklistItem]
    reviewer_boundary: str


def build_source_finder_checklist(root: Path) -> SourceFinderChecklist:
    """Build official-source finder checklists for open modern LegiScan items."""

    resolved_root = root.resolve()
    queue = build_modern_legiscan_repair_queue(resolved_root)
    items = [_checklist_item(item) for item in queue.items]
    return SourceFinderChecklist(
        generated_at=datetime.now(timezone.utc),
        status="active" if items else "complete",
        purpose=(
            "Give reviewers a consistent process for locating, confirming, and "
            "preserving official replacement files before guarded LegiScan repair intake."
        ),
        queue_path=QUEUE_PATH.as_posix(),
        item_count=len(items),
        open_by_year=dict(sorted(Counter(item.session for item in items).items())),
        open_by_category=dict(sorted(Counter(item.category for item in items).items())),
        items=items,
        reviewer_boundary=(
            "This checklist helps reviewers find official source files. It does not "
            "approve unofficial substitutions, edited files, or legal reliance."
        ),
    )


def write_source_finder_checklist(root: Path) -> SourceFinderChecklist:
    """Write the source finder checklist artifacts."""

    resolved_root = root.resolve()
    checklist = build_source_finder_checklist(resolved_root)
    atomic_write_json(resolved_root / CHECKLIST_PATH, checklist, resolved_root)
    atomic_write_text(resolved_root / DOCS_CHECKLIST_PATH, _docs_report(checklist), resolved_root)
    return checklist


def _checklist_item(item: ModernLegiScanRepairItem) -> SourceFinderChecklistItem:
    start_points = [
        f"https://leg.colorado.gov/bills/{item.bill_id.lower()}",
        item.preferred_url,
    ]
    if item.source_url:
        start_points.append(item.source_url)
    return SourceFinderChecklistItem(
        queue_id=item.queue_id,
        bill_id=item.bill_id,
        session=item.session,
        category=item.category,
        title=item.title,
        document_type=item.document_type,
        failed_url=item.preferred_url,
        source_url=item.source_url,
        archive_path=item.archive_path,
        official_source_hosts=[
            "leg.colorado.gov",
            "content.leg.colorado.gov",
            "s3-us-west-2.amazonaws.com/leg.colorado.gov",
        ],
        search_start_points=start_points,
        confirmation_checklist=[
            "Open the Colorado General Assembly bill page for the bill and session.",
            "Find a document matching the queue item category, document type, and bill version.",
            "Confirm the replacement file is hosted by an approved official Colorado legislative source.",
            "Download the file without editing, converting, OCR correction, or renaming its contents.",
            "Open the file and confirm it is readable and matches the expected bill, year, and document type.",
            "Record the official source URL used for the replacement file.",
            "Run the guarded LegiScan repair intake command for this queue_id.",
            "Rerun the repair progress dashboard and recent download audit after intake.",
        ],
        intake_command_shape=(
            "python -m geode.pipeline.legiscan_repair_intake --root . "
            f"--queue-id {item.queue_id} --source-file <verified_official_file> "
            "--official-source-url <official_leg_colorado_url> "
            "--reviewer-name <reviewer_name> --custody-note <custody_note>"
        ),
        status="needs_official_source_file",
    )


def _docs_report(checklist: SourceFinderChecklist) -> str:
    lines = [
        "# LegiScan Official Source Finder Checklist",
        "",
        f"Generated: {checklist.generated_at.isoformat()}",
        "",
        "## Summary",
        "",
        f"- Status: {checklist.status}",
        f"- Open checklist items: {checklist.item_count}",
        f"- Open by year: {_format_counts(checklist.open_by_year)}",
        f"- Open by category: {_format_counts(checklist.open_by_category)}",
        "",
        "## Standard Review Steps",
        "",
    ]
    standard_steps = checklist.items[0].confirmation_checklist if checklist.items else []
    for index, step in enumerate(standard_steps, start=1):
        lines.append(f"{index}. {step}")
    lines.extend(
        [
            "",
            "## Open Items",
            "",
            "| Queue ID | Bill | Year | Category | Type | Starting Point |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in checklist.items:
        lines.append(
            f"| {item.queue_id} | {item.bill_id} | {item.session} | {item.category} | "
            f"{item.document_type or ''} | {item.search_start_points[0]} |"
        )
    lines.extend(["", "## Boundary", "", checklist.reviewer_boundary, ""])
    return "\n".join(lines)


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}: {value}" for key, value in counts.items())


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--write", action="store_true", help="Write checklist artifacts.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the source finder checklist builder."""

    parser = build_parser()
    args = parser.parse_args(argv)
    checklist = (
        write_source_finder_checklist(args.root)
        if args.write
        else build_source_finder_checklist(args.root)
    )
    if args.json:
        print(checklist.model_dump_json(indent=2))
    else:
        print(f"LegiScan source finder checklist: {checklist.item_count} open item(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
