"""Phased CCR bulk acquisition workflow and CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, ConfigDict, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.connectors.archive_paths import (
    ccr_rule_document_path,
    download_manifest_path,
)
from geode.connectors.ccr_dataset import write_ccr_dataset
from geode.connectors.ccr_industry_filter import write_ccr_industry_tags
from geode.connectors.ccr_scraper import (
    CCRBlockedResponseError,
    CCRDownloadError,
    CCRRuleEntry,
    iter_rule_index_entries,
    resolve_rule_info_page,
    download_rule,
    _canonical_source_url,
    reconcile_download_state,
    _session_or_client,
)
from geode.net.http_client import (
    DEFAULT_MAX_RETRY_DELAY_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    GeodeHttpAttempt,
    GeodeThrottle,
    GeodeThrottleConfig,
)
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, load_json
from geode.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)

QUEUE_NAME = "ccr_bulk_queue.jsonl"
CHECKPOINT_NAME = "ccr_bulk_checkpoint.json"
SUMMARY_NAME = "ccr_bulk_summary.json"
FAILURES_NAME = "ccr_bulk_failures.jsonl"
REGULATIONS_LAYER = "02_Regulations_CCR"
INVENTORY_DIR_NAME = "_inventory"
INVENTORY_MANIFEST_NAME = "ccr_inventory_manifest.jsonl"
INVENTORY_QUALITY_NAME = "ccr_inventory_quality.json"
CURRENT_ASSET_SCOPE = "current"

TERMINAL_STATUSES = {
    "downloaded",
    "skipped_existing",
    "failed",
    "failed_permanent",
    "blocked",
}


@dataclass(frozen=True)
class CCRBulkConfig:
    """Configuration for one phased CCR bulk acquisition run."""

    output_root: Path
    max_items: int | None = None
    resume: bool = True
    discovery_only: bool = False
    max_agencies: int | None = None
    discovery_delay: float = 0.5
    discovery_delay_jitter_seconds: float = 0.1
    download_delay: float = 1.0
    download_delay_jitter_seconds: float = 0.25
    max_retries: int = 4
    base_delay: float = 2.0
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS
    retry_jitter_ratio: float = 0.25
    write_industry_tags: bool = True
    client: Any | None = None


class CCRBulkQueueEvent(BaseModel):
    """Append-only queue event for one CCR work item."""

    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=0)
    timestamp: datetime
    item_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    ccr_number: str = Field(min_length=1)
    department: str | None = None
    agency: str | None = None
    source_page_url: str
    browse_source_url: str | None = None
    pdf_url: str | None = None
    docx_url: str | None = None
    preferred_url: str | None = None
    archive_path: str | None = None
    error: str | None = None


class CCRInventoryManifestRow(BaseModel):
    """Canonical persisted CCR inventory row for one discovered asset target."""

    model_config = ConfigDict(extra="forbid")

    manifest_row_id: str = Field(min_length=1)
    manifest_row_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    item_id: str = Field(min_length=1)
    department_name: str | None = None
    department_id: str | None = None
    agency_name: str | None = None
    agency_id: str | None = None
    division_name: str | None = None
    browse_source_url: str | None = None
    ccr_number: str = Field(min_length=1)
    rule_title: str | None = None
    rule_detail_url: str | None = None
    rule_id: str | None = None
    status_markers: list[str] = Field(default_factory=list)
    asset_scope: str = CURRENT_ASSET_SCOPE
    asset_format: str | None = None
    download_url: str | None = None
    effective_date: str | None = None
    filing_type: str | None = None
    register_publication_date: str | None = None
    edocket_tracking_number: str | None = None
    is_current_version: bool | None = None
    is_preferred_asset: bool | None = None
    source_page_url: str
    discovered_at: datetime
    resolved_at: datetime | None = None
    inventory_status: str = Field(min_length=1)
    queue_status: str = Field(min_length=1)
    archive_path: str | None = None
    error: str | None = None


class CCRInventoryFieldCoverage(BaseModel):
    """Population counts for one CCR inventory field."""

    model_config = ConfigDict(extra="forbid")

    field_name: str = Field(min_length=1)
    total: int = Field(ge=0)
    populated: int = Field(ge=0)
    missing: int = Field(ge=0)
    populated_ratio: float = Field(ge=0.0, le=1.0)


class CCRInventoryQualityReport(BaseModel):
    """Generated QA evidence for a CCR inventory manifest."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    output_root: str
    inventory_manifest_path: str
    queue_path: str
    run_status: str
    max_items: int | None = None
    max_agencies: int | None = None
    run_capped_by_max_items: bool
    run_capped_by_max_agencies: bool
    uncapped_discovery_requested: bool
    uncapped_discovery_completed: bool
    traversal_validation_status: str = Field(min_length=1)
    field_population_status: str = Field(min_length=1)
    queue_items_total: int = Field(ge=0)
    inventory_rows_total: int = Field(ge=0)
    download_targets_total: int = Field(ge=0)
    unique_department_names_total: int = Field(ge=0)
    unique_department_ids_total: int = Field(ge=0)
    unique_agency_names_total: int = Field(ge=0)
    unique_agency_ids_total: int = Field(ge=0)
    unique_browse_source_urls_total: int = Field(ge=0)
    unique_rule_series_total: int = Field(ge=0)
    unique_rule_detail_urls_total: int = Field(ge=0)
    asset_format_counts: dict[str, int] = Field(default_factory=dict)
    queue_status_counts: dict[str, int] = Field(default_factory=dict)
    inventory_status_counts: dict[str, int] = Field(default_factory=dict)
    field_coverage: dict[str, CCRInventoryFieldCoverage] = Field(default_factory=dict)
    duplicate_manifest_row_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CCRBulkSummary(BaseModel):
    """Deterministic summary from a phased CCR bulk run."""

    model_config = ConfigDict(extra="forbid")

    started_at: datetime
    completed_at: datetime
    status: str
    output_root: str
    archive_dir: str
    queue_path: str
    checkpoint_path: str
    summary_path: str
    failure_path: str
    manifest_path: str
    inventory_dir: str
    inventory_manifest_path: str
    inventory_quality_path: str
    dataset_jsonl_path: str | None = None
    dataset_csv_path: str | None = None
    dataset_summary_path: str | None = None
    normalized_records_dir: str | None = None
    normalized_records_jsonl_path: str | None = None
    normalized_meta_path: str | None = None
    normalized_index_path: str | None = None
    normalized_summary_path: str | None = None
    normalized_records_total: int = Field(default=0, ge=0)
    tagged_jsonl_path: str | None = None
    tagged_csv_path: str | None = None
    tag_summary_path: str | None = None
    tagged_records_total: int = Field(default=0, ge=0)
    tagged_total: int = Field(default=0, ge=0)
    untagged_total: int = Field(default=0, ge=0)
    resume: bool
    discovery_only: bool
    max_items: int | None = None
    queue_items_total: int = Field(ge=0)
    discovered: int = Field(default=0, ge=0)
    indexed: int = Field(ge=0)
    resolved: int = Field(ge=0)
    attempted: int = Field(ge=0)
    downloaded: int = Field(ge=0)
    skipped_existing: int = Field(ge=0)
    failed: int = Field(ge=0)
    failed_permanent: int = Field(default=0, ge=0)
    blocked: int = Field(ge=0)
    pending_retry: int = Field(default=0, ge=0)
    retry_count: int = Field(ge=0)
    pending: int = Field(ge=0)
    inventory_rows_total: int = Field(default=0, ge=0)
    inventory_download_targets: int = Field(default=0, ge=0)
    traversal_validation_status: str | None = None
    field_population_status: str | None = None


