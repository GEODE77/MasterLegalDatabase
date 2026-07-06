"""Build a focused repair queue for modern LegiScan document source gaps."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, atomic_write_text, iter_jsonl

MODERN_START_YEAR = 2018
DOCUMENT_DATASET_PATH = Path("03_Legislation") / "_documents" / "bill_documents.jsonl"
QUEUE_PATH = Path(CONTROL_PLANE_DIR) / "MODERN_LEGISCAN_REPAIR_QUEUE.json"
DOCS_REPORT_PATH = Path("docs") / "audits" / "MODERN_LEGISCAN_REPAIR_QUEUE_2026-07-06.md"


class ModernLegiScanRepairItem(BaseModel):
    """One modern LegiScan source gap that is small enough for targeted review."""

    queue_id: str
    priority_rank: int = Field(ge=1)
    status: str
    bill_id: str
    session: str
    document_id: str
    category: str
    title: str
    document_type: str | None = None
    document_date: str | None = None
    preferred_url: str
    state_link: str | None = None
    source_url: str | None = None
    archive_path: str
    failure_host: str
    failure_reason: str
    original_error: str | None = None
    recommended_action: str
    verification_after_repair: list[str]


class ModernLegiScanRepairQueue(BaseModel):
    """Machine-readable queue for modern LegiScan document repair."""

    generated_at: datetime
    status: str
    purpose: str
    source_dataset_path: str
    modern_start_year: int
    item_count: int = Field(ge=0)
    year_counts: dict[str, int]
    category_counts: dict[str, int]
    host_counts: dict[str, int]
    items: list[ModernLegiScanRepairItem]
    next_action: str
    boundary: str


def build_modern_legiscan_repair_queue(
    root: Path,
    modern_start_year: int = MODERN_START_YEAR,
) -> ModernLegiScanRepairQueue:
    """Build a repair queue from modern permanent LegiScan document failures."""

    resolved_root = root.resolve()
    rows = [
        row
        for row in iter_jsonl(resolved_root / DOCUMENT_DATASET_PATH)
        if _is_modern_permanent_failure(row, modern_start_year)
    ]
    rows.sort(key=_priority_key)
    items = [_repair_item(resolved_root, row, rank) for rank, row in enumerate(rows, start=1)]
    return ModernLegiScanRepairQueue(
        generated_at=datetime.now(timezone.utc),
        status="active" if items else "empty",
        purpose=(
            "Separate the small set of modern LegiScan permanent document failures from "
            "the large historical archive-recovery project."
        ),
        source_dataset_path=DOCUMENT_DATASET_PATH.as_posix(),
        modern_start_year=modern_start_year,
        item_count=len(items),
        year_counts=dict(sorted(Counter(item.session for item in items).items())),
        category_counts=dict(sorted(Counter(item.category for item in items).items())),
        host_counts=dict(sorted(Counter(item.failure_host for item in items).items())),
        items=items,
        next_action=(
            "Review these modern items first by checking whether the Colorado General "
            "Assembly page has a corrected official document URL, then archive any "
            "verified official file through the guarded LegiScan document workflow."
        ),
        boundary=(
            "This queue does not downgrade the historical LegiScan source gap. It only "
            "creates a smaller, current-era repair lane that can be completed before the "
            "larger legacy archive project."
        ),
    )


def write_modern_legiscan_repair_queue(root: Path) -> ModernLegiScanRepairQueue:
    """Write the modern LegiScan repair queue and human report."""

    resolved_root = root.resolve()
    queue = build_modern_legiscan_repair_queue(resolved_root)
    atomic_write_json(resolved_root / QUEUE_PATH, queue, resolved_root)
    atomic_write_text(resolved_root / DOCS_REPORT_PATH, _docs_report(queue), resolved_root)
    return queue


def _is_modern_permanent_failure(row: dict[str, Any], modern_start_year: int) -> bool:
    session = str(row.get("session") or "")
    return (
        row.get("status") == "failed_permanent"
        and session.isdigit()
        and int(session) >= modern_start_year
    )


def _priority_key(row: dict[str, Any]) -> tuple[int, int, str, str]:
    category_order = {"texts": 0, "amendments": 1, "supplements": 2}
    return (
        -int(str(row.get("session") or "0")),
        category_order.get(str(row.get("category") or ""), 9),
        str(row.get("bill_id") or ""),
        str(row.get("document_id") or ""),
    )


def _repair_item(root: Path, row: dict[str, Any], rank: int) -> ModernLegiScanRepairItem:
    preferred_url = str(row.get("preferred_url") or "")
    host = urlparse(preferred_url).hostname or "unknown"
    return ModernLegiScanRepairItem(
        queue_id=f"LEGISCAN-MODERN-{row.get('document_id')}",
        priority_rank=rank,
        status="open",
        bill_id=str(row.get("bill_id") or ""),
        session=str(row.get("session") or ""),
        document_id=str(row.get("document_id") or ""),
        category=str(row.get("category") or ""),
        title=str(row.get("title") or ""),
        document_type=_optional_str(row.get("document_type")),
        document_date=_optional_str(row.get("document_date")),
        preferred_url=preferred_url,
        state_link=_optional_str(row.get("state_link")),
        source_url=_optional_str(row.get("source_url")),
        archive_path=_archive_path(root, row.get("archive_path")),
        failure_host=host,
        failure_reason=_failure_reason(row),
        original_error=_optional_str(row.get("error")),
        recommended_action=(
            "Find the current official Colorado General Assembly document URL for this "
            "bill document, verify it is the same document version, and rerun guarded "
            "document intake for this single item."
        ),
        verification_after_repair=[
            "Confirm the raw source file exists under _RAW_ARCHIVE/legiscan_documents.",
            "Confirm bill_documents.jsonl marks the item downloaded with size and hash.",
            "Rerun the modern LegiScan repair queue and recent download audit.",
        ],
    )


def _failure_reason(row: dict[str, Any]) -> str:
    error = str(row.get("error") or "")
    if "status 404" in error:
        return "official document URL returned 404"
    if "status 410" in error:
        return "official document URL is gone"
    if "status 400" in error:
        return "official document URL was rejected"
    return "permanent source download failure"


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _archive_path(root: Path, value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    marker = f"/{root.name}/"
    normalized_text = text.replace("\\", "/")
    if marker in normalized_text:
        return normalized_text.split(marker, 1)[1]
    path = Path(text)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _docs_report(queue: ModernLegiScanRepairQueue) -> str:
    lines = [
        "# Modern LegiScan Repair Queue",
        "",
        f"Generated: {queue.generated_at.isoformat()}",
        "",
        (
            f"This queue separates {queue.item_count} modern LegiScan document gaps from "
            "the larger historical archive-recovery project."
        ),
        "",
        "## Summary",
        "",
        f"- Status: {queue.status}",
        f"- Modern start year: {queue.modern_start_year}",
        f"- Source dataset: `{queue.source_dataset_path}`",
        f"- Years: {_format_counts(queue.year_counts)}",
        f"- Categories: {_format_counts(queue.category_counts)}",
        f"- Hosts: {_format_counts(queue.host_counts)}",
        "",
        "## Review Queue",
        "",
        "| Rank | Bill | Year | Category | Type | Host | Reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in queue.items:
        lines.append(
            "| "
            f"{item.priority_rank} | "
            f"{item.bill_id} | "
            f"{item.session} | "
            f"{item.category} | "
            f"{item.document_type or ''} | "
            f"{item.failure_host} | "
            f"{item.failure_reason} |"
        )
    lines.extend(
        [
            "",
            "## Next Action",
            "",
            queue.next_action,
            "",
            "## Boundary",
            "",
            queue.boundary,
            "",
        ]
    )
    return "\n".join(lines)


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}: {value}" for key, value in counts.items())


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--write", action="store_true", help="Write queue artifacts.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the modern LegiScan repair queue builder."""

    parser = build_parser()
    args = parser.parse_args(argv)
    queue = (
        write_modern_legiscan_repair_queue(args.root)
        if args.write
        else build_modern_legiscan_repair_queue(args.root)
    )
    if args.json:
        print(queue.model_dump_json(indent=2))
    else:
        print(f"Modern LegiScan repair queue: {queue.item_count} item(s), {queue.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
