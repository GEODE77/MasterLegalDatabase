"""Download document attachments referenced by archived LegiScan bills."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import os
import re
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from geode.connectors.archive_paths import raw_connector_dir, safe_archive_stem
from geode.connectors.legiscan_transformer import transform_bill
from geode.constants import CONTROL_PLANE_DIR, RAW_ARCHIVE_DIR
from geode.net.http_client import GeodeHttpClient, GeodeHttpClientConfig, GeodeHttpError
from geode.utils.file_io import (
    atomic_write_json,
    atomic_write_jsonl,
    atomic_write_text,
    load_json,
)
from geode.utils.hashing import sha256_file
from geode.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)

LEGISLATION_LAYER = "03_Legislation"
DOCUMENTS_DIR = "_documents"
DOCUMENT_QUEUE_NAME = "bill_document_queue.jsonl"
DOCUMENT_DATASET_NAME = "bill_documents.jsonl"
DOCUMENT_CSV_NAME = "bill_documents.csv"
DOCUMENT_SUMMARY_NAME = "bill_document_summary.json"
DOCUMENT_MANIFEST_NAME = "download_manifest.jsonl"
SAFE_BULK_REPORT_NAME = "safe_bulk_report.json"
SAFE_BULK_BATCHES_NAME = "safe_bulk_batches.jsonl"
SAFE_BULK_DEFAULT_PHASES = ("texts", "amendments", "supplements")
DEFAULT_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/octet-stream",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/html",
    }
)
PERMANENT_MISSING_STATUS_CODES = frozenset({400, 404, 410})
RETRYABLE_SOURCE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
PERMANENT_BLOCKED_HOSTS = frozenset({"www.leg.state.co.us", "leg.state.co.us"})
HTML_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})
BINARY_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".doc", ".docx"})
ARCHIVE_WRAPPER_MARKERS = (
    b"colorado legislative - archived content",
    b"archive-iframe",
    b"accessible-archive",
)
LEGACY_ARCHIVE_WRAPPER_ERROR = (
    "legacy Colorado archive returned an HTML wrapper instead of the source document"
)
LEGACY_ARCHIVE_UNRECOVERABLE_ERROR = (
    "legacy Colorado archive document URL is not retrievable by plain HTTP"
)
ARCHIVE_REPLACE_ATTEMPTS = 10
ARCHIVE_REPLACE_DELAY_SECONDS = 0.2


class LegiScanDocumentItem(BaseModel):
    """One document attachment discovered from a raw LegiScan bill record."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    bill_id: str = Field(min_length=1)
    session: str = Field(pattern=r"^\d{4}$")
    bill_number: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    document_type: str | None = None
    document_date: str | None = None
    legiscan_doc_id: str | None = None
    source_url: str
    state_link: str | None = None
    preferred_url: str
    mime: str | None = None
    expected_size: int | None = Field(default=None, ge=0)
    text_hash: str | None = None
    source_bill_path: str
    archive_path: str


class LegiScanDocumentManifestEntry(BaseModel):
    """One attempted or completed LegiScan document download."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    bill_id: str
    category: str
    preferred_url: str
    archive_path: str
    status: str
    status_code: int | None = None
    content_type: str | None = None
    size_bytes: int = Field(default=0, ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    downloaded_at: datetime
    error: str | None = None


class LegiScanDocumentMetadata(BaseModel):
    """Normalized metadata row for one LegiScan document attachment."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    bill_id: str
    session: str
    bill_number: str
    title: str
    category: str
    document_type: str | None = None
    document_date: str | None = None
    source_url: str
    state_link: str | None = None
    preferred_url: str
    archive_path: str
    status: str
    content_type: str | None = None
    size_bytes: int = Field(default=0, ge=0)
    sha256: str | None = None
    error: str | None = None
    downloaded_at: datetime | None = None


class LegiScanDocumentSummary(BaseModel):
    """Summary for one LegiScan document attachment run."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    output_root: str
    bill_archive_dir: str
    document_archive_dir: str
    queue_path: str
    manifest_path: str
    dataset_jsonl_path: str
    dataset_csv_path: str
    summary_path: str
    discovered_total: int = Field(ge=0)
    run_attempted: int = Field(default=0, ge=0)
    run_downloaded: int = Field(default=0, ge=0)
    run_skipped_existing: int = Field(default=0, ge=0)
    run_failed: int = Field(default=0, ge=0)
    run_failed_permanent: int = Field(default=0, ge=0)
    run_pending_retry: int = Field(default=0, ge=0)
    attempted: int = Field(ge=0)
    downloaded: int = Field(ge=0)
    skipped_existing: int = Field(ge=0)
    failed: int = Field(ge=0)
    failed_permanent: int = Field(default=0, ge=0)
    pending_retry: int = Field(default=0, ge=0)
    records_total: int = Field(ge=0)
    pending: int = Field(ge=0)
    max_documents: int | None = None
    discovery_only: bool
    category_counts: dict[str, int] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)
    failures: list[str] = Field(default_factory=list)


class LegiScanSafeBulkSummary(BaseModel):
    """Summary for a staged safe bulk document run."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    output_root: str
    status: str
    phase_order: list[str]
    batch_size: int
    delay: float
    final_delay: float
    max_retries: int
    cooldown_seconds: float
    max_rate_limit_pauses: int
    rate_limit_pauses: int = Field(ge=0)
    batches_attempted: int = Field(ge=0)
    run_downloaded: int = Field(ge=0)
    run_failed: int = Field(ge=0)
    run_failed_permanent: int = Field(ge=0)
    run_pending_retry: int = Field(ge=0)
    final_downloaded: int = Field(ge=0)
    final_failed: int = Field(ge=0)
    final_failed_permanent: int = Field(ge=0)
    final_pending_retry: int = Field(ge=0)
    final_pending: int = Field(ge=0)
    final_records_total: int = Field(ge=0)
    stopped_reason: str | None = None
    report_path: str
    batches_path: str
    summary_path: str


