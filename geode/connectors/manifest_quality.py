"""Safe manifest quality utilities for source connector outputs."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from geode.connectors.archive_paths import download_manifest_path
from geode.utils.file_io import atomic_write_json

DEDUPLICATION_STRATEGY = "latest_row_wins"


@dataclass(frozen=True)
class _ManifestRow:
    """One parsed JSONL manifest row with its source line number."""

    row_number: int
    payload: dict[str, Any]


class ManifestDuplicateGroup(BaseModel):
    """Duplicate manifest rows that point to one archive path."""

    model_config = ConfigDict(extra="forbid")

    archive_path: str
    row_numbers: list[int] = Field(default_factory=list)
    kept_row_number: int
    count: int = Field(ge=2)
    document_ids: list[str] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=list)


class ManifestQualityReport(BaseModel):
    """Operational manifest duplicate summary."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    manifest_path: str
    total_rows: int = Field(ge=0)
    rows_with_archive_path: int = Field(ge=0)
    unique_archive_paths: int = Field(ge=0)
    duplicate_archive_paths: int = Field(ge=0)
    duplicate_rows: int = Field(ge=0)
    duplicate_excess_rows: int = Field(ge=0)
    malformed_rows: int = Field(ge=0)
    duplicates: list[ManifestDuplicateGroup] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @property
    def has_duplicates(self) -> bool:
        """Return whether duplicate archive paths were found."""

        return self.duplicate_archive_paths > 0


