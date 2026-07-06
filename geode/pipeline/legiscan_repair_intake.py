"""Guarded single-item intake for modern LegiScan document repairs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from geode.connectors.archive_paths import raw_connector_dir
from geode.connectors.download_metadata import source_format_from_extension
from geode.connectors.legiscan_documents import LegiScanDocumentMetadata, LegiScanDocumentSummary
from geode.constants import CONTROL_PLANE_DIR, RAW_ARCHIVE_DIR
from geode.pipeline.modern_legiscan_repair_queue import (
    DOCUMENT_DATASET_PATH,
    build_modern_legiscan_repair_queue,
    write_modern_legiscan_repair_queue,
)
from geode.schemas.validators import require_official_source_url
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, atomic_write_text, iter_jsonl

LEDGER_PATH = Path(CONTROL_PLANE_DIR) / "LEGISCAN_REPAIR_INTAKE_LEDGER.jsonl"
REPORT_PATH = Path(CONTROL_PLANE_DIR) / "LEGISCAN_REPAIR_INTAKE_REPORT.json"
DOCUMENT_CSV_PATH = Path("03_Legislation") / "_documents" / "bill_documents.csv"
DOCUMENT_SUMMARY_PATH = Path("03_Legislation") / "_documents" / "bill_document_summary.json"
ARCHIVE_MANIFEST_PATH = Path(RAW_ARCHIVE_DIR) / "legiscan_documents" / "repair_intake_manifest.jsonl"


class LegiScanRepairIntakeRequest(BaseModel):
    """Request to repair one item from the modern LegiScan repair queue."""

    model_config = ConfigDict(extra="forbid")

    queue_id: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    official_source_url: str
    official_source_name: str = Field(default="Colorado General Assembly", min_length=1)
    reviewer_name: str = Field(min_length=1)
    custody_note: str = Field(min_length=10)
    expected_sha256: str | None = None
    content_type: str | None = None
    allow_existing_archive: bool = False

    @field_validator("official_source_url")
    @classmethod
    def _official_url(cls, value: str) -> str:
        """Require an approved official source host."""

        return require_official_source_url(value.strip())

    @field_validator("expected_sha256")
    @classmethod
    def _valid_sha(cls, value: str | None) -> str | None:
        """Validate optional SHA-256."""

        if value is None or not value.strip():
            return None
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(char not in "0123456789abcdef" for char in cleaned):
            raise ValueError("expected_sha256 must be a 64-character hex digest")
        return cleaned


class LegiScanRepairIntakeRecord(BaseModel):
    """Durable control-plane record for one repaired LegiScan document."""

    model_config = ConfigDict(extra="forbid")

    intake_id: str
    queue_id: str
    document_id: str
    bill_id: str
    session: str
    category: str
    official_source_name: str
    official_source_url: str
    reviewer_name: str
    custody_note: str
    source_file: str
    archive_path: str
    sha256: str
    size_bytes: int = Field(ge=1)
    content_type: str
    source_format: str
    repaired_at: datetime
    archive_write: str
    dataset_status_after: str
    remaining_modern_queue_items: int = Field(ge=0)
    boundary: str


class LegiScanRepairIntakeReport(BaseModel):
    """Summary of guarded LegiScan repair intakes."""

    generated_at: datetime
    ledger_path: str
    archive_manifest_path: str
    records: int = Field(ge=0)
    latest_queue_id: str | None = None
    latest_document_id: str | None = None
    remaining_modern_queue_items: int = Field(ge=0)
    boundary: str


def repair_modern_legiscan_item(
    root: Path,
    request: LegiScanRepairIntakeRequest | dict[str, Any],
    *,
    dry_run: bool = False,
    timestamp: datetime | None = None,
) -> LegiScanRepairIntakeRecord:
    """Archive a verified official file and mark one modern LegiScan item repaired."""

    resolved_root = root.resolve()
    intake_request = LegiScanRepairIntakeRequest.model_validate(request)
    repaired_at = timestamp or datetime.now(timezone.utc)
    queue = build_modern_legiscan_repair_queue(resolved_root)
    item = next((entry for entry in queue.items if entry.queue_id == intake_request.queue_id), None)
    if item is None:
        raise ValueError(f"queue_id is not open in the modern LegiScan queue: {intake_request.queue_id}")

    source_path = Path(intake_request.source_file).expanduser().resolve()
    _validate_source_file(source_path)
    content = source_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if intake_request.expected_sha256 and digest != intake_request.expected_sha256:
        raise ValueError("source file SHA-256 does not match expected_sha256")

    archive_path = _resolve_archive_path(resolved_root, item.archive_path)
    archive_write = _archive_repair_file(
        archive_path,
        content,
        digest,
        allow_existing=intake_request.allow_existing_archive,
        dry_run=dry_run,
    )
    content_type = intake_request.content_type or _content_type(source_path)
    record = LegiScanRepairIntakeRecord(
        intake_id=f"LRI-{repaired_at.strftime('%Y%m%dT%H%M%S%fZ')}-{item.document_id}",
        queue_id=item.queue_id,
        document_id=item.document_id,
        bill_id=item.bill_id,
        session=item.session,
        category=item.category,
        official_source_name=intake_request.official_source_name,
        official_source_url=intake_request.official_source_url,
        reviewer_name=intake_request.reviewer_name,
        custody_note=intake_request.custody_note,
        source_file=source_path.as_posix(),
        archive_path=_relative_path(archive_path, resolved_root),
        sha256=digest,
        size_bytes=len(content),
        content_type=content_type,
        source_format=source_format_from_extension(source_path.suffix),
        repaired_at=repaired_at,
        archive_write=archive_write,
        dataset_status_after="downloaded" if not dry_run else "dry_run",
        remaining_modern_queue_items=max(queue.item_count - 1, 0),
        boundary=(
            "This intake records a verified source repair for one LegiScan document. It "
            "does not certify legal interpretation or replace later source review."
        ),
    )
    if dry_run:
        return record

    _update_document_outputs(resolved_root, item.document_id, intake_request, record)
    _append_jsonl_raw(resolved_root / ARCHIVE_MANIFEST_PATH, record)
    _append_jsonl_control(resolved_root / LEDGER_PATH, record, resolved_root)
    refreshed_queue = write_modern_legiscan_repair_queue(resolved_root)
    from geode.pipeline.legiscan_repair_progress_dashboard import (
        write_legiscan_repair_progress_dashboard,
    )

    write_legiscan_repair_progress_dashboard(resolved_root)
    final_record = record.model_copy(
        update={"remaining_modern_queue_items": refreshed_queue.item_count}
    )
    write_repair_intake_report(resolved_root)
    return final_record


def write_repair_intake_report(root: Path) -> LegiScanRepairIntakeReport:
    """Write a summary report for LegiScan repair intakes."""

    resolved_root = root.resolve()
    records = _read_ledger(resolved_root / LEDGER_PATH)
    latest = records[-1] if records else None
    remaining = build_modern_legiscan_repair_queue(resolved_root).item_count
    report = LegiScanRepairIntakeReport(
        generated_at=datetime.now(timezone.utc),
        ledger_path=LEDGER_PATH.as_posix(),
        archive_manifest_path=ARCHIVE_MANIFEST_PATH.as_posix(),
        records=len(records),
        latest_queue_id=latest.queue_id if latest else None,
        latest_document_id=latest.document_id if latest else None,
        remaining_modern_queue_items=remaining,
        boundary=(
            "This report tracks guarded single-item source repairs. Each repaired item "
            "still depends on official-source verification and normal downstream audits."
        ),
    )
    atomic_write_json(resolved_root / REPORT_PATH, report, resolved_root)
    return report


def _validate_source_file(source_path: Path) -> None:
    if not source_path.exists() or not source_path.is_file():
        raise ValueError(f"source_file does not exist: {source_path}")
    if source_path.stat().st_size <= 0:
        raise ValueError("source_file is empty")


def _resolve_archive_path(root: Path, archive_path_text: str) -> Path:
    if not archive_path_text:
        raise ValueError("queue item is missing archive_path")
    archive_path = Path(archive_path_text)
    if not archive_path.is_absolute():
        archive_path = root / archive_path
    resolved = archive_path.resolve()
    archive_root = (root / RAW_ARCHIVE_DIR / "legiscan_documents").resolve()
    if not resolved.is_relative_to(archive_root):
        raise ValueError(f"archive_path is outside LegiScan raw archive: {archive_path_text}")
    return resolved


def _archive_repair_file(
    archive_path: Path,
    content: bytes,
    digest: str,
    *,
    allow_existing: bool,
    dry_run: bool,
) -> str:
    if archive_path.exists():
        existing_digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        if allow_existing and existing_digest == digest:
            return "existing_matching_archive_used"
        raise ValueError(f"archive target already exists and will not be overwritten: {archive_path}")
    if dry_run:
        return "dry_run_pending_archive"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(content)
    return "new_archive_file_written"


def _update_document_outputs(
    root: Path,
    document_id: str,
    request: LegiScanRepairIntakeRequest,
    record: LegiScanRepairIntakeRecord,
) -> None:
    rows = [LegiScanDocumentMetadata.model_validate(row) for row in iter_jsonl(root / DOCUMENT_DATASET_PATH)]
    updated: list[LegiScanDocumentMetadata] = []
    matched = False
    downloaded_at = record.repaired_at
    archive_path = (root / record.archive_path).resolve().as_posix()
    for row in rows:
        if row.document_id != document_id:
            updated.append(row)
            continue
        matched = True
        updated.append(
            row.model_copy(
                update={
                    "preferred_url": request.official_source_url,
                    "state_link": request.official_source_url,
                    "archive_path": archive_path,
                    "status": "downloaded",
                    "content_type": record.content_type,
                    "size_bytes": record.size_bytes,
                    "sha256": record.sha256,
                    "error": None,
                    "downloaded_at": downloaded_at,
                }
            )
        )
    if not matched:
        raise ValueError(f"document_id not found in bill_documents.jsonl: {document_id}")
    atomic_write_jsonl(root / DOCUMENT_DATASET_PATH, updated, root)
    _write_csv(root / DOCUMENT_CSV_PATH, updated, root)
    _write_summary(root, updated)


def _write_summary(root: Path, rows: list[LegiScanDocumentMetadata]) -> None:
    status_counts = Counter(row.status for row in rows)
    category_counts = Counter(row.category for row in rows)
    failures = [
        f"{row.document_id}: {row.error}"
        for row in rows
        if row.status in {"failed", "failed_permanent"} and row.error
    ][:100]
    document_archive = raw_connector_dir(root / RAW_ARCHIVE_DIR, "legiscan_documents")
    bill_archive = raw_connector_dir(root / RAW_ARCHIVE_DIR, "legiscan")
    summary = LegiScanDocumentSummary(
        generated_at=datetime.now(timezone.utc),
        output_root=root.as_posix(),
        bill_archive_dir=bill_archive.as_posix(),
        document_archive_dir=document_archive.as_posix(),
        queue_path=(document_archive / "bill_document_queue.jsonl").as_posix(),
        manifest_path=(document_archive / "download_manifest.jsonl").as_posix(),
        dataset_jsonl_path=(root / DOCUMENT_DATASET_PATH).as_posix(),
        dataset_csv_path=(root / DOCUMENT_CSV_PATH).as_posix(),
        summary_path=(root / DOCUMENT_SUMMARY_PATH).as_posix(),
        discovered_total=len(rows),
        attempted=sum(
            1
            for row in rows
            if row.status in {"downloaded", "failed", "failed_permanent", "pending_retry"}
        ),
        downloaded=status_counts.get("downloaded", 0),
        skipped_existing=status_counts.get("skipped_existing", 0),
        failed=status_counts.get("failed", 0),
        failed_permanent=status_counts.get("failed_permanent", 0),
        pending_retry=status_counts.get("pending_retry", 0),
        records_total=len(rows),
        pending=status_counts.get("discovered", 0),
        discovery_only=False,
        category_counts=dict(sorted(category_counts.items())),
        status_counts=dict(sorted(status_counts.items())),
        failures=failures,
    )
    atomic_write_json(root / DOCUMENT_SUMMARY_PATH, summary, root)


def _write_csv(path: Path, records: list[LegiScanDocumentMetadata], root: Path) -> None:
    fields = [
        "document_id",
        "bill_id",
        "session",
        "category",
        "document_type",
        "document_date",
        "preferred_url",
        "archive_path",
        "status",
        "content_type",
        "size_bytes",
        "sha256",
        "error",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for record in records:
        payload = record.model_dump(mode="json")
        writer.writerow({field: payload.get(field) for field in fields})
    atomic_write_text(path, output.getvalue(), root)


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".doc":
        return "application/msword"
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if suffix in {".html", ".htm"}:
        return "text/html"
    return "application/octet-stream"


def _append_jsonl_raw(path: Path, record: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(record.model_dump_json() + "\n")


def _append_jsonl_control(path: Path, record: BaseModel, root: Path) -> None:
    existing: list[dict[str, Any]] = []
    if path.exists():
        existing = list(iter_jsonl(path))
    existing.append(record.model_dump(mode="json"))
    atomic_write_jsonl(path, existing, root)


def _read_ledger(path: Path) -> list[LegiScanRepairIntakeRecord]:
    if not path.exists():
        return []
    return [
        LegiScanRepairIntakeRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--queue-id", required=True, help="Queue id from the modern repair queue.")
    parser.add_argument("--source-file", required=True, help="Verified official replacement file.")
    parser.add_argument("--official-source-url", required=True)
    parser.add_argument("--official-source-name", default="Colorado General Assembly")
    parser.add_argument("--reviewer-name", required=True)
    parser.add_argument("--custody-note", required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--content-type")
    parser.add_argument("--allow-existing-archive", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one guarded LegiScan repair intake."""

    parser = build_parser()
    args = parser.parse_args(argv)
    record = repair_modern_legiscan_item(
        args.root,
        {
            "queue_id": args.queue_id,
            "source_file": args.source_file,
            "official_source_url": args.official_source_url,
            "official_source_name": args.official_source_name,
            "reviewer_name": args.reviewer_name,
            "custody_note": args.custody_note,
            "expected_sha256": args.expected_sha256,
            "content_type": args.content_type,
            "allow_existing_archive": args.allow_existing_archive,
        },
        dry_run=args.dry_run,
    )
    if args.json:
        print(record.model_dump_json(indent=2))
    else:
        print(
            "LegiScan repair intake "
            f"{record.dataset_status_after}: {record.document_id}; "
            f"{record.remaining_modern_queue_items} modern item(s) remain."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