@dataclass(frozen=True)
class _BulkPaths:
    output_root: Path
    archive_dir: Path
    inventory_dir: Path
    queue_path: Path
    checkpoint_path: Path
    summary_path: Path
    failure_path: Path
    manifest_path: Path
    inventory_manifest_path: Path
    inventory_quality_path: Path


@dataclass
class _RetryCounter:
    retry_count: int = 0

    def record_retry(self, attempt: GeodeHttpAttempt) -> None:
        """Record one retry attempt."""

        self.retry_count += 1


@dataclass
class _RunCounts:
    indexed: int = 0
    resolved: int = 0
    attempted: int = 0
    downloaded: int = 0
    skipped_existing: int = 0
    failed: int = 0
    failed_permanent: int = 0
    blocked: int = 0


@dataclass(frozen=True)
class _AssetTarget:
    asset_format: str | None
    download_url: str | None
    is_preferred_asset: bool | None


@dataclass(frozen=True)
class _QueueHistory:
    latest_by_id: dict[str, CCRBulkQueueEvent]
    first_timestamp_by_id: dict[str, datetime]
    resolved_timestamp_by_id: dict[str, datetime]
    order: list[str]


def run_ccr_bulk(config: CCRBulkConfig) -> CCRBulkSummary:
    """Run phased CCR bulk acquisition with queue/checkpoint artifacts."""

    _validate_config(config)
    paths = _bulk_paths(config.output_root)
    paths.archive_dir.mkdir(parents=True, exist_ok=True)
    if not config.resume:
        _reset_artifacts(paths)

    started_at = datetime.now(timezone.utc)
    state, order, next_sequence = _load_queue_state(paths.queue_path)
    counts = _RunCounts()
    retry_counter = _RetryCounter()
    session = _session_or_client(
        config.client,
        max_retries=config.max_retries,
        base_delay=config.base_delay,
        timeout_seconds=config.timeout_seconds,
        max_retry_delay_seconds=config.max_retry_delay_seconds,
        retry_jitter_ratio=config.retry_jitter_ratio,
        retry_hook=retry_counter.record_retry,
    )
    download_throttle = GeodeThrottle(
        GeodeThrottleConfig(
            delay_seconds=config.download_delay,
            jitter_seconds=config.download_delay_jitter_seconds,
            label="ccr_bulk_download",
        )
    )
    status = "completed"
    inventory_rows: list[CCRInventoryManifestRow] = []
    quality_report: CCRInventoryQualityReport | None = None

    try:
        next_sequence, status = _discover_queue_entries(
            paths,
            session,
            config,
            counts,
            retry_counter,
            next_sequence,
            state,
            order,
        )
        next_sequence = _resolve_queue_entries(
            paths,
            session,
            config,
            counts,
            retry_counter,
            next_sequence,
            state,
            order,
        )
        inventory_rows = write_ccr_inventory_manifest(paths)
        if not config.discovery_only:
            next_sequence = _retrieve_inventory_entries(
                paths,
                session,
                config,
                counts,
                next_sequence,
                state,
                order,
                download_throttle,
            )
            inventory_rows = write_ccr_inventory_manifest(paths)
    except KeyboardInterrupt:
        status = "interrupted"
        _write_checkpoint(paths, status, None, counts, retry_counter)
        raise

    quality_report = write_ccr_inventory_quality_report(
        paths,
        config,
        status,
        inventory_rows,
        state,
    )
    summary = _build_summary(
        config,
        paths,
        started_at,
        status,
        counts,
        retry_counter,
        state,
        inventory_rows,
        quality_report,
    )
    dataset_summary = write_ccr_dataset(paths.output_root)
    summary_updates: dict[str, Any] = {
        "dataset_jsonl_path": dataset_summary.metadata_jsonl_path,
        "dataset_csv_path": dataset_summary.metadata_csv_path,
        "dataset_summary_path": dataset_summary.summary_path,
        "normalized_records_dir": dataset_summary.normalized_records_dir,
        "normalized_records_jsonl_path": dataset_summary.normalized_records_jsonl_path,
        "normalized_meta_path": dataset_summary.normalized_meta_path,
        "normalized_index_path": dataset_summary.normalized_index_path,
        "normalized_summary_path": dataset_summary.normalized_summary_path,
        "normalized_records_total": dataset_summary.normalized_records_total,
    }
    if config.write_industry_tags:
        tag_summary = write_ccr_industry_tags(paths.output_root)
        summary_updates.update(
            {
                "tagged_jsonl_path": tag_summary.tagged_jsonl_path,
                "tagged_csv_path": tag_summary.tagged_csv_path,
                "tag_summary_path": tag_summary.summary_path,
                "tagged_records_total": tag_summary.records_total,
                "tagged_total": tag_summary.tagged_total,
                "untagged_total": tag_summary.untagged_total,
            }
        )
    summary = summary.model_copy(update=summary_updates)
    _update_ccr_master_manifest(paths.output_root, summary, config)
    _write_json(paths.summary_path, summary.model_dump(mode="json"))
    _write_checkpoint(paths, status, None, counts, retry_counter, summary=summary)
    LOGGER.info(
        "CCR bulk workflow status=%s indexed=%s resolved=%s attempted=%s "
        "downloaded=%s skipped=%s failed=%s blocked=%s queue=%s",
        summary.status,
        summary.indexed,
        summary.resolved,
        summary.attempted,
        summary.downloaded,
        summary.skipped_existing,
        summary.failed,
        summary.blocked,
        summary.queue_path,
    )
    return summary


def _update_ccr_master_manifest(
    root: Path,
    summary: CCRBulkSummary,
    config: CCRBulkConfig,
) -> None:
    """Update the CCR layer manifest after a completed non-dry-run refresh."""

    if config.discovery_only or summary.status != "completed" or summary.normalized_records_total == 0:
        return
    manifest_path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    if not manifest_path.exists():
        return
    payload = load_json(manifest_path)
    if not isinstance(payload, dict):
        raise ValueError("MASTER_MANIFEST.json must contain an object")
    refreshed_date = summary.completed_at.date().isoformat()
    for layer in payload.get("data_layers", []):
        if isinstance(layer, dict) and layer.get("id") == REGULATIONS_LAYER:
            layer["record_count"] = summary.normalized_records_total
            layer["last_checked"] = refreshed_date
            layer["last_ingested"] = refreshed_date
            layer["status"] = "ready"
            break
    atomic_write_json(manifest_path, payload, root)