class DeduplicatedManifestReport(BaseModel):
    """Separate report artifact with a non-canonical deduplicated row set."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    source_manifest_path: str
    strategy: str
    original_rows: int = Field(ge=0)
    deduplicated_row_count: int = Field(ge=0)
    duplicate_archive_paths: int = Field(ge=0)
    duplicate_excess_rows: int = Field(ge=0)
    duplicates: list[ManifestDuplicateGroup] = Field(default_factory=list)
    deduplicated_rows: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def build_ccr_manifest_quality_report(ccr_archive_dir: Path) -> ManifestQualityReport:
    """Build a manifest quality report for a CCR raw archive directory.

    Args:
        ccr_archive_dir: Directory containing the CCR ``download_manifest.jsonl``.

    Returns:
        Manifest duplicate summary for the CCR manifest.
    """

    return build_manifest_quality_report(download_manifest_path(ccr_archive_dir))


def build_manifest_quality_report(manifest_path: Path) -> ManifestQualityReport:
    """Inspect a JSONL manifest for duplicate archive paths without modifying it.

    Args:
        manifest_path: Connector download manifest to inspect.

    Returns:
        Structured duplicate-path report suitable for logs or terminal summaries.
    """

    rows, errors = _read_manifest_rows(manifest_path)
    rows_by_path: dict[str, list[_ManifestRow]] = defaultdict(list)
    for row in rows:
        archive_path = _normalized_archive_path(row.payload.get("archive_path"))
        if archive_path:
            rows_by_path[archive_path].append(row)

    duplicates = [
        _duplicate_group(archive_path, grouped_rows)
        for archive_path, grouped_rows in sorted(rows_by_path.items())
        if len(grouped_rows) > 1
    ]
    duplicate_rows = sum(group.count for group in duplicates)
    return ManifestQualityReport(
        generated_at=datetime.now(timezone.utc),
        manifest_path=manifest_path.as_posix(),
        total_rows=len(rows),
        rows_with_archive_path=sum(len(grouped_rows) for grouped_rows in rows_by_path.values()),
        unique_archive_paths=len(rows_by_path),
        duplicate_archive_paths=len(duplicates),
        duplicate_rows=duplicate_rows,
        duplicate_excess_rows=sum(group.count - 1 for group in duplicates),
        malformed_rows=len(errors),
        duplicates=duplicates,
        errors=errors,
    )


def render_manifest_quality_summary(
    report: ManifestQualityReport,
    max_duplicate_paths: int = 20,
) -> str:
    """Render a concise terminal-friendly manifest quality summary.

    Args:
        report: Structured manifest report to render.
        max_duplicate_paths: Maximum duplicate groups to list before truncating.

    Returns:
        Human-readable summary text for operator review.
    """

    lines = [
        "Manifest quality summary",
        f"Manifest: {report.manifest_path}",
        (
            "Rows: {total}  Unique archive paths: {unique}  "
            "Duplicate paths: {duplicates}  Extra duplicate rows: {extra}"
        ).format(
            total=report.total_rows,
            unique=report.unique_archive_paths,
            duplicates=report.duplicate_archive_paths,
            extra=report.duplicate_excess_rows,
        ),
    ]
    if report.malformed_rows:
        lines.append(f"Malformed rows: {report.malformed_rows}")
    if not report.duplicates:
        lines.append("Duplicate archive paths: none")
        return "\n".join(lines)

    lines.append("Duplicate archive paths:")
    for group in report.duplicates[:max_duplicate_paths]:
        row_text = ", ".join(str(row_number) for row_number in group.row_numbers)
        lines.append(
            f"- {group.archive_path}: rows {row_text}; keep row {group.kept_row_number}"
        )
    remaining = len(report.duplicates) - max_duplicate_paths
    if remaining > 0:
        lines.append(f"... {remaining} more duplicate archive paths")
    return "\n".join(lines)


def build_deduplicated_manifest_report(
    report: ManifestQualityReport,
) -> DeduplicatedManifestReport:
    """Build a non-canonical deduplicated manifest report artifact.

    The canonical manifest is append-only operational evidence. This report uses
    latest-row-wins to show what a deduplicated candidate row set would contain,
    but it does not rewrite the source manifest.

    Args:
        report: Manifest duplicate report created from the target manifest.

    Returns:
        Separate JSON-serializable report with deduplicated rows.
    """

    manifest_path = Path(report.manifest_path)
    rows, read_errors = _read_manifest_rows(manifest_path)
    deduplicated_rows = _deduplicated_rows(rows)
    return DeduplicatedManifestReport(
        generated_at=datetime.now(timezone.utc),
        source_manifest_path=report.manifest_path,
        strategy=DEDUPLICATION_STRATEGY,
        original_rows=report.total_rows,
        deduplicated_row_count=len(deduplicated_rows),
        duplicate_archive_paths=report.duplicate_archive_paths,
        duplicate_excess_rows=report.duplicate_excess_rows,
        duplicates=report.duplicates,
        deduplicated_rows=deduplicated_rows,
        errors=[*report.errors, *read_errors],
    )


def write_deduplicated_manifest_report(
    report: ManifestQualityReport,
    output_path: Path,
    root: Path,
) -> Path:
    """Write a separate deduplicated manifest report without touching the manifest.

    Args:
        report: Manifest duplicate report created from the source manifest.
        output_path: JSON artifact path to write. Must not be the source manifest.
        root: Project root used for safe atomic writes.

    Returns:
        The path written.

    Raises:
        ValueError: If ``output_path`` is the source manifest path.
    """

    manifest_path = Path(report.manifest_path)
    if output_path.resolve() == manifest_path.resolve():
        raise ValueError("deduplicated report output must not overwrite the source manifest")
    artifact = build_deduplicated_manifest_report(report)
    atomic_write_json(output_path, artifact, root)
    return output_path


def _read_manifest_rows(manifest_path: Path) -> tuple[list[_ManifestRow], list[str]]:
    """Read JSONL manifest rows while collecting malformed-line errors."""

    if not manifest_path.exists():
        return [], [f"manifest does not exist: {manifest_path.as_posix()}"]

    rows: list[_ManifestRow] = []
    errors: list[str] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for row_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                errors.append(f"blank JSONL line at {manifest_path}:{row_number}")
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append(f"malformed JSON at {manifest_path}:{row_number}: {exc}")
                continue
            if not isinstance(payload, dict):
                errors.append(f"JSONL row must be an object at {manifest_path}:{row_number}")
                continue
            rows.append(_ManifestRow(row_number=row_number, payload=payload))
    return rows, errors


def _duplicate_group(
    archive_path: str,
    rows: list[_ManifestRow],
) -> ManifestDuplicateGroup:
    """Create one duplicate group from rows sharing an archive path."""

    row_numbers = [row.row_number for row in rows]
    return ManifestDuplicateGroup(
        archive_path=archive_path,
        row_numbers=row_numbers,
        kept_row_number=max(row_numbers),
        count=len(rows),
        document_ids=_distinct_strings(row.payload.get("document_id") for row in rows),
        statuses=_distinct_strings(row.payload.get("status") for row in rows),
    )


def _deduplicated_rows(rows: list[_ManifestRow]) -> list[dict[str, Any]]:
    """Return rows with duplicate archive paths collapsed by latest row."""

    keep_row_numbers: set[int] = set()
    latest_by_archive_path: dict[str, int] = {}
    for row in rows:
        archive_path = _normalized_archive_path(row.payload.get("archive_path"))
        if not archive_path:
            keep_row_numbers.add(row.row_number)
            continue
        latest_by_archive_path[archive_path] = row.row_number
    keep_row_numbers.update(latest_by_archive_path.values())
    return [row.payload for row in rows if row.row_number in keep_row_numbers]


def _normalized_archive_path(value: object) -> str:
    """Return a stable archive path key for duplicate detection."""

    if value is None:
        return ""
    return str(value).strip().replace("\\", "/")


def _distinct_strings(values: Iterable[object]) -> list[str]:
    """Return distinct non-empty strings in first-seen order."""

    distinct: list[str] = []
    for value in values:
        if value is None:
            continue
        item = str(value)
        if item and item not in distinct:
            distinct.append(item)
    return distinct
