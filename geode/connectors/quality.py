"""Lightweight quality reports for bulk source downloads."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from geode.connectors.archive_paths import (
    DOWNLOAD_MANIFEST_NAME,
    FAILURE_MANIFEST_NAME,
)
from geode.utils.file_io import atomic_write_json

QUALITY_REPORT_PATH = Path("_CONTROL_PLANE") / "BULK_DOWNLOAD_QUALITY_REPORT.json"
NEAR_EMPTY_BYTES = 16


class QualityIssue(BaseModel):
    """One bulk-download quality issue."""

    model_config = ConfigDict(extra="forbid")

    severity: Literal["error", "warning"]
    connector: str
    code: str
    path: str
    message: str


class ConnectorQualityReport(BaseModel):
    """Quality report for one connector output directory."""

    model_config = ConfigDict(extra="forbid")

    connector: str
    raw_dir: str
    manifest_path: str
    failure_manifest_path: str | None = None
    attempted: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    manifest_rows: int = Field(ge=0)
    failure_rows: int = Field(ge=0)
    issues: list[QualityIssue] = Field(default_factory=list)

    @property
    def error_count(self) -> int:
        """Return the number of error issues."""

        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        """Return the number of warning issues."""

        return sum(1 for issue in self.issues if issue.severity == "warning")


class BulkDownloadQualityReport(BaseModel):
    """Machine-readable post-run quality report."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    root: str
    valid: bool
    summary: dict[str, int]
    connectors: list[ConnectorQualityReport] = Field(default_factory=list)
    issues: list[QualityIssue] = Field(default_factory=list)


def build_bulk_download_quality_report(
    root: Path,
    results: list[Any],
) -> BulkDownloadQualityReport:
    """Build a lightweight quality report from connector summaries and manifests."""

    connector_reports = [_connector_report(root, _result_dict(result)) for result in results]
    issues = [issue for report in connector_reports for issue in report.issues]
    summary = {
        "connectors": len(connector_reports),
        "attempted": sum(report.attempted for report in connector_reports),
        "succeeded": sum(report.succeeded for report in connector_reports),
        "failed": sum(report.failed for report in connector_reports),
        "skipped": sum(report.skipped for report in connector_reports),
        "errors": sum(report.error_count for report in connector_reports),
        "warnings": sum(report.warning_count for report in connector_reports),
    }
    return BulkDownloadQualityReport(
        generated_at=datetime.now(timezone.utc),
        root=root.as_posix(),
        valid=summary["errors"] == 0,
        summary=summary,
        connectors=connector_reports,
        issues=issues,
    )


def write_bulk_download_quality_report(
    root: Path,
    report: BulkDownloadQualityReport,
    report_path: Path | None = None,
) -> Path:
    """Write the bulk-download quality report under the control plane."""

    target = root / (report_path or QUALITY_REPORT_PATH)
    atomic_write_json(target, report, root)
    return target


def _connector_report(root: Path, result: dict[str, Any]) -> ConnectorQualityReport:
    """Build a quality report for one connector result."""

    connector = str(result.get("connector", "unknown"))
    raw_dir = _resolve_path(root, str(result.get("raw_dir", "")))
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    metrics = _connector_metrics(summary)
    issues: list[QualityIssue] = []

    manifest_path = _resolve_path(
        root,
        str(summary.get("manifest_path") or raw_dir / DOWNLOAD_MANIFEST_NAME),
    )
    failure_manifest_path = raw_dir / FAILURE_MANIFEST_NAME
    manifest_rows = _read_jsonl_rows(connector, manifest_path, issues)
    separate_failure_rows = _read_jsonl_rows(connector, failure_manifest_path, issues)
    success_rows = [row for row in manifest_rows if _is_success_row(row)]
    failure_rows = [row for row in manifest_rows if _is_failure_row(row)]
    failure_rows.extend(separate_failure_rows)

    _check_summary_counts(connector, summary, metrics, issues)
    _check_summary_paths(connector, root, summary, issues)
    _check_manifest_presence(connector, manifest_path, metrics, issues)
    _check_duplicate_values(connector, success_rows, "archive_path", issues)
    _check_duplicate_values(connector, success_rows, "document_id", issues)
    _check_downloaded_files(connector, root, success_rows, issues)
    _check_failure_rows(connector, failure_rows, metrics, issues)
    _check_parse_failures(connector, summary, issues)

    return ConnectorQualityReport(
        connector=connector,
        raw_dir=raw_dir.as_posix(),
        manifest_path=manifest_path.as_posix(),
        failure_manifest_path=failure_manifest_path.as_posix()
        if failure_manifest_path.exists()
        else None,
        attempted=metrics["attempted"],
        succeeded=metrics["succeeded"],
        failed=metrics["failed"],
        skipped=metrics["skipped"],
        manifest_rows=len(manifest_rows),
        failure_rows=len(failure_rows),
        issues=issues,
    )