def build_parser() -> argparse.ArgumentParser:
    """Build the CCR bulk workflow CLI parser."""

    parser = argparse.ArgumentParser(description="Run phased CCR bulk acquisition.")
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--max-agencies", type=int)
    parser.add_argument("--resume", dest="resume", action="store_true", default=True)
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.add_argument(
        "--discovery-only",
        "--dry-run",
        dest="discovery_only",
        action="store_true",
        help="Build/resolve the queue but do not fetch document content.",
    )
    parser.add_argument("--discovery-delay", type=float, default=0.5)
    parser.add_argument("--discovery-delay-jitter", type=float, default=0.1)
    parser.add_argument("--download-delay", type=float, default=1.0)
    parser.add_argument("--download-delay-jitter", type=float, default=0.25)
    parser.add_argument("--http-timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--http-max-retries", type=int, default=4)
    parser.add_argument("--http-base-delay", type=float, default=2.0)
    parser.add_argument(
        "--http-max-retry-delay-seconds",
        type=float,
        default=DEFAULT_MAX_RETRY_DELAY_SECONDS,
    )
    parser.add_argument("--http-retry-jitter-ratio", type=float, default=0.25)
    parser.add_argument(
        "--write-industry-tags",
        dest="write_industry_tags",
        action="store_true",
        default=True,
        help="Write CCR tagged dataset outputs after normalized dataset generation.",
    )
    parser.add_argument(
        "--no-industry-tags",
        dest="write_industry_tags",
        action="store_false",
        help="Skip CCR industry tagging during the bulk run.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument("--json", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace) -> CCRBulkConfig:
    """Convert parsed CLI arguments into CCR bulk workflow config."""

    return CCRBulkConfig(
        output_root=args.output_root,
        max_items=args.max_items,
        resume=args.resume,
        discovery_only=args.discovery_only,
        max_agencies=args.max_agencies,
        discovery_delay=args.discovery_delay,
        discovery_delay_jitter_seconds=args.discovery_delay_jitter,
        download_delay=args.download_delay,
        download_delay_jitter_seconds=args.download_delay_jitter,
        max_retries=args.http_max_retries,
        base_delay=args.http_base_delay,
        timeout_seconds=args.http_timeout_seconds,
        max_retry_delay_seconds=args.http_max_retry_delay_seconds,
        retry_jitter_ratio=args.http_retry_jitter_ratio,
        write_industry_tags=args.write_industry_tags,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the CCR bulk workflow CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(getattr(logging, args.log_level))
    try:
        summary = run_ccr_bulk(config_from_args(args))
    except ValueError as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        LOGGER.warning("CCR bulk workflow interrupted.")
        return 130

    if args.json:
        print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        _print_summary(summary)
    return 0 if summary.failed == 0 and summary.blocked == 0 else 2


def _discover_queue_entries(
    paths: _BulkPaths,
    session: Any,
    config: CCRBulkConfig,
    counts: _RunCounts,
    retry_counter: _RetryCounter,
    next_sequence: int,
    state: dict[str, CCRBulkQueueEvent],
    order: list[str],
) -> tuple[int, str]:
    """Traverse CCR browse pages and persist newly discovered queue events."""

    if _queue_limit_reached(order, config.max_items):
        return next_sequence, "completed"
    status = "completed"
    for entry in iter_rule_index_entries(
        client=session,
        max_agencies=config.max_agencies,
        request_delay=config.discovery_delay,
        request_delay_jitter_seconds=config.discovery_delay_jitter_seconds,
        max_retries=config.max_retries,
        base_delay=config.base_delay,
        timeout_seconds=config.timeout_seconds,
        max_retry_delay_seconds=config.max_retry_delay_seconds,
        retry_jitter_ratio=config.retry_jitter_ratio,
    ):
        if entry.canonical_id in state:
            continue
        if _queue_limit_reached(order, config.max_items):
            status = "paused"
            break
        event = _queue_event(
            sequence=next_sequence,
            entry=entry,
            status="discovered",
            phase="discovery",
        )
        order.append(event.item_id)
        next_sequence = _append_queue_event(paths.queue_path, event, state)
        counts.indexed += 1
        _write_checkpoint(paths, "running", event, counts, retry_counter)
    return next_sequence, status


def _resolve_queue_entries(
    paths: _BulkPaths,
    session: Any,
    config: CCRBulkConfig,
    counts: _RunCounts,
    retry_counter: _RetryCounter,
    next_sequence: int,
    state: dict[str, CCRBulkQueueEvent],
    order: list[str],
) -> int:
    """Resolve queued rule-info pages after the discovery pass is persisted."""

    for item_id in _limited_order(order, config.max_items):
        event = state[item_id]
        if event.status not in {"indexed", "discovered"}:
            continue
        next_sequence = _resolve_queue_event(
            event,
            paths,
            session,
            config,
            counts,
            retry_counter,
            next_sequence,
            state,
        )
    return next_sequence


def _resolve_queue_event(
    event: CCRBulkQueueEvent,
    paths: _BulkPaths,
    session: Any,
    config: CCRBulkConfig,
    counts: _RunCounts,
    retry_counter: _RetryCounter,
    next_sequence: int,
    state: dict[str, CCRBulkQueueEvent],
) -> int:
    """Resolve one discovered queue event into downloadable asset URLs."""

    entry = _entry_from_event(event)
    try:
        resolved = _resolve_entry(entry, session, config)
    except Exception as exc:
        failed = _queue_event(
            sequence=next_sequence,
            entry=entry,
            status="failed_permanent",
            phase="detail_resolution",
            error=exc,
        )
        next_sequence = _append_queue_event(paths.queue_path, failed, state)
        _append_failure(paths.failure_path, failed)
        counts.failed += 1
        counts.failed_permanent += 1
        _write_checkpoint(paths, "running", failed, counts, retry_counter)
        return next_sequence

    resolved_event = _queue_event(
        sequence=next_sequence,
        entry=resolved,
        status="resolved",
        phase="detail_resolution",
        archive_path=_target_path(paths.archive_dir, resolved),
    )
    next_sequence = _append_queue_event(paths.queue_path, resolved_event, state)
    counts.resolved += 1
    _write_checkpoint(paths, "running", resolved_event, counts, retry_counter)
    return next_sequence


def _retrieve_inventory_entries(
    paths: _BulkPaths,
    session: Any,
    config: CCRBulkConfig,
    counts: _RunCounts,
    next_sequence: int,
    state: dict[str, CCRBulkQueueEvent],
    order: list[str],
    download_throttle: GeodeThrottle,
) -> int:
    """Retrieve documents by consuming the persisted canonical inventory manifest."""

    eligible_item_ids = set(_limited_order(order, config.max_items))
    for item_id, entry in _download_entries_from_inventory(paths.inventory_manifest_path):
        if item_id not in eligible_item_ids:
            continue
        event = state.get(item_id)
        if not _should_attempt_inventory_retrieval(event):
            continue
        attempted_before = counts.attempted
        next_sequence = _retrieve_entry(
            entry,
            paths,
            session,
            config,
            counts,
            next_sequence,
            state,
        )
        if counts.attempted > attempted_before:
            download_throttle.wait(reason="ccr_bulk_content_retrieval")
    return next_sequence


def _should_attempt_inventory_retrieval(event: CCRBulkQueueEvent | None) -> bool:
    """Return whether an inventory item should be retrieved or repaired on resume."""

    if event is None:
        return False
    if event.status == "resolved":
        return True
    return (
        event.status == "failed_permanent"
        and event.phase == "content_retrieval"
        and not _event_archive_exists(event)
    )


def _event_archive_exists(event: CCRBulkQueueEvent) -> bool:
    """Return whether a queue event points at an existing archive artifact."""

    if not event.archive_path:
        return False
    return Path(event.archive_path).exists()


def write_ccr_inventory_manifest(paths: _BulkPaths) -> list[CCRInventoryManifestRow]:
    """Materialize the canonical CCR inventory manifest from the bulk queue."""

    rows = _inventory_rows_from_queue(paths.queue_path)
    atomic_write_jsonl(paths.inventory_manifest_path, rows, paths.output_root)
    LOGGER.info(
        "Wrote CCR inventory manifest rows=%s path=%s",
        len(rows),
        paths.inventory_manifest_path,
    )
    return rows


def write_ccr_inventory_quality_report(
    paths: _BulkPaths,
    config: CCRBulkConfig,
    run_status: str,
    inventory_rows: list[CCRInventoryManifestRow],
    state: dict[str, CCRBulkQueueEvent],
) -> CCRInventoryQualityReport:
    """Write generated QA evidence for traversal and field population."""

    report = _build_inventory_quality_report(
        paths,
        config,
        run_status,
        inventory_rows,
        state,
    )
    _write_json(paths.inventory_quality_path, report.model_dump(mode="json"))
    LOGGER.info(
        "Wrote CCR inventory quality report status=%s field_status=%s path=%s",
        report.traversal_validation_status,
        report.field_population_status,
        paths.inventory_quality_path,
    )
    return report


def _build_inventory_quality_report(
    paths: _BulkPaths,
    config: CCRBulkConfig,
    run_status: str,
    inventory_rows: list[CCRInventoryManifestRow],
    state: dict[str, CCRBulkQueueEvent],
) -> CCRInventoryQualityReport:
    """Build traversal and field-population evidence for an inventory manifest."""

    field_coverage = _inventory_field_coverage(inventory_rows)
    duplicate_ids = _duplicate_manifest_row_ids(inventory_rows)
    warnings = _inventory_quality_warnings(
        config,
        run_status,
        inventory_rows,
        field_coverage,
        duplicate_ids,
    )
    uncapped_requested = config.max_items is None and config.max_agencies is None
    uncapped_completed = uncapped_requested and run_status == "completed"
    return CCRInventoryQualityReport(
        generated_at=datetime.now(timezone.utc),
        output_root=paths.output_root.as_posix(),
        inventory_manifest_path=paths.inventory_manifest_path.as_posix(),
        queue_path=paths.queue_path.as_posix(),
        run_status=run_status,
        max_items=config.max_items,
        max_agencies=config.max_agencies,
        run_capped_by_max_items=config.max_items is not None,
        run_capped_by_max_agencies=config.max_agencies is not None,
        uncapped_discovery_requested=uncapped_requested,
        uncapped_discovery_completed=uncapped_completed,
        traversal_validation_status=_traversal_validation_status(
            run_status,
            config,
            inventory_rows,
        ),
        field_population_status=_field_population_status(field_coverage),
        queue_items_total=len(state),
        inventory_rows_total=len(inventory_rows),
        download_targets_total=sum(1 for row in inventory_rows if row.download_url),
        unique_department_names_total=_unique_count(row.department_name for row in inventory_rows),
        unique_department_ids_total=_unique_count(row.department_id for row in inventory_rows),
        unique_agency_names_total=_unique_count(row.agency_name for row in inventory_rows),
        unique_agency_ids_total=_unique_count(row.agency_id for row in inventory_rows),
        unique_browse_source_urls_total=_unique_count(
            row.browse_source_url for row in inventory_rows
        ),
        unique_rule_series_total=_unique_count(row.ccr_number for row in inventory_rows),
        unique_rule_detail_urls_total=_unique_count(
            row.rule_detail_url for row in inventory_rows
        ),
        asset_format_counts=_value_counts(row.asset_format for row in inventory_rows),
        queue_status_counts=_value_counts(event.status for event in state.values()),
        inventory_status_counts=_value_counts(row.inventory_status for row in inventory_rows),
        field_coverage=field_coverage,
        duplicate_manifest_row_ids=duplicate_ids,
        warnings=warnings,
    )


def _inventory_field_coverage(
    inventory_rows: list[CCRInventoryManifestRow],
) -> dict[str, CCRInventoryFieldCoverage]:
    """Return field-population coverage for the production-critical fields."""

    fields = (
        "department_name",
        "department_id",
        "agency_name",
        "agency_id",
        "browse_source_url",
        "ccr_number",
        "rule_detail_url",
        "rule_id",
        "asset_format",
        "download_url",
        "source_page_url",
        "discovered_at",
    )
    return {
        field_name: _field_coverage(field_name, inventory_rows)
        for field_name in fields
    }


def _field_coverage(
    field_name: str,
    inventory_rows: list[CCRInventoryManifestRow],
) -> CCRInventoryFieldCoverage:
    """Return population counts for one inventory field."""

    total = len(inventory_rows)
    populated = sum(1 for row in inventory_rows if _field_populated(getattr(row, field_name)))
    missing = total - populated
    ratio = populated / total if total else 0.0
    return CCRInventoryFieldCoverage(
        field_name=field_name,
        total=total,
        populated=populated,
        missing=missing,
        populated_ratio=ratio,
    )


def _field_populated(value: object) -> bool:
    """Return whether a field has a non-empty persisted value."""

    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | dict | set | tuple):
        return bool(value)
    return True


def _traversal_validation_status(
    run_status: str,
    config: CCRBulkConfig,
    inventory_rows: list[CCRInventoryManifestRow],
) -> str:
    """Return a concise traversal validation status for the generated manifest."""

    if not inventory_rows:
        return "empty_inventory"
    if run_status != "completed":
        return "incomplete_or_interrupted"
    if config.max_items is not None or config.max_agencies is not None:
        return "capped_run"
    return "uncapped_discovery_completed"


def _field_population_status(
    coverage: dict[str, CCRInventoryFieldCoverage],
) -> str:
    """Return a concise field-population status for critical target fields."""

    critical_fields = ("department_id", "agency_id", "asset_format", "download_url")
    if any(coverage[field_name].missing for field_name in critical_fields):
        return "critical_gaps_detected"
    if coverage["rule_id"].missing:
        return "rule_id_gaps_detected"
    return "critical_fields_populated"


def _inventory_quality_warnings(
    config: CCRBulkConfig,
    run_status: str,
    inventory_rows: list[CCRInventoryManifestRow],
    coverage: dict[str, CCRInventoryFieldCoverage],
    duplicate_ids: list[str],
) -> list[str]:
    """Return operator-facing inventory quality warnings."""

    warnings: list[str] = []
    if config.max_items is not None:
        warnings.append("Run used --max-items; full traversal is not proven.")
    if config.max_agencies is not None:
        warnings.append("Run used --max-agencies; full agency traversal is not proven.")
    if run_status != "completed":
        warnings.append(f"Run status is {run_status}; traversal is not complete.")
    if not inventory_rows:
        warnings.append("Inventory manifest contains no rows.")
    for field_name, field_report in coverage.items():
        if field_report.missing:
            warnings.append(
                f"Field {field_name} missing for {field_report.missing} "
                f"of {field_report.total} inventory rows."
            )
    if duplicate_ids:
        warnings.append(
            f"Duplicate manifest_row_id values detected: {len(duplicate_ids)}."
        )
    return warnings


def _duplicate_manifest_row_ids(
    inventory_rows: list[CCRInventoryManifestRow],
) -> list[str]:
    """Return duplicate manifest row IDs in deterministic order."""

    counts = _value_counts(row.manifest_row_id for row in inventory_rows)
    return sorted(row_id for row_id, count in counts.items() if count > 1)


def _value_counts(values: Iterator[str | None] | Iterator[str]) -> dict[str, int]:
    """Return deterministic counts for non-empty values."""

    counts: dict[str, int] = {}
    for value in values:
        if value is None:
            continue
        key = str(value).strip()
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _unique_count(values: Iterator[str | None]) -> int:
    """Return the count of unique non-empty values."""

    return len(_value_counts(values))


def _process_event(
    event: CCRBulkQueueEvent,
    paths: _BulkPaths,
    session: Any,
    config: CCRBulkConfig,
    counts: _RunCounts,
    next_sequence: int,
    state: dict[str, CCRBulkQueueEvent],
) -> int:
    """Resolve and optionally retrieve one queue item."""

    entry = _entry_from_event(event)
    resolved = entry
    if event.status in {"indexed", "discovered"}:
        try:
            resolved = _resolve_entry(entry, session, config)
        except Exception as exc:
            failed = _queue_event(
                sequence=next_sequence,
                entry=entry,
                status="failed_permanent",
                phase="detail_resolution",
                error=exc,
            )
            next_sequence = _append_queue_event(paths.queue_path, failed, state)
            _append_failure(paths.failure_path, failed)
            counts.failed += 1
            counts.failed_permanent += 1
            _write_checkpoint(paths, "running", failed, counts, None)
            return next_sequence
        resolved_event = _queue_event(
            sequence=next_sequence,
            entry=resolved,
            status="resolved",
            phase="detail_resolution",
            archive_path=_target_path(paths.archive_dir, resolved),
        )
        next_sequence = _append_queue_event(paths.queue_path, resolved_event, state)
        counts.resolved += 1
        _write_checkpoint(paths, "running", resolved_event, counts, None)
        event = resolved_event

    if config.discovery_only:
        return next_sequence
    return _retrieve_entry(resolved, paths, session, config, counts, next_sequence, state)


def _resolve_entry(entry: CCRRuleEntry, session: Any, config: CCRBulkConfig) -> CCRRuleEntry:
    """Resolve a queued CCR index entry into document URLs."""

    if entry.pdf_url is not None or entry.docx_url is not None:
        return entry
    resolved = resolve_rule_info_page(
        entry,
        client=session,
        max_retries=config.max_retries,
        base_delay=config.base_delay,
        timeout_seconds=config.timeout_seconds,
        max_retry_delay_seconds=config.max_retry_delay_seconds,
        retry_jitter_ratio=config.retry_jitter_ratio,
    )
    if resolved.pdf_url is None and resolved.docx_url is None:
        raise CCRDownloadError(f"no downloadable URL for {resolved.ccr_number}")
    return resolved


def _retrieve_entry(
    entry: CCRRuleEntry,
    paths: _BulkPaths,
    session: Any,
    config: CCRBulkConfig,
    counts: _RunCounts,
    next_sequence: int,
    state: dict[str, CCRBulkQueueEvent],
) -> int:
    """Retrieve one resolved CCR document and append queue status."""

    target = _target_path(paths.archive_dir, entry)
    download_state = reconcile_download_state(paths.manifest_path, entry, target)
    if download_state.status == "downloaded":
        event = _queue_event(
            sequence=next_sequence,
            entry=entry,
            status="skipped_existing",
            phase="content_retrieval",
            archive_path=download_state.archive_path,
        )
        next_sequence = _append_queue_event(paths.queue_path, event, state)
        counts.skipped_existing += 1
        _write_checkpoint(paths, "running", event, counts, None)
        return next_sequence

    counts.attempted += 1
    try:
        path = download_rule(
            entry,
            paths.archive_dir,
            client=session,
            max_retries=config.max_retries,
            base_delay=config.base_delay,
            timeout_seconds=config.timeout_seconds,
            max_retry_delay_seconds=config.max_retry_delay_seconds,
            retry_jitter_ratio=config.retry_jitter_ratio,
        )
    except CCRBlockedResponseError as exc:
        event = _queue_event(
            sequence=next_sequence,
            entry=entry,
            status="blocked",
            phase="content_retrieval",
            archive_path=target,
            error=exc,
        )
        next_sequence = _append_queue_event(paths.queue_path, event, state)
        _append_failure(paths.failure_path, event)
        counts.blocked += 1
        counts.failed += 1
        _write_checkpoint(paths, "running", event, counts, None)
    except CCRDownloadError as exc:
        fallback = _fallback_entry(entry)
        if fallback is not None:
            try:
                path = download_rule(
                    fallback,
                    paths.archive_dir,
                    client=session,
                    max_retries=config.max_retries,
                    base_delay=config.base_delay,
                    timeout_seconds=config.timeout_seconds,
                    max_retry_delay_seconds=config.max_retry_delay_seconds,
                    retry_jitter_ratio=config.retry_jitter_ratio,
                )
            except CCRBlockedResponseError as fallback_exc:
                event = _queue_event(
                    sequence=next_sequence,
                    entry=fallback,
                    status="blocked",
                    phase="content_retrieval",
                    archive_path=_target_path(paths.archive_dir, fallback),
                    error=fallback_exc,
                )
                next_sequence = _append_queue_event(paths.queue_path, event, state)
                _append_failure(paths.failure_path, event)
                counts.blocked += 1
                counts.failed += 1
                _write_checkpoint(paths, "running", event, counts, None)
            except CCRDownloadError as fallback_exc:
                event = _queue_event(
                    sequence=next_sequence,
                    entry=fallback,
                    status="failed_permanent",
                    phase="content_retrieval",
                    archive_path=_target_path(paths.archive_dir, fallback),
                    error=fallback_exc,
                )
                next_sequence = _append_queue_event(paths.queue_path, event, state)
                _append_failure(paths.failure_path, event)
                counts.failed += 1
                counts.failed_permanent += 1
                _write_checkpoint(paths, "running", event, counts, None)
            else:
                event = _queue_event(
                    sequence=next_sequence,
                    entry=fallback,
                    status="downloaded",
                    phase="content_retrieval",
                    archive_path=path,
                )
                next_sequence = _append_queue_event(paths.queue_path, event, state)
                counts.downloaded += 1
                _write_checkpoint(paths, "running", event, counts, None)
        else:
            event = _queue_event(
                sequence=next_sequence,
                entry=entry,
                status="failed_permanent",
                phase="content_retrieval",
                archive_path=target,
                error=exc,
            )
            next_sequence = _append_queue_event(paths.queue_path, event, state)
            _append_failure(paths.failure_path, event)
            counts.failed += 1
            counts.failed_permanent += 1
            _write_checkpoint(paths, "running", event, counts, None)
    else:
        event = _queue_event(
            sequence=next_sequence,
            entry=entry,
            status="downloaded",
            phase="content_retrieval",
            archive_path=path,
        )
        next_sequence = _append_queue_event(paths.queue_path, event, state)
        counts.downloaded += 1
        _write_checkpoint(paths, "running", event, counts, None)
    return next_sequence


def _fallback_entry(entry: CCRRuleEntry) -> CCRRuleEntry | None:
    """Return an alternate document entry when the preferred asset fails."""

    if entry.pdf_url is not None and entry.docx_url is not None:
        return CCRRuleEntry(
            ccr_number=entry.ccr_number,
            department=entry.department,
            agency=entry.agency,
            source_page_url=entry.source_page_url,
            browse_source_url=entry.browse_source_url,
            pdf_url=None,
            docx_url=entry.docx_url,
        )
    return None


def _queue_event(
    *,
    sequence: int,
    entry: CCRRuleEntry,
    status: str,
    phase: str,
    archive_path: Path | None = None,
    error: Exception | None = None,
) -> CCRBulkQueueEvent:
    """Build one queue event from a CCR rule entry."""

    return CCRBulkQueueEvent(
        sequence=sequence,
        timestamp=datetime.now(timezone.utc),
        item_id=entry.canonical_id,
        status=status,
        phase=phase,
        ccr_number=entry.ccr_number,
        department=entry.department,
        agency=entry.agency,
        source_page_url=str(_canonical_source_url(str(entry.source_page_url))),
        browse_source_url=_optional_url(entry.browse_source_url),
        pdf_url=_optional_url(entry.pdf_url),
        docx_url=_optional_url(entry.docx_url),
        preferred_url=_preferred_url(entry),
        archive_path=archive_path.as_posix() if archive_path is not None else None,
        error=str(error) if error is not None else None,
    )


def _entry_from_event(event: CCRBulkQueueEvent) -> CCRRuleEntry:
    """Rehydrate a CCR rule entry from the latest queue event."""

    return CCRRuleEntry(
        ccr_number=event.ccr_number,
        department=event.department or "Unknown Department",
        agency=event.agency or "Unknown Agency",
        source_page_url=event.source_page_url,
        browse_source_url=event.browse_source_url,
        pdf_url=event.pdf_url,
        docx_url=event.docx_url,
    )


def _inventory_rows_from_queue(queue_path: Path) -> list[CCRInventoryManifestRow]:
    """Return deterministic inventory rows from the append-only queue."""

    history = _load_queue_history(queue_path)
    rows: list[CCRInventoryManifestRow] = []
    for item_id in history.order:
        event = history.latest_by_id[item_id]
        discovered_at = history.first_timestamp_by_id[item_id]
        resolved_at = history.resolved_timestamp_by_id.get(item_id)
        rows.extend(_inventory_rows_for_event(event, discovered_at, resolved_at))
    return rows


def _load_queue_history(queue_path: Path) -> _QueueHistory:
    """Load latest and first-seen queue state for inventory materialization."""

    latest_by_id: dict[str, CCRBulkQueueEvent] = {}
    first_timestamp_by_id: dict[str, datetime] = {}
    resolved_timestamp_by_id: dict[str, datetime] = {}
    order: list[str] = []
    for event in _iter_queue_events(queue_path):
        if event.item_id not in latest_by_id:
            order.append(event.item_id)
            first_timestamp_by_id[event.item_id] = event.timestamp
        latest_by_id[event.item_id] = event
        if event.status == "resolved":
            resolved_timestamp_by_id[event.item_id] = event.timestamp
    return _QueueHistory(
        latest_by_id=latest_by_id,
        first_timestamp_by_id=first_timestamp_by_id,
        resolved_timestamp_by_id=resolved_timestamp_by_id,
        order=order,
    )


def _inventory_rows_for_event(
    event: CCRBulkQueueEvent,
    discovered_at: datetime,
    resolved_at: datetime | None,
) -> list[CCRInventoryManifestRow]:
    """Build one or more canonical inventory rows from the latest queue event."""

    targets = _asset_targets(event)
    if not targets:
        targets = [_AssetTarget(None, None, None)]
    return [
        _inventory_row(event, target, discovered_at, resolved_at)
        for target in targets
    ]


def _inventory_row(
    event: CCRBulkQueueEvent,
    target: _AssetTarget,
    discovered_at: datetime,
    resolved_at: datetime | None,
) -> CCRInventoryManifestRow:
    """Build a validated inventory manifest row."""

    source_page_url = str(_canonical_source_url(event.source_page_url))
    browse_source_url = _browse_source_url(event)
    rule_detail_url = source_page_url if _is_rule_detail_url(source_page_url) else None
    manifest_row_id = _manifest_row_id(event.item_id, target.asset_format, target.download_url)
    payload: dict[str, Any] = {
        "manifest_row_id": manifest_row_id,
        "manifest_row_checksum": "0" * 64,
        "item_id": event.item_id,
        "department_name": event.department,
        "department_id": _first_query_value("deptID", browse_source_url, source_page_url),
        "agency_name": event.agency,
        "agency_id": _first_query_value("agencyID", browse_source_url, source_page_url),
        "division_name": None,
        "browse_source_url": browse_source_url,
        "ccr_number": event.ccr_number,
        "rule_title": None,
        "rule_detail_url": rule_detail_url,
        "rule_id": _first_query_value("ruleId", rule_detail_url, source_page_url),
        "status_markers": [],
        "asset_scope": CURRENT_ASSET_SCOPE,
        "asset_format": target.asset_format,
        "download_url": target.download_url,
        "effective_date": None,
        "filing_type": None,
        "register_publication_date": None,
        "edocket_tracking_number": None,
        "is_current_version": True if target.download_url else None,
        "is_preferred_asset": target.is_preferred_asset,
        "source_page_url": source_page_url,
        "discovered_at": discovered_at,
        "resolved_at": resolved_at,
        "inventory_status": event.status,
        "queue_status": event.status,
        "archive_path": event.archive_path,
        "error": event.error,
    }
    payload["manifest_row_checksum"] = _stable_row_checksum(payload)
    return CCRInventoryManifestRow.model_validate(payload)


def _asset_targets(event: CCRBulkQueueEvent) -> list[_AssetTarget]:
    """Return unique downloadable asset targets from a queue event."""

    preferred_url = _canonical_optional_url(event.preferred_url)
    candidates = (
        ("pdf", event.pdf_url),
        (_asset_format_from_url(event.docx_url), event.docx_url),
    )
    targets: list[_AssetTarget] = []
    seen_urls: set[str] = set()
    for fallback_format, raw_url in candidates:
        download_url = _canonical_optional_url(raw_url)
        if download_url is None or download_url in seen_urls:
            continue
        seen_urls.add(download_url)
        asset_format = _asset_format_from_url(download_url) or fallback_format
        targets.append(
            _AssetTarget(
                asset_format=asset_format,
                download_url=download_url,
                is_preferred_asset=download_url == preferred_url,
            )
        )
    if not targets and preferred_url is not None:
        targets.append(
            _AssetTarget(
                asset_format=_asset_format_from_url(preferred_url),
                download_url=preferred_url,
                is_preferred_asset=True,
            )
        )
    return targets


def _download_entries_from_inventory(
    inventory_path: Path,
) -> Iterator[tuple[str, CCRRuleEntry]]:
    """Yield downloader-ready entries from the persisted inventory manifest."""

    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in _iter_inventory_rows(inventory_path):
        if row.download_url is None:
            continue
        if row.item_id not in grouped:
            order.append(row.item_id)
            grouped[row.item_id] = {
                "ccr_number": row.ccr_number,
                "department": row.department_name or "Unknown Department",
                "agency": row.agency_name or "Unknown Agency",
                "source_page_url": row.source_page_url,
                "browse_source_url": row.browse_source_url,
                "pdf_url": None,
                "docx_url": None,
            }
        if row.asset_format == "pdf":
            grouped[row.item_id]["pdf_url"] = row.download_url
        elif row.asset_format in {"doc", "docx"}:
            grouped[row.item_id]["docx_url"] = row.download_url
        elif row.is_preferred_asset:
            grouped[row.item_id]["pdf_url"] = row.download_url
    for item_id in order:
        payload = grouped[item_id]
        if payload["pdf_url"] is None and payload["docx_url"] is None:
            continue
        yield item_id, CCRRuleEntry.model_validate(payload)


def _iter_inventory_rows(path: Path) -> Iterator[CCRInventoryManifestRow]:
    """Yield validated rows from the canonical inventory manifest."""

    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield CCRInventoryManifestRow.model_validate_json(line)


def _browse_source_url(event: CCRBulkQueueEvent) -> str | None:
    """Return the agency browse/list source URL when it is known."""

    if event.browse_source_url:
        return str(_canonical_source_url(event.browse_source_url))
    source_page_url = str(_canonical_source_url(event.source_page_url))
    if _is_browse_url(source_page_url):
        return source_page_url
    return None


def _manifest_row_id(
    item_id: str,
    asset_format: str | None,
    download_url: str | None,
) -> str:
    """Return a stable inventory row identifier."""

    target_kind = asset_format or "unresolved"
    if download_url is None:
        return f"{item_id}:{CURRENT_ASSET_SCOPE}:{target_kind}"
    return f"{item_id}:{CURRENT_ASSET_SCOPE}:{target_kind}"


def _stable_row_checksum(payload: dict[str, Any]) -> str:
    """Return a stable checksum for an inventory row payload."""

    checksum_payload = dict(payload)
    checksum_payload["manifest_row_checksum"] = None
    serialized = json.dumps(
        checksum_payload,
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _asset_format_from_url(url: str | None) -> str | None:
    """Return the source asset format indicated by a CCR download URL."""

    if url is None:
        return None
    lowered = url.casefold()
    if ".docx" in lowered or "type=word" in lowered:
        return "docx"
    if ".doc?" in lowered or ".doc&" in lowered or "generateruledoc" in lowered:
        return "doc"
    if ".pdf" in lowered or "pdf" in lowered:
        return "pdf"
    return None


def _canonical_optional_url(value: str | None) -> str | None:
    """Return a canonical URL string or null."""

    if value is None:
        return None
    return str(_canonical_source_url(value))


def _is_rule_detail_url(url: str) -> bool:
    """Return whether a URL points to a CCR DisplayRule detail page."""

    return "displayrule.do" in url.casefold()


def _is_browse_url(url: str) -> bool:
    """Return whether a URL points to an agency CCR browse/list page."""

    return "numericalccrdoclist.do" in url.casefold()


def _first_query_value(key: str, *urls: str | None) -> str | None:
    """Return the first matching query value from a set of URLs."""

    for url in urls:
        if not url:
            continue
        parsed = urlparse(str(_canonical_source_url(url)))
        values = parse_qs(parsed.query)
        for query_key, query_values in values.items():
            if query_key.casefold() == key.casefold() and query_values:
                value = query_values[0].strip()
                if value:
                    return value
    return None


def _limited_order(order: list[str], max_items: int | None) -> list[str]:
    """Return the run-limited item order."""

    if max_items is None:
        return list(order)
    return list(order[:max_items])


def _queue_limit_reached(order: list[str], max_items: int | None) -> bool:
    """Return whether the persisted queue has reached the run item cap."""

    return max_items is not None and len(order) >= max_items


def _bulk_paths(output_root: Path) -> _BulkPaths:
    """Return canonical paths for one CCR bulk workflow root."""

    root = output_root.resolve()
    archive_dir = root / "_RAW_ARCHIVE" / "ccr"
    inventory_dir = root / REGULATIONS_LAYER / INVENTORY_DIR_NAME
    return _BulkPaths(
        output_root=root,
        archive_dir=archive_dir,
        inventory_dir=inventory_dir,
        queue_path=archive_dir / QUEUE_NAME,
        checkpoint_path=archive_dir / CHECKPOINT_NAME,
        summary_path=archive_dir / SUMMARY_NAME,
        failure_path=archive_dir / FAILURES_NAME,
        manifest_path=download_manifest_path(archive_dir),
        inventory_manifest_path=inventory_dir / INVENTORY_MANIFEST_NAME,
        inventory_quality_path=inventory_dir / INVENTORY_QUALITY_NAME,
    )


def _load_queue_state(
    queue_path: Path,
) -> tuple[dict[str, CCRBulkQueueEvent], list[str], int]:
    """Load latest queue state by item ID without loading document content."""

    state: dict[str, CCRBulkQueueEvent] = {}
    order: list[str] = []
    next_sequence = 0
    if not queue_path.exists():
        return state, order, next_sequence
    with queue_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            event = CCRBulkQueueEvent.model_validate_json(line)
            if event.item_id not in state:
                order.append(event.item_id)
            state[event.item_id] = event
            next_sequence = max(next_sequence, event.sequence + 1)
    return state, order, next_sequence


def _build_summary(
    config: CCRBulkConfig,
    paths: _BulkPaths,
    started_at: datetime,
    status: str,
    counts: _RunCounts,
    retry_counter: _RetryCounter,
    state: dict[str, CCRBulkQueueEvent],
    inventory_rows: list[CCRInventoryManifestRow],
    quality_report: CCRInventoryQualityReport | None,
) -> CCRBulkSummary:
    """Build a deterministic run summary."""

    pending = sum(1 for event in state.values() if event.status not in TERMINAL_STATUSES)
    inventory_download_targets = sum(1 for row in inventory_rows if row.download_url)
    return CCRBulkSummary(
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        status=status,
        output_root=paths.output_root.as_posix(),
        archive_dir=paths.archive_dir.as_posix(),
        queue_path=paths.queue_path.as_posix(),
        checkpoint_path=paths.checkpoint_path.as_posix(),
        summary_path=paths.summary_path.as_posix(),
        failure_path=paths.failure_path.as_posix(),
        manifest_path=paths.manifest_path.as_posix(),
        inventory_dir=paths.inventory_dir.as_posix(),
        inventory_manifest_path=paths.inventory_manifest_path.as_posix(),
        inventory_quality_path=paths.inventory_quality_path.as_posix(),
        resume=config.resume,
        discovery_only=config.discovery_only,
        max_items=config.max_items,
        queue_items_total=len(state),
        discovered=counts.indexed,
        indexed=counts.indexed,
        resolved=counts.resolved,
        attempted=counts.attempted,
        downloaded=counts.downloaded,
        skipped_existing=counts.skipped_existing,
        failed=counts.failed,
        failed_permanent=counts.failed_permanent,
        blocked=counts.blocked,
        pending_retry=0,
        retry_count=retry_counter.retry_count,
        pending=pending,
        inventory_rows_total=len(inventory_rows),
        inventory_download_targets=inventory_download_targets,
        traversal_validation_status=(
            quality_report.traversal_validation_status if quality_report else None
        ),
        field_population_status=(
            quality_report.field_population_status if quality_report else None
        ),
    )


def _write_checkpoint(
    paths: _BulkPaths,
    status: str,
    event: CCRBulkQueueEvent | None,
    counts: _RunCounts,
    retry_counter: _RetryCounter | None,
    *,
    summary: CCRBulkSummary | None = None,
) -> None:
    """Write the latest CCR bulk checkpoint atomically."""

    payload: dict[str, Any] = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "queue_path": paths.queue_path.as_posix(),
        "inventory_manifest_path": paths.inventory_manifest_path.as_posix(),
        "inventory_quality_path": paths.inventory_quality_path.as_posix(),
        "summary_path": paths.summary_path.as_posix(),
        "indexed": counts.indexed,
        "resolved": counts.resolved,
        "attempted": counts.attempted,
        "downloaded": counts.downloaded,
        "skipped_existing": counts.skipped_existing,
        "failed": counts.failed,
        "failed_permanent": counts.failed_permanent,
        "blocked": counts.blocked,
        "pending_retry": 0,
        "retry_count": retry_counter.retry_count if retry_counter else None,
    }
    if event is not None:
        payload["last_sequence"] = event.sequence
        payload["last_item_id"] = event.item_id
        payload["last_status"] = event.status
    if summary is not None:
        payload["run_summary"] = summary.model_dump(mode="json")
    _write_json(paths.checkpoint_path, payload)


def _append_queue_event(
    queue_path: Path,
    event: CCRBulkQueueEvent,
    state: dict[str, CCRBulkQueueEvent],
) -> int:
    """Append one queue event and update in-memory latest state."""

    _append_jsonl(queue_path, event.model_dump(mode="json"))
    state[event.item_id] = event
    return event.sequence + 1


def _append_failure(path: Path, event: CCRBulkQueueEvent) -> None:
    """Append one bulk workflow failure event."""

    _append_jsonl(path, event.model_dump(mode="json"))


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    """Append one JSON object to a JSONL artifact atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    existing.append(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    tmp_path = _artifact_tmp_path(path)
    try:
        tmp_path.write_text("\n".join(existing) + "\n", encoding="utf-8", newline="\n")
        _replace_artifact(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON artifact atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _artifact_tmp_path(path)
    try:
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        _replace_artifact(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _reset_artifacts(paths: _BulkPaths) -> None:
    """Start a fresh CCR bulk queue while preserving downloaded source files."""

    for path in (paths.queue_path, paths.failure_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8", newline="\n")
    atomic_write_jsonl(paths.inventory_manifest_path, [], paths.output_root)
    if paths.inventory_quality_path.exists():
        paths.inventory_quality_path.unlink()
    for path in (paths.checkpoint_path, paths.summary_path):
        if path.exists():
            path.unlink()


def _artifact_tmp_path(path: Path) -> Path:
    """Return a unique adjacent temporary path for an artifact write."""

    stamp = time.time_ns()
    return path.with_name(f"{path.name}.{os.getpid()}.{stamp}.tmp")


def _replace_artifact(tmp_path: Path, target: Path) -> None:
    """Replace an artifact with a short bounded retry for Windows file locks."""

    for attempt in range(1, 8):
        try:
            os.replace(tmp_path, target)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.05 * attempt)


def _iter_queue_events(path: Path) -> Iterator[CCRBulkQueueEvent]:
    """Yield queue events from a queue artifact."""

    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield CCRBulkQueueEvent.model_validate_json(line)


def _target_path(archive_dir: Path, entry: CCRRuleEntry) -> Path:
    """Return the expected archive target path for a CCR entry."""

    return ccr_rule_document_path(archive_dir, entry.canonical_id, entry.preferred_extension)


def _optional_url(value: object) -> str | None:
    """Return a normalized optional URL string."""

    if value is None:
        return None
    return str(_canonical_source_url(str(value)))


def _preferred_url(entry: CCRRuleEntry) -> str | None:
    """Return a preferred document URL, if the entry is resolved."""

    try:
        return str(_canonical_source_url(entry.preferred_url))
    except CCRDownloadError:
        return None


def _limit_reached(processed: int, max_items: int | None) -> bool:
    """Return whether the run-level item cap has been reached."""

    return max_items is not None and processed >= max_items


def _validate_config(config: CCRBulkConfig) -> None:
    """Validate CCR bulk workflow options."""

    if config.max_items is not None and config.max_items < 0:
        raise ValueError("--max-items cannot be negative")
    if config.max_agencies is not None and config.max_agencies < 0:
        raise ValueError("--max-agencies cannot be negative")
    for name, value in (
        ("--discovery-delay", config.discovery_delay),
        ("--discovery-delay-jitter", config.discovery_delay_jitter_seconds),
        ("--download-delay", config.download_delay),
        ("--download-delay-jitter", config.download_delay_jitter_seconds),
        ("--http-base-delay", config.base_delay),
        ("--http-retry-jitter-ratio", config.retry_jitter_ratio),
    ):
        if value < 0:
            raise ValueError(f"{name} cannot be negative")
    if config.max_retries < 1:
        raise ValueError("--http-max-retries must be at least 1")
    if config.timeout_seconds <= 0:
        raise ValueError("--http-timeout-seconds must be positive")
    if (
        config.max_retry_delay_seconds is not None
        and config.max_retry_delay_seconds <= 0
    ):
        raise ValueError("--http-max-retry-delay-seconds must be positive")


def _print_summary(summary: CCRBulkSummary) -> None:
    """Print a concise human-readable run summary."""

    print("CCR bulk workflow summary")
    print(f"Status: {summary.status}")
    print(f"Output root: {summary.output_root}")
    print(f"Queue: {summary.queue_path}")
    print(f"Inventory manifest: {summary.inventory_manifest_path}")
    print(f"Inventory quality: {summary.inventory_quality_path}")
    print(f"Summary: {summary.summary_path}")
    print(f"Dataset: {summary.dataset_jsonl_path}")
    print(
        "Indexed: {indexed}  Resolved: {resolved}  Attempted: {attempted}  "
        "Downloaded: {downloaded}  Skipped: {skipped_existing}  "
        "Failed: {failed}  Blocked: {blocked}  Pending: {pending}  "
        "Inventory targets: {inventory_download_targets}".format(
            **summary.model_dump(mode="json")
        )
    )
    print(f"Traversal QA: {summary.traversal_validation_status}")
    print(f"Field QA: {summary.field_population_status}")
    if summary.tagged_jsonl_path:
        print(f"Tagged dataset: {summary.tagged_jsonl_path}")


if __name__ == "__main__":
    raise SystemExit(main())