def run_legiscan_document_pipeline(
    output_root: Path,
    *,
    max_documents: int | None = None,
    year: int | None = None,
    category: str | None = None,
    discovery_only: bool = False,
    refresh_queue: bool = False,
    delay: float = 0.25,
    timeout_seconds: float = 60.0,
    max_retries: int = 3,
) -> LegiScanDocumentSummary:
    """Discover and optionally download LegiScan bill document attachments."""

    _validate_options(max_documents, delay, timeout_seconds, max_retries)
    root = output_root.resolve()
    paths = _paths(root)
    if discovery_only or refresh_queue or not paths["queue"].exists():
        all_items = discover_document_items(root)
        _write_jsonl_raw(paths["queue"], all_items)
    else:
        all_items = _read_queue(paths["queue"])
    items = _filter_items(all_items, year=year, category=category)
    run_stats: Counter[str] = Counter()
    if not discovery_only:
        run_stats = _download_items(
            items,
            paths["manifest"],
            root,
            max_documents=max_documents,
            delay=delay,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    summary = write_document_dataset(
        root,
        items if discovery_only else all_items,
        max_documents=max_documents,
        discovery_only=discovery_only,
        run_stats=run_stats,
    )
    LOGGER.info(
        "LegiScan document workflow records=%s run_downloaded=%s run_failed=%s "
        "cumulative_downloaded=%s pending=%s",
        summary.records_total,
        summary.run_downloaded,
        summary.run_failed,
        summary.downloaded,
        summary.pending,
    )
    return summary


def run_legiscan_document_safe_bulk(
    output_root: Path,
    *,
    batch_size: int = 1000,
    delay: float = 0.75,
    timeout_seconds: float = 60.0,
    max_retries: int = 1,
    cooldown_seconds: float = 900.0,
    max_rate_limit_pauses: int = 3,
    rate_limit_delay_multiplier: float = 2.0,
    max_batches: int | None = None,
    phase_order: list[str] | None = None,
    refresh_queue: bool = False,
) -> LegiScanSafeBulkSummary:
    """Run staged document acquisition with conservative stop conditions."""

    _validate_options(batch_size, delay, timeout_seconds, max_retries)
    _validate_safe_bulk_options(cooldown_seconds, max_rate_limit_pauses, rate_limit_delay_multiplier)
    if batch_size <= 0:
        raise ValueError("--batch-size must be positive")
    if max_batches is not None and max_batches <= 0:
        raise ValueError("--max-batches must be positive")
    root = output_root.resolve()
    paths = _paths(root)
    phases = phase_order or list(SAFE_BULK_DEFAULT_PHASES)
    _validate_phases(phases)
    if refresh_queue or not paths["queue"].exists():
        all_items = discover_document_items(root)
        _write_jsonl_raw(paths["queue"], all_items)
    paths["safe_bulk_batches"].parent.mkdir(parents=True, exist_ok=True)
    if not paths["safe_bulk_batches"].exists():
        paths["safe_bulk_batches"].write_text("", encoding="utf-8")

    totals: Counter[str] = Counter()
    batches_attempted = 0
    rate_limit_pauses = 0
    active_delay = delay
    stopped_reason: str | None = None
    for phase in phases:
        while True:
            before = write_document_dataset(root)
            phase_remaining = _count_remaining_by_category(root, phase)
            if phase_remaining == 0:
                break
            summary = run_legiscan_document_pipeline(
                root,
                max_documents=batch_size,
                category=phase,
                delay=active_delay,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
            batches_attempted += 1
            totals["downloaded"] += summary.run_downloaded
            totals["failed"] += summary.run_failed
            totals["failed_permanent"] += summary.run_failed_permanent
            totals["pending_retry"] += summary.run_pending_retry
            _append_safe_bulk_batch(
                paths["safe_bulk_batches"],
                phase,
                batches_attempted,
                before,
                summary,
            )
            if summary.run_pending_retry > 0:
                rate_limit_pauses += 1
                if rate_limit_pauses > max_rate_limit_pauses:
                    stopped_reason = f"retryable source condition during {phase}"
                    break
                active_delay *= rate_limit_delay_multiplier
                LOGGER.warning(
                    "Retryable source condition during phase=%s; cooling down for %s seconds, "
                    "then resuming with delay=%s.",
                    phase,
                    cooldown_seconds,
                    active_delay,
                )
                time.sleep(cooldown_seconds)
                continue
            if summary.run_failed > 0:
                stopped_reason = f"non-permanent failure during {phase}"
                break
            if max_batches is not None and batches_attempted >= max_batches:
                stopped_reason = "max batches reached"
                break
            if summary.run_attempted == 0:
                break
        if stopped_reason is not None:
            break

    final_summary = write_document_dataset(root)
    status = "completed" if final_summary.pending == 0 and final_summary.pending_retry == 0 else "paused"
    if final_summary.failed > 0:
        status = "needs_review"
    safe_summary = LegiScanSafeBulkSummary(
        generated_at=datetime.now(timezone.utc),
        output_root=root.as_posix(),
        status=status,
        phase_order=phases,
        batch_size=batch_size,
        delay=delay,
        final_delay=active_delay,
        max_retries=max_retries,
        cooldown_seconds=cooldown_seconds,
        max_rate_limit_pauses=max_rate_limit_pauses,
        rate_limit_pauses=rate_limit_pauses,
        batches_attempted=batches_attempted,
        run_downloaded=totals["downloaded"],
        run_failed=totals["failed"],
        run_failed_permanent=totals["failed_permanent"],
        run_pending_retry=totals["pending_retry"],
        final_downloaded=final_summary.downloaded,
        final_failed=final_summary.failed,
        final_failed_permanent=final_summary.failed_permanent,
        final_pending_retry=final_summary.pending_retry,
        final_pending=final_summary.pending,
        final_records_total=final_summary.records_total,
        stopped_reason=stopped_reason,
        report_path=paths["safe_bulk_report"].as_posix(),
        batches_path=paths["safe_bulk_batches"].as_posix(),
        summary_path=paths["summary"].as_posix(),
    )
    atomic_write_json(paths["safe_bulk_report"], safe_summary, root)
    return safe_summary


def discover_document_items(
    output_root: Path,
    *,
    year: int | None = None,
    category: str | None = None,
) -> list[LegiScanDocumentItem]:
    """Return deterministic document work items from archived LegiScan JSON files."""

    root = output_root.resolve()
    paths = _paths(root)
    ontology = load_json(root / CONTROL_PLANE_DIR / "ONTOLOGY.json")
    items: dict[str, LegiScanDocumentItem] = {}
    for bill_path in sorted(paths["bill_archive"].rglob("*.json")):
        payload = json.loads(bill_path.read_text(encoding="utf-8"))
        record = transform_bill(payload, ontology)
        if year is not None and record["session"] != str(year):
            continue
        bill = payload.get("bill", payload)
        if not isinstance(bill, dict):
            continue
        for document_category in ("texts", "amendments", "supplements"):
            if category is not None and document_category != category:
                continue
            for index, source in enumerate(bill.get(document_category, []) or []):
                if not isinstance(source, dict):
                    continue
                item = _item_from_source(
                    source,
                    record,
                    bill_path,
                    paths["document_archive"],
                    document_category,
                    index,
                )
                if item is not None:
                    items[item.document_id] = item
    return [items[key] for key in sorted(items)]


def write_document_dataset(
    output_root: Path,
    items: list[LegiScanDocumentItem] | None = None,
    *,
    max_documents: int | None = None,
    discovery_only: bool = False,
    run_stats: Counter[str] | None = None,
) -> LegiScanDocumentSummary:
    """Write normalized document metadata and summary outputs."""

    root = output_root.resolve()
    paths = _paths(root)
    if items is None:
        items = _read_queue(paths["queue"])
    if run_stats is None:
        run_stats = Counter()
    manifest = _latest_manifest(paths["manifest"])
    records = [_metadata_for(item, manifest.get(item.document_id)) for item in items]
    status_counts = Counter(record.status for record in records)
    category_counts = Counter(record.category for record in records)
    failures = [
        f"{record.document_id}: {record.error}"
        for record in records
        if record.status in {"failed", "failed_permanent"} and record.error
    ][:100]
    atomic_write_jsonl(paths["dataset"], records, root)
    _write_csv(paths["csv"], records, root)
    summary = LegiScanDocumentSummary(
        generated_at=datetime.now(timezone.utc),
        output_root=root.as_posix(),
        bill_archive_dir=paths["bill_archive"].as_posix(),
        document_archive_dir=paths["document_archive"].as_posix(),
        queue_path=paths["queue"].as_posix(),
        manifest_path=paths["manifest"].as_posix(),
        dataset_jsonl_path=paths["dataset"].as_posix(),
        dataset_csv_path=paths["csv"].as_posix(),
        summary_path=paths["summary"].as_posix(),
        discovered_total=len(items),
        run_attempted=run_stats.get("attempted", 0),
        run_downloaded=run_stats.get("downloaded", 0),
        run_skipped_existing=run_stats.get("skipped_existing", 0),
        run_failed=run_stats.get("failed", 0),
        run_failed_permanent=run_stats.get("failed_permanent", 0),
        run_pending_retry=run_stats.get("pending_retry", 0),
        attempted=sum(
            1
            for entry in manifest.values()
            if entry.status in {"downloaded", "failed", "failed_permanent", "pending_retry"}
        ),
        downloaded=status_counts.get("downloaded", 0),
        skipped_existing=status_counts.get("skipped_existing", 0),
        failed=status_counts.get("failed", 0),
        failed_permanent=status_counts.get("failed_permanent", 0),
        pending_retry=status_counts.get("pending_retry", 0),
        records_total=len(records),
        pending=status_counts.get("discovered", 0),
        max_documents=max_documents,
        discovery_only=discovery_only,
        category_counts=dict(sorted(category_counts.items())),
        status_counts=dict(sorted(status_counts.items())),
        failures=failures,
    )
    atomic_write_json(paths["summary"], summary, root)
    return summary


def build_parser() -> argparse.ArgumentParser:
    """Build the LegiScan document pipeline CLI parser."""

    parser = argparse.ArgumentParser(description="Download LegiScan bill document files.")
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    parser.add_argument("--max-documents", type=int)
    parser.add_argument("--year", type=int)
    parser.add_argument("--category", choices=["texts", "amendments", "supplements"])
    parser.add_argument("--discovery-only", action="store_true")
    parser.add_argument("--refresh-queue", action="store_true")
    parser.add_argument("--safe-bulk", action="store_true")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument(
        "--phase-order",
        default="texts,amendments,supplements",
        help="Comma-separated safe bulk phase order.",
    )
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--cooldown-seconds", type=float, default=900.0)
    parser.add_argument("--max-rate-limit-pauses", type=int, default=3)
    parser.add_argument("--rate-limit-delay-multiplier", type=float, default=2.0)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the LegiScan document pipeline CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(getattr(logging, args.log_level))
    try:
        if args.safe_bulk:
            safe_summary = run_legiscan_document_safe_bulk(
                args.output_root,
                batch_size=args.batch_size,
                delay=args.delay,
                timeout_seconds=args.timeout_seconds,
                max_retries=args.max_retries,
                cooldown_seconds=args.cooldown_seconds,
                max_rate_limit_pauses=args.max_rate_limit_pauses,
                rate_limit_delay_multiplier=args.rate_limit_delay_multiplier,
                max_batches=args.max_batches,
                phase_order=_parse_phase_order(args.phase_order),
                refresh_queue=args.refresh_queue,
            )
            if args.json:
                print(json.dumps(safe_summary.model_dump(mode="json"), indent=2, sort_keys=True))
            else:
                print(f"Safe bulk status: {safe_summary.status}")
                print(f"Downloaded this run: {safe_summary.run_downloaded}")
                print(f"Downloaded total: {safe_summary.final_downloaded}")
                print(f"Pending total: {safe_summary.final_pending}")
            if safe_summary.run_failed > 0:
                return 2
            if safe_summary.run_pending_retry > 0:
                return 3
            return 0
        summary = run_legiscan_document_pipeline(
            args.output_root,
            max_documents=args.max_documents,
            year=args.year,
            category=args.category,
            discovery_only=args.discovery_only,
            refresh_queue=args.refresh_queue,
            delay=args.delay,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
        )
    except Exception as exc:
        LOGGER.exception("LegiScan document pipeline failed: %s", exc)
        return 1
    if args.json:
        print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        print(f"Documents discovered: {summary.discovered_total}")
        print(f"Downloaded this run: {summary.run_downloaded}")
        print(f"Downloaded total: {summary.downloaded}")
        print(f"Pending: {summary.pending}")
    if summary.run_failed > 0:
        return 2
    if summary.run_pending_retry > 0:
        return 3
    return 0


def _download_items(
    items: list[LegiScanDocumentItem],
    manifest_path: Path,
    root: Path,
    *,
    max_documents: int | None,
    delay: float,
    timeout_seconds: float,
    max_retries: int,
) -> Counter[str]:
    """Download queued document items with manifest-backed resume."""

    manifest = _latest_manifest(manifest_path)
    run_stats: Counter[str] = Counter()
    client = GeodeHttpClient(
        config=GeodeHttpClientConfig(
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            throttle_delay_seconds=delay,
            base_delay=max(delay, 0.25),
            retry_statuses=RETRYABLE_SOURCE_STATUS_CODES,
            log_level=logging.DEBUG,
        )
    )
    items_attempted = 0
    for item in items:
        prior = manifest.get(item.document_id)
        if _should_skip_on_resume(item, prior):
            run_stats["skipped_existing"] += 1
            continue
        if max_documents is not None and items_attempted >= max_documents:
            break
        items_attempted += 1
        run_stats["attempted"] += 1
        started = datetime.now(timezone.utc)
        known_gap_reason = _known_unrecoverable_source_reason(item)
        if known_gap_reason is not None:
            entry = LegiScanDocumentManifestEntry(
                document_id=item.document_id,
                bill_id=item.bill_id,
                category=item.category,
                preferred_url=item.preferred_url,
                archive_path=item.archive_path,
                status="failed_permanent",
                size_bytes=0,
                downloaded_at=started,
                error=known_gap_reason,
            )
            _append_manifest(manifest_path, entry)
            manifest[item.document_id] = entry
            run_stats["failed_permanent"] += 1
            LOGGER.warning(
                "LegiScan document source skipped as unrecoverable document_id=%s url=%s "
                "reason=%s",
                item.document_id,
                item.preferred_url,
                known_gap_reason,
            )
            continue
        try:
            response = client.get(
                item.preferred_url,
                allowed_content_types=DEFAULT_CONTENT_TYPES,
                require_content=True,
            )
            content_type = _content_type(response.headers)
            invalid_reason = _invalid_response_reason(item, content_type, response.content)
            if invalid_reason is not None:
                entry = LegiScanDocumentManifestEntry(
                    document_id=item.document_id,
                    bill_id=item.bill_id,
                    category=item.category,
                    preferred_url=item.preferred_url,
                    archive_path=item.archive_path,
                    status="failed_permanent",
                    status_code=response.status_code,
                    content_type=content_type,
                    size_bytes=len(response.content),
                    downloaded_at=started,
                    error=invalid_reason,
                )
                _append_manifest(manifest_path, entry)
                manifest[item.document_id] = entry
                run_stats["failed_permanent"] += 1
                LOGGER.warning(
                    "LegiScan document source returned invalid content document_id=%s "
                    "url=%s content_type=%s reason=%s",
                    item.document_id,
                    item.preferred_url,
                    content_type,
                    invalid_reason,
                )
                continue
            target = Path(item.archive_path)
            _write_bytes(target, response.content)
            entry = LegiScanDocumentManifestEntry(
                document_id=item.document_id,
                bill_id=item.bill_id,
                category=item.category,
                preferred_url=item.preferred_url,
                archive_path=item.archive_path,
                status="downloaded",
                status_code=response.status_code,
                content_type=content_type,
                size_bytes=target.stat().st_size,
                sha256=sha256_file(target),
                downloaded_at=started,
            )
            _append_manifest(manifest_path, entry)
            manifest[item.document_id] = entry
            run_stats["downloaded"] += 1
        except GeodeHttpError as exc:
            if _is_retryable_source_failure(exc.status_code):
                status = "pending_retry"
            elif _is_permanent_source_failure(exc.status_code, item.preferred_url):
                status = "failed_permanent"
            else:
                status = "failed"
            entry = LegiScanDocumentManifestEntry(
                document_id=item.document_id,
                bill_id=item.bill_id,
                category=item.category,
                preferred_url=item.preferred_url,
                archive_path=item.archive_path,
                status=status,
                status_code=exc.status_code,
                size_bytes=0,
                downloaded_at=started,
                error=str(exc),
            )
            _append_manifest(manifest_path, entry)
            manifest[item.document_id] = entry
            run_stats[status] += 1
            if exc.is_rate_limited:
                LOGGER.warning(
                    "LegiScan document download stopped document_id=%s url=%s status=%s error=%s",
                    item.document_id,
                    item.preferred_url,
                    status,
                    exc,
                )
                LOGGER.warning(
                    "Stopping LegiScan document run after rate limit; resume later with "
                    "a lower request rate."
                )
                break
            LOGGER.warning(
                "LegiScan document download failed document_id=%s url=%s status=%s error=%s",
                item.document_id,
                item.preferred_url,
                status,
                exc,
            )
        except Exception as exc:
            entry = LegiScanDocumentManifestEntry(
                document_id=item.document_id,
                bill_id=item.bill_id,
                category=item.category,
                preferred_url=item.preferred_url,
                archive_path=item.archive_path,
                status="failed",
                status_code=getattr(exc, "status_code", None),
                size_bytes=0,
                downloaded_at=started,
                error=str(exc),
            )
            _append_manifest(manifest_path, entry)
            manifest[item.document_id] = entry
            run_stats["failed"] += 1
            LOGGER.warning(
                "LegiScan document download failed document_id=%s url=%s error=%s",
                item.document_id,
                item.preferred_url,
                exc,
            )
    return run_stats


def _item_from_source(
    source: dict,
    record: dict,
    bill_path: Path,
    archive_dir: Path,
    category: str,
    index: int,
) -> LegiScanDocumentItem | None:
    """Build a document item from one LegiScan document-like source object."""

    source_url = _clean_url(source.get("url"))
    state_link = _clean_url(source.get("state_link"))
    preferred_url = state_link or source_url
    if preferred_url is None or source_url is None:
        return None
    raw_doc_id = source.get("doc_id") or source.get("amendment_id") or source.get("id")
    doc_material = str(raw_doc_id or _url_identifier(preferred_url) or index)
    document_id = safe_archive_stem(f"{record['id']}_{category}_{doc_material}")
    extension = _extension_for(source, preferred_url)
    archive_path = (
        archive_dir
        / str(record["session"])
        / safe_archive_stem(record["id"])
        / category
        / f"{document_id}{extension}"
    )
    return LegiScanDocumentItem(
        document_id=document_id,
        bill_id=record["id"],
        session=record["session"],
        bill_number=record["bill_number"],
        title=record["title"],
        category=category,
        document_type=_optional_str(source.get("type")),
        document_date=_optional_str(source.get("date")),
        legiscan_doc_id=_optional_str(raw_doc_id),
        source_url=source_url,
        state_link=state_link,
        preferred_url=preferred_url,
        mime=_optional_str(source.get("mime")),
        expected_size=_optional_int(source.get("text_size")),
        text_hash=_optional_str(source.get("text_hash")),
        source_bill_path=bill_path.as_posix(),
        archive_path=archive_path.as_posix(),
    )


def _metadata_for(
    item: LegiScanDocumentItem,
    manifest_entry: LegiScanDocumentManifestEntry | None,
) -> LegiScanDocumentMetadata:
    """Build a normalized metadata row from item and latest manifest state."""

    status = "discovered"
    content_type = None
    size_bytes = 0
    checksum = None
    error = None
    downloaded_at = None
    if manifest_entry is not None:
        status = manifest_entry.status
        content_type = manifest_entry.content_type
        size_bytes = manifest_entry.size_bytes
        checksum = manifest_entry.sha256
        error = manifest_entry.error
        downloaded_at = manifest_entry.downloaded_at
        invalid_reason = _invalid_manifest_download_reason(item, manifest_entry)
        if invalid_reason is not None:
            status = "failed_permanent"
            error = error or invalid_reason
        if status == "failed":
            if _is_retryable_source_failure(manifest_entry.status_code):
                status = "pending_retry"
            elif _is_permanent_source_failure(
                manifest_entry.status_code,
                manifest_entry.preferred_url,
            ):
                status = "failed_permanent"
    if status == "downloaded" and not Path(item.archive_path).exists():
        status = "pending_retry"
        error = "manifest says downloaded but archive file is missing"
    return LegiScanDocumentMetadata(
        document_id=item.document_id,
        bill_id=item.bill_id,
        session=item.session,
        bill_number=item.bill_number,
        title=item.title,
        category=item.category,
        document_type=item.document_type,
        document_date=item.document_date,
        source_url=item.source_url,
        state_link=item.state_link,
        preferred_url=item.preferred_url,
        archive_path=item.archive_path,
        status=status,
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=checksum,
        error=error,
        downloaded_at=downloaded_at,
    )


def _paths(root: Path) -> dict[str, Path]:
    """Return canonical paths for the LegiScan document pipeline."""

    bill_archive = raw_connector_dir(root / RAW_ARCHIVE_DIR, "legiscan")
    document_archive = raw_connector_dir(root / RAW_ARCHIVE_DIR, "legiscan_documents")
    documents_dir = root / LEGISLATION_LAYER / DOCUMENTS_DIR
    return {
        "bill_archive": bill_archive,
        "document_archive": document_archive,
        "queue": document_archive / DOCUMENT_QUEUE_NAME,
        "manifest": document_archive / DOCUMENT_MANIFEST_NAME,
        "dataset": documents_dir / DOCUMENT_DATASET_NAME,
        "csv": documents_dir / DOCUMENT_CSV_NAME,
        "summary": documents_dir / DOCUMENT_SUMMARY_NAME,
        "safe_bulk_report": documents_dir / SAFE_BULK_REPORT_NAME,
        "safe_bulk_batches": documents_dir / SAFE_BULK_BATCHES_NAME,
    }


def _read_queue(path: Path) -> list[LegiScanDocumentItem]:
    """Read document queue items from JSONL."""

    if not path.exists():
        return []
    return [
        LegiScanDocumentItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _filter_items(
    items: list[LegiScanDocumentItem],
    *,
    year: int | None,
    category: str | None,
) -> list[LegiScanDocumentItem]:
    """Apply lightweight filters to queued document items."""

    filtered = items
    if year is not None:
        filtered = [item for item in filtered if item.session == str(year)]
    if category is not None:
        filtered = [item for item in filtered if item.category == category]
    return filtered


def _count_remaining_by_category(root: Path, category: str) -> int:
    """Return retryable or undiscovered item count for one category."""

    paths = _paths(root)
    manifest = _latest_manifest(paths["manifest"])
    remaining = 0
    for item in _read_queue(paths["queue"]):
        if item.category != category:
            continue
        entry = manifest.get(item.document_id)
        if not _should_skip_on_resume(item, entry):
            remaining += 1
    return remaining


def _append_safe_bulk_batch(
    path: Path,
    phase: str,
    batch_number: int,
    before: LegiScanDocumentSummary,
    after: LegiScanDocumentSummary,
) -> None:
    """Append one safe-bulk batch report row."""

    payload = {
        "batch_number": batch_number,
        "phase": phase,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "before_downloaded": before.downloaded,
        "before_pending": before.pending,
        "before_pending_retry": before.pending_retry,
        "before_failed_permanent": before.failed_permanent,
        "run_attempted": after.run_attempted,
        "run_downloaded": after.run_downloaded,
        "run_failed": after.run_failed,
        "run_failed_permanent": after.run_failed_permanent,
        "run_pending_retry": after.run_pending_retry,
        "after_downloaded": after.downloaded,
        "after_pending": after.pending,
        "after_pending_retry": after.pending_retry,
        "after_failed_permanent": after.failed_permanent,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _parse_phase_order(value: str) -> list[str]:
    """Parse a comma-separated phase order option."""

    phases = [part.strip() for part in value.split(",") if part.strip()]
    _validate_phases(phases)
    return phases


def _validate_phases(phases: list[str]) -> None:
    """Validate safe-bulk phase names."""

    allowed = set(SAFE_BULK_DEFAULT_PHASES)
    invalid = [phase for phase in phases if phase not in allowed]
    if invalid:
        raise ValueError(f"invalid phase(s): {', '.join(invalid)}")
    if len(set(phases)) != len(phases):
        raise ValueError("duplicate phases are not allowed")


def _latest_manifest(path: Path) -> dict[str, LegiScanDocumentManifestEntry]:
    """Return latest manifest entry by document ID."""

    if not path.exists():
        return {}
    latest: dict[str, LegiScanDocumentManifestEntry] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = LegiScanDocumentManifestEntry.model_validate_json(line)
            latest[entry.document_id] = entry
    return latest


def _should_skip_on_resume(
    item: LegiScanDocumentItem,
    manifest_entry: LegiScanDocumentManifestEntry | None,
) -> bool:
    """Return whether a document has a terminal state that should not be retried."""

    if manifest_entry is None:
        return False
    if _invalid_manifest_download_reason(item, manifest_entry) is not None:
        return True
    if manifest_entry.status == "downloaded":
        target = Path(item.archive_path)
        return bool(target.exists() and manifest_entry.sha256 == sha256_file(target))
    if manifest_entry.status == "failed_permanent":
        return True
    return bool(
        manifest_entry.status == "failed"
        and _is_permanent_source_failure(
            manifest_entry.status_code,
            manifest_entry.preferred_url,
        )
    )


def _is_permanent_source_failure(status_code: int | None, url: str) -> bool:
    """Return whether a failed source URL should not be retried automatically."""

    if status_code in PERMANENT_MISSING_STATUS_CODES:
        return True
    if status_code == 403:
        return urlparse(url).hostname in PERMANENT_BLOCKED_HOSTS
    return False


def _is_retryable_source_failure(status_code: int | None) -> bool:
    """Return whether a source failure should be retried in a later run."""

    return status_code in RETRYABLE_SOURCE_STATUS_CODES


def _invalid_response_reason(
    item: LegiScanDocumentItem,
    content_type: str | None,
    content: bytes,
) -> str | None:
    """Return a terminal content error when a response is not the expected document."""

    if not _expects_binary_document(item) or not _is_html_content_type(content_type):
        return None
    if _is_legacy_archive_host(item.preferred_url):
        return LEGACY_ARCHIVE_WRAPPER_ERROR
    if _looks_like_archive_wrapper(content):
        return "Colorado archive returned an HTML wrapper instead of the source document"
    return None


def _known_unrecoverable_source_reason(item: LegiScanDocumentItem) -> str | None:
    """Return a terminal reason for source URLs that should not be requested again."""

    if _expects_binary_document(item) and _is_legacy_archive_host(item.preferred_url):
        return LEGACY_ARCHIVE_UNRECOVERABLE_ERROR
    return None


def _invalid_manifest_download_reason(
    item: LegiScanDocumentItem,
    manifest_entry: LegiScanDocumentManifestEntry,
) -> str | None:
    """Return a terminal content error for stale manifest rows misclassified as downloads."""

    if manifest_entry.status != "downloaded":
        return None
    if not _expects_binary_document(item) or not _is_html_content_type(manifest_entry.content_type):
        return None
    if _is_legacy_archive_host(manifest_entry.preferred_url):
        return LEGACY_ARCHIVE_WRAPPER_ERROR
    target = Path(item.archive_path)
    if target.exists() and _path_looks_like_archive_wrapper(target):
        return "Colorado archive wrapper was previously stored as a document"
    return None


def _expects_binary_document(item: LegiScanDocumentItem) -> bool:
    """Return whether the item should resolve to a binary document, not HTML."""

    suffixes = {
        Path(urlparse(item.preferred_url).path).suffix.lower(),
        Path(item.archive_path).suffix.lower(),
    }
    if suffixes & BINARY_DOCUMENT_EXTENSIONS:
        return True
    mime = (item.mime or "").casefold()
    return any(token in mime for token in ("pdf", "msword", "wordprocessingml"))


def _is_html_content_type(content_type: str | None) -> bool:
    """Return whether a content type represents HTML."""

    return (content_type or "").casefold() in HTML_CONTENT_TYPES


def _is_legacy_archive_host(url: str) -> bool:
    """Return whether a URL points at the old Colorado legislative archive host."""

    return urlparse(url).hostname in PERMANENT_BLOCKED_HOSTS


def _looks_like_archive_wrapper(content: bytes) -> bool:
    """Return whether HTML content is the Colorado legislative archive wrapper page."""

    preview = content[:8192].lower()
    return any(marker in preview for marker in ARCHIVE_WRAPPER_MARKERS)


def _path_looks_like_archive_wrapper(path: Path) -> bool:
    """Return whether a stored file begins with the known archive wrapper HTML."""

    try:
        return _looks_like_archive_wrapper(path.read_bytes()[:8192])
    except OSError:
        return False


def _append_manifest(path: Path, entry: LegiScanDocumentManifestEntry) -> None:
    """Append one document manifest row."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(entry.model_dump_json() + "\n")


def _write_bytes(path: Path, content: bytes) -> None:
    """Write raw document bytes with atomic replacement."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _unique_tmp(path)
    try:
        tmp_path.write_bytes(content)
        _replace_with_retry(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _write_jsonl_raw(path: Path, records: list[BaseModel]) -> None:
    """Write a JSONL runtime artifact inside the raw archive."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _unique_tmp(path)
    try:
        content = "\n".join(record.model_dump_json() for record in records)
        tmp_path.write_text((content + "\n") if content else "", encoding="utf-8", newline="\n")
        _replace_with_retry(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _write_csv(path: Path, records: list[LegiScanDocumentMetadata], root: Path) -> None:
    """Write document metadata CSV companion."""

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


def _replace_with_retry(source: Path, target: Path) -> None:
    """Replace a file while tolerating short Windows/OneDrive locks."""

    for attempt in range(1, ARCHIVE_REPLACE_ATTEMPTS + 1):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == ARCHIVE_REPLACE_ATTEMPTS:
                raise
            time.sleep(ARCHIVE_REPLACE_DELAY_SECONDS * attempt)


def _unique_tmp(path: Path) -> Path:
    """Return a unique adjacent temp file path."""

    return path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")


def _extension_for(source: dict, url: str) -> str:
    """Return an archive extension for one source document."""

    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix:
        return suffix
    mime = str(source.get("mime") or "").casefold()
    if "pdf" in mime:
        return ".pdf"
    if "wordprocessingml" in mime:
        return ".docx"
    if "msword" in mime:
        return ".doc"
    if "html" in mime:
        return ".html"
    return ".bin"


def _content_type(headers: dict[str, str]) -> str | None:
    """Return response content type without parameters."""

    for key, value in headers.items():
        if key.casefold() == "content-type":
            return value.split(";", 1)[0].strip()
    return None


def _url_identifier(url: str) -> str:
    """Return a deterministic short identifier for a URL."""

    match = re.search(r"/id/(\d+)", url)
    if match:
        return match.group(1)
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _clean_url(value: object) -> str | None:
    """Return a cleaned URL string when present."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_str(value: object) -> str | None:
    """Return a non-empty string or ``None``."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    """Return an integer value when present."""

    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _validate_options(
    max_documents: int | None,
    delay: float,
    timeout_seconds: float,
    max_retries: int,
) -> None:
    """Validate CLI options."""

    if max_documents is not None and max_documents < 0:
        raise ValueError("--max-documents cannot be negative")
    if delay < 0:
        raise ValueError("--delay cannot be negative")
    if timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive")
    if max_retries < 1:
        raise ValueError("--max-retries must be at least 1")


def _validate_safe_bulk_options(
    cooldown_seconds: float,
    max_rate_limit_pauses: int,
    rate_limit_delay_multiplier: float,
) -> None:
    """Validate safe bulk pacing options."""

    if cooldown_seconds < 0:
        raise ValueError("--cooldown-seconds cannot be negative")
    if max_rate_limit_pauses < 0:
        raise ValueError("--max-rate-limit-pauses cannot be negative")
    if rate_limit_delay_multiplier < 1:
        raise ValueError("--rate-limit-delay-multiplier must be at least 1")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