def _result_dict(result: Any) -> dict[str, Any]:
    """Return a connector result as a plain dictionary."""

    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if isinstance(result, dict):
        return dict(result)
    return {}


def _connector_metrics(summary: dict[str, Any]) -> dict[str, int]:
    """Extract operational counts from a connector summary."""

    skipped = _int_value(summary.get("skipped"))
    failed = _int_value(summary.get("failed"))
    succeeded = _int_value(summary.get("downloaded"))
    if succeeded == 0 and "bills" in summary:
        succeeded = max(_int_value(summary.get("bills")) - skipped, 0)
    attempted = _int_value(summary.get("attempted"))
    if "attempted" not in summary:
        attempted = max(_int_value(summary.get("discovered")), succeeded + skipped + failed)
    return {
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
    }


def _int_value(value: object) -> int:
    """Return a non-negative integer value."""

    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return max(int(value), 0)
    return 0


def _resolve_path(root: Path, value: str) -> Path:
    """Resolve relative artifact paths under the project root."""

    path = Path(value)
    return path if path.is_absolute() else root / path


def _read_jsonl_rows(
    connector: str,
    path: Path,
    issues: list[QualityIssue],
) -> list[dict[str, Any]]:
    """Read JSONL rows and surface malformed files as quality issues."""

    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                raise ValueError(f"blank JSONL line at {path}:{line_number}")
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL row must be an object at {path}:{line_number}")
            rows.append(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        issues.append(
            _issue(
                "error",
                connector,
                "malformed_manifest",
                path,
                f"manifest could not be read as JSONL: {exc}",
            )
        )
    return rows


def _is_success_row(row: dict[str, Any]) -> bool:
    """Return whether a manifest row represents a successful archived artifact."""

    status = str(row.get("status", "downloaded")).casefold()
    return status != "failed" and not row.get("error")


def _is_failure_row(row: dict[str, Any]) -> bool:
    """Return whether a manifest row represents a failed artifact."""

    status = str(row.get("status", "")).casefold()
    return status == "failed" or bool(row.get("error"))


def _check_summary_counts(
    connector: str,
    summary: dict[str, Any],
    metrics: dict[str, int],
    issues: list[QualityIssue],
) -> None:
    """Check discovered-vs-accounted counts when the connector reports discovery."""

    accounted = metrics["succeeded"] + metrics["skipped"] + metrics["failed"]
    if metrics["attempted"] != accounted:
        issues.append(
            _issue(
                "error",
                connector,
                "count_mismatch",
                "summary",
                f"attempted={metrics['attempted']} but succeeded+skipped+failed={accounted}",
            )
        )
        return

    if "discovered" not in summary:
        return
    discovered = _int_value(summary.get("discovered"))
    if discovered < metrics["attempted"]:
        issues.append(
            _issue(
                "error",
                connector,
                "count_mismatch",
                "summary",
                f"discovered={discovered} but attempted={metrics['attempted']}",
            )
        )
    elif discovered > metrics["attempted"]:
        issues.append(
            _issue(
                "warning",
                connector,
                "partial_run",
                "summary",
                f"discovered={discovered} but this run attempted={metrics['attempted']}",
            )
        )


def _check_summary_paths(
    connector: str,
    root: Path,
    summary: dict[str, Any],
    issues: list[QualityIssue],
) -> None:
    """Check duplicate output paths listed in the run summary."""

    paths = summary.get("paths")
    if not isinstance(paths, list):
        return
    normalized = [str(_resolve_path(root, str(path)).as_posix()) for path in paths if path]
    for duplicate in _duplicates(normalized):
        issues.append(
            _issue(
                "error",
                connector,
                "duplicate_summary_path",
                duplicate,
                f"summary contains duplicate output path: {duplicate}",
            )
        )


def _check_manifest_presence(
    connector: str,
    manifest_path: Path,
    metrics: dict[str, int],
    issues: list[QualityIssue],
) -> None:
    """Check that successful runs have a durable manifest."""

    if metrics["succeeded"] + metrics["skipped"] > 0 and not manifest_path.exists():
        issues.append(
            _issue(
                "error",
                connector,
                "missing_manifest",
                manifest_path,
                "successful or skipped outputs were reported but no download manifest exists",
            )
        )


def _check_duplicate_values(
    connector: str,
    rows: list[dict[str, Any]],
    key: str,
    issues: list[QualityIssue],
) -> None:
    """Check duplicate successful manifest values for one key."""

    values = [str(row[key]) for row in rows if row.get(key)]
    code = f"duplicate_{key}"
    for duplicate in _duplicates(values):
        issues.append(
            _issue(
                "error",
                connector,
                code,
                duplicate,
                f"successful manifest rows contain duplicate {key}: {duplicate}",
            )
        )


def _check_downloaded_files(
    connector: str,
    root: Path,
    rows: list[dict[str, Any]],
    issues: list[QualityIssue],
) -> None:
    """Check that successful manifest rows point to usable artifacts."""

    for row in rows:
        archive_path = row.get("archive_path")
        if not archive_path:
            issues.append(
                _issue(
                    "error",
                    connector,
                    "missing_archive_path",
                    "manifest",
                    "successful manifest row has no archive_path",
                )
            )
            continue
        path = _resolve_path(root, str(archive_path))
        if not path.exists():
            issues.append(
                _issue(
                    "error",
                    connector,
                    "missing_output",
                    path,
                    "successful manifest row points to a missing output file",
                )
            )
            continue
        size = path.stat().st_size
        declared_size = _int_value(row.get("size_bytes"))
        if declared_size and declared_size != size:
            issues.append(
                _issue(
                    "error",
                    connector,
                    "size_mismatch",
                    path,
                    f"manifest size_bytes={declared_size} but file size={size}",
                )
            )
        if size == 0:
            issues.append(_issue("error", connector, "empty_output", path, "output file is empty"))
        elif size < NEAR_EMPTY_BYTES:
            issues.append(
                _issue(
                    "warning",
                    connector,
                    "near_empty_output",
                    path,
                    f"output file is only {size} bytes",
                )
            )
        _check_json_artifact(connector, path, issues)


def _check_json_artifact(
    connector: str,
    path: Path,
    issues: list[QualityIssue],
) -> None:
    """Check JSON artifacts for parseability."""

    if path.suffix.casefold() != ".json":
        return
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        issues.append(
            _issue(
                "error",
                connector,
                "malformed_json_output",
                path,
                f"downloaded JSON artifact could not be parsed: {exc}",
            )
        )


def _check_failure_rows(
    connector: str,
    rows: list[dict[str, Any]],
    metrics: dict[str, int],
    issues: list[QualityIssue],
) -> None:
    """Surface failed item rows and missing failure detail."""

    if metrics["failed"] > 0 and not rows:
        issues.append(
            _issue(
                "warning",
                connector,
                "missing_failure_details",
                "failure_manifest",
                "failed items were reported but no failure manifest rows were found",
            )
        )
    for row in rows:
        message = str(row.get("error") or "download failed")
        issues.append(
            _issue(
                "warning",
                connector,
                "failed_download",
                str(row.get("archive_path") or row.get("source_url") or "failure_manifest"),
                message,
            )
        )


def _check_parse_failures(
    connector: str,
    summary: dict[str, Any],
    issues: list[QualityIssue],
) -> None:
    """Surface parser failures if a connector summary includes parse counts."""

    for key in ("parse_failed", "parser_failed", "parsed_failed"):
        failed = _int_value(summary.get(key))
        if failed:
            issues.append(
                _issue(
                    "error",
                    connector,
                    "parse_failed",
                    "summary",
                    f"{key}={failed}",
                )
            )
    parse_errors = summary.get("parse_errors")
    if isinstance(parse_errors, list) and parse_errors:
        issues.append(
            _issue(
                "error",
                connector,
                "parse_errors",
                "summary",
                f"parse_errors reported: {len(parse_errors)}",
            )
        )


def _duplicates(values: list[str]) -> list[str]:
    """Return sorted duplicate values."""

    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _issue(
    severity: Literal["error", "warning"],
    connector: str,
    code: str,
    path: str | Path,
    message: str,
) -> QualityIssue:
    """Create one quality issue."""

    return QualityIssue(
        severity=severity,
        connector=connector,
        code=code,
        path=path.as_posix() if isinstance(path, Path) else path,
        message=message,
    )
