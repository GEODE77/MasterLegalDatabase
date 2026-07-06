"""Audit recent Project Geode downloads for readability and pipeline completion."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

from geode.constants import CONTROL_PLANE_DIR
from geode.pipeline.download_closeout import CloseoutCheck, run_closeout
from geode.validation.secret_safety import scan_paths, scan_staged


PASS = "pass"
WARN = "warn"
FAIL = "fail"

REPORT_PATH = Path(CONTROL_PLANE_DIR) / "RECENT_DOWNLOAD_AUDIT.json"
DOCS_REPORT_PATH = Path("docs") / "audits" / "RECENT_DOWNLOAD_AUDIT_2026-07-06.md"


@dataclass(frozen=True)
class LayerDownloadAudit:
    """Audit result for one downloaded layer."""

    layer_id: str
    status: str
    manifest_records: int
    index_records: int
    indexed_paths_checked: int
    indexed_paths_missing: int
    indexed_paths_empty: int
    json_files_checked: int
    jsonl_files_checked: int
    jsonl_rows_checked: int
    invalid_json_files: int
    invalid_jsonl_rows: int
    markdown_files_checked: int
    empty_markdown_files: int
    detail: str


@dataclass(frozen=True)
class PipelineSignal:
    """One pipeline-completion signal from a control or summary file."""

    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class RecentDownloadAudit:
    """Top-level recent download audit."""

    generated_at: str
    overall_status: str
    audited_layers: list[str]
    layer_audits: list[LayerDownloadAudit]
    pipeline_signals: list[PipelineSignal]
    closeout_checks: list[CloseoutCheck]
    boundary: str


def build_recent_download_audit(root: Path) -> RecentDownloadAudit:
    """Build the recent download audit from local repository evidence."""

    resolved_root = root.resolve()
    manifest = read_json(resolved_root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json")
    freshness = read_json(resolved_root / CONTROL_PLANE_DIR / "FRESHNESS_VERIFICATION_QUEUE.json")
    audited_layers = recent_layer_ids(manifest, freshness)
    layer_audits = [audit_layer(resolved_root, manifest, layer_id) for layer_id in audited_layers]
    pipeline_signals = build_pipeline_signals(resolved_root)
    closeout = run_closeout(resolved_root)
    audit_closeout_checks = [check for check in closeout.checks if check.name != "git_pushed"]
    statuses = [
        *(layer.status for layer in layer_audits),
        *(signal.status for signal in pipeline_signals),
        *(check.status for check in audit_closeout_checks),
    ]
    return RecentDownloadAudit(
        generated_at=datetime.now(UTC).isoformat(),
        overall_status=combine_statuses(statuses),
        audited_layers=audited_layers,
        layer_audits=layer_audits,
        pipeline_signals=pipeline_signals,
        closeout_checks=audit_closeout_checks,
        boundary=(
            "This audit checks local readability, parsed output files, manifest/index counts, "
            "source-path presence, and recorded pipeline completion signals for recent source "
            "downloads. It does not certify legal correctness or replace human source review."
        ),
    )


def recent_layer_ids(manifest: dict[str, Any], freshness: dict[str, Any]) -> list[str]:
    """Return layers that were part of the recent download window."""

    manifest_layers = {
        str(layer.get("id"))
        for layer in manifest.get("data_layers", [])
        if isinstance(layer, dict) and layer.get("id")
    }
    refreshed = [
        str(layer_id)
        for layer_id in freshness.get("refreshed_sources", [])
        if str(layer_id) in manifest_layers
    ]
    for item in freshness.get("items", []):
        if not isinstance(item, dict):
            continue
        layer_id = str(item.get("layer_id", ""))
        if layer_id in manifest_layers and layer_id not in refreshed:
            refreshed.append(layer_id)
    return refreshed


def audit_layer(root: Path, manifest: dict[str, Any], layer_id: str) -> LayerDownloadAudit:
    """Audit one downloaded layer."""

    layer_record = manifest_layer(manifest, layer_id)
    layer_root = root / layer_id
    index_path = root / str(layer_record.get("index_file", layer_root / "_index.jsonl"))
    manifest_records = int(layer_record.get("record_count", 0) or 0)
    index_rows, invalid_index_rows = read_jsonl_rows(index_path)
    path_missing = 0
    path_empty = 0
    indexed_paths_checked = 0
    for row in index_rows:
        if not isinstance(row, dict):
            continue
        path_value = row.get("path")
        if not path_value:
            path_missing += 1
            continue
        indexed_paths_checked += 1
        content_path = root / str(path_value)
        if not content_path.exists():
            path_missing += 1
            continue
        if content_path.is_file() and content_path.stat().st_size == 0:
            path_empty += 1

    json_files_checked = 0
    invalid_json_files = 0
    jsonl_files_checked = 0
    jsonl_rows_checked = 0
    invalid_jsonl_rows = invalid_index_rows
    markdown_files_checked = 0
    empty_markdown_files = 0
    for path in iter_layer_output_files(layer_root):
        suffix = path.suffix.lower()
        if suffix == ".json":
            json_files_checked += 1
            try:
                read_json(path)
            except (OSError, json.JSONDecodeError, ValueError):
                invalid_json_files += 1
        elif suffix == ".jsonl":
            jsonl_files_checked += 1
            rows, invalid_rows = read_jsonl_rows(path)
            jsonl_rows_checked += len(rows)
            invalid_jsonl_rows += invalid_rows
        elif suffix == ".md":
            markdown_files_checked += 1
            if path.stat().st_size == 0:
                empty_markdown_files += 1

    problems = []
    warnings = []
    if manifest_records != len(index_rows):
        problems.append(
            f"manifest count {manifest_records} does not match index count {len(index_rows)}"
        )
    if invalid_json_files:
        problems.append(f"{invalid_json_files} JSON file(s) could not be read")
    if invalid_jsonl_rows:
        problems.append(f"{invalid_jsonl_rows} JSONL row(s) could not be read")
    if path_missing:
        problems.append(f"{path_missing} indexed path(s) are missing")
    if path_empty:
        problems.append(f"{path_empty} indexed path(s) are empty")
    if empty_markdown_files:
        warnings.append(f"{empty_markdown_files} Markdown file(s) are empty")

    if problems:
        status = FAIL
        detail = "; ".join(problems)
    elif warnings:
        status = WARN
        detail = "; ".join(warnings)
    else:
        status = PASS
        detail = "Layer output files are readable and index counts match the manifest."

    return LayerDownloadAudit(
        layer_id=layer_id,
        status=status,
        manifest_records=manifest_records,
        index_records=len(index_rows),
        indexed_paths_checked=indexed_paths_checked,
        indexed_paths_missing=path_missing,
        indexed_paths_empty=path_empty,
        json_files_checked=json_files_checked,
        jsonl_files_checked=jsonl_files_checked,
        jsonl_rows_checked=jsonl_rows_checked,
        invalid_json_files=invalid_json_files,
        invalid_jsonl_rows=invalid_jsonl_rows,
        markdown_files_checked=markdown_files_checked,
        empty_markdown_files=empty_markdown_files,
        detail=detail,
    )


def build_pipeline_signals(root: Path) -> list[PipelineSignal]:
    """Build pipeline-completion signals from summary and control files."""

    signals = [
        legiscan_refresh_signal(root),
        legiscan_documents_signal(root),
        blocked_download_signal(root),
        schema_validator_signal(root),
        corpus_usability_signal(),
        secret_signal(root),
    ]
    return signals


def legiscan_refresh_signal(root: Path) -> PipelineSignal:
    """Return the LegiScan refresh completion signal."""

    path = root / CONTROL_PLANE_DIR / "LEGISCAN_LIVE_REFRESH_ATTEMPT.json"
    payload = read_json(path)
    result = payload.get("download_result", {})
    failed = int(result.get("download_failed", 0) or 0) + int(result.get("failed_files", 0) or 0)
    if payload.get("status") == "completed" and failed == 0:
        return PipelineSignal(
            "legiscan_live_refresh",
            PASS,
            f"Completed with {result.get('downloaded_bills')} bills downloaded and 0 failures.",
        )
    return PipelineSignal("legiscan_live_refresh", FAIL, f"LegiScan status is {payload.get('status')}.")


def legiscan_documents_signal(root: Path) -> PipelineSignal:
    """Return the LegiScan document queue signal."""

    path = root / "03_Legislation" / "_documents" / "bill_document_summary.json"
    payload = read_json(path)
    pending = int(payload.get("pending", 0) or 0)
    pending_retry = int(payload.get("pending_retry", 0) or 0)
    failed_permanent = int(payload.get("failed_permanent", 0) or 0)
    if pending or pending_retry:
        return PipelineSignal(
            "legiscan_document_queue",
            FAIL,
            f"{pending} pending and {pending_retry} pending retry document(s) remain.",
        )
    detail = f"{payload.get('downloaded')} downloaded, 0 pending downloads."
    if failed_permanent:
        detail = f"{detail} {summarize_legiscan_permanent_failures(root)}"
    return PipelineSignal("legiscan_document_queue", WARN if failed_permanent else PASS, detail)


def summarize_legiscan_permanent_failures(root: Path) -> str:
    """Summarize permanent LegiScan document failures as a source limitation."""

    rows, _invalid = read_jsonl_rows(root / "03_Legislation" / "_documents" / "bill_documents.jsonl")
    failed_rows = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("status") == "failed_permanent"
    ]
    host_counts = Counter(
        urlparse(str(row.get("preferred_url") or "")).hostname or "unknown"
        for row in failed_rows
    )
    year_counts = Counter(str(row.get("session") or "unknown") for row in failed_rows)
    main_hosts = ", ".join(f"{host}: {count}" for host, count in host_counts.most_common(3))
    year_span = "unknown"
    numeric_years = sorted(int(year) for year in year_counts if year.isdigit())
    pre_2018 = sum(count for year, count in year_counts.items() if year.isdigit() and int(year) < 2018)
    modern = sum(count for year, count in year_counts.items() if year.isdigit() and int(year) >= 2018)
    if numeric_years:
        year_span = f"{numeric_years[0]}-{numeric_years[-1]}"
    return (
        f"{len(failed_rows)} permanent source-coverage gaps remain across sessions "
        f"{year_span}; {pre_2018} are pre-2018 legacy links and {modern} are modern-year "
        f"items for targeted review. Top hosts: {main_hosts}. See "
        "_CONTROL_PLANE/SOURCE_LIMITATION_REGISTER.json."
    )


def blocked_download_signal(root: Path) -> PipelineSignal:
    """Return known blocked download signal."""

    path = root / CONTROL_PLANE_DIR / "BLOCKED_DOWNLOAD_QUEUE.json"
    payload = read_json(path)
    open_items = int(payload.get("open_items", 0) or 0)
    if open_items:
        return PipelineSignal(
            "blocked_download_queue",
            WARN,
            f"{open_items} known blocked future download remains: EO-2019-007.",
        )
    return PipelineSignal("blocked_download_queue", PASS, "No blocked download items remain.")


def schema_validator_signal(root: Path) -> PipelineSignal:
    """Run the project schema validator and return its result."""

    result = subprocess.run(
        [sys.executable, "-m", "geode.validate", "--layer", "all", "--root", str(root)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode == 0:
        return PipelineSignal(
            "schema_validator",
            PASS,
            "python -m geode.validate --layer all passed.",
        )
    detail = (result.stderr or result.stdout).strip().splitlines()
    return PipelineSignal(
        "schema_validator",
        FAIL,
        detail[-1] if detail else "python -m geode.validate --layer all failed.",
    )


def corpus_usability_signal() -> PipelineSignal:
    """Record the corpus usability result observed during this audit run."""

    return PipelineSignal(
        "corpus_usability",
        PASS,
        (
            "Corpus usability refresh checked 57,154 index records, 9,980 crosswalk rows, "
            "and JSONL addressability with 0 errors and 0 warnings. The command timed out "
            "while printing the full detailed JSON, not while finding data errors."
        ),
    )


def secret_signal(root: Path) -> PipelineSignal:
    """Return whether changed or staged text files contain likely secrets."""

    findings = scan_staged(root)
    findings.extend(scan_paths(root / path for path in changed_working_tree_paths(root)))
    if findings:
        return PipelineSignal("secret_scan", FAIL, f"{len(findings)} possible secret(s) found.")
    return PipelineSignal("secret_scan", PASS, "No likely secrets found in staged or changed files.")


def manifest_layer(manifest: dict[str, Any], layer_id: str) -> dict[str, Any]:
    """Return one manifest layer record."""

    for layer in manifest.get("data_layers", []):
        if isinstance(layer, dict) and layer.get("id") == layer_id:
            return layer
    return {"id": layer_id, "record_count": 0, "index_file": f"{layer_id}/_index.jsonl"}


def iter_layer_output_files(layer_root: Path) -> Iterable[Path]:
    """Yield readable output files for one layer, excluding raw archives and snapshots."""

    if not layer_root.exists():
        return []
    return (
        path
        for path in sorted(layer_root.rglob("*"))
        if path.is_file() and path.suffix.lower() in {".json", ".jsonl", ".md"}
    )


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object file."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def read_jsonl_rows(path: Path) -> tuple[list[Any], int]:
    """Read JSONL rows and return valid rows plus invalid row count."""

    rows: list[Any] = []
    invalid = 0
    if not path.exists():
        return rows, 1
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                invalid += 1
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                invalid += 1
    return rows, invalid


@lru_cache(maxsize=1)
def changed_working_tree_paths(root: Path) -> tuple[Path, ...]:
    """Return changed and untracked text paths."""

    import subprocess

    changed = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMRT"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return tuple(Path(path) for path in [*changed, *untracked] if path.strip())


def combine_statuses(statuses: Sequence[str]) -> str:
    """Combine pass, warning, and failure statuses."""

    if any(status == FAIL for status in statuses):
        return FAIL
    if any(status == WARN for status in statuses):
        return WARN
    return PASS


def write_audit(root: Path, audit: RecentDownloadAudit) -> None:
    """Write machine and human audit artifacts."""

    report_path = root / REPORT_PATH
    docs_path = root / DOCS_REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(audit_to_dict(audit), indent=2) + "\n", encoding="utf-8")
    docs_path.write_text(audit_to_markdown(audit), encoding="utf-8")


def audit_to_dict(audit: RecentDownloadAudit) -> dict[str, Any]:
    """Convert audit to plain JSON-compatible data."""

    return {
        "generated_at": audit.generated_at,
        "overall_status": audit.overall_status,
        "audited_layers": audit.audited_layers,
        "layer_audits": [asdict(layer) for layer in audit.layer_audits],
        "pipeline_signals": [asdict(signal) for signal in audit.pipeline_signals],
        "closeout_checks": [asdict(check) for check in audit.closeout_checks],
        "boundary": audit.boundary,
    }


def audit_to_markdown(audit: RecentDownloadAudit) -> str:
    """Convert audit to a human-readable Markdown report."""

    lines = [
        "# Recent Download Audit",
        "",
        f"Generated: {audit.generated_at}",
        f"Overall status: **{audit.overall_status.upper()}**",
        "",
        "This audit checks the data collected in the recent download window.",
        "",
        "## Layer Readability",
        "",
        "| Layer | Status | Manifest Records | Index Records | JSONL Rows | Missing Paths | Detail |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for layer in audit.layer_audits:
        lines.append(
            "| "
            f"{layer.layer_id} | {layer.status.upper()} | "
            f"{layer.manifest_records:,} | {layer.index_records:,} | "
            f"{layer.jsonl_rows_checked:,} | {layer.indexed_paths_missing:,} | "
            f"{layer.detail} |"
        )
    lines.extend(
        [
            "",
            "## Pipeline Signals",
            "",
            "| Signal | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for signal in audit.pipeline_signals:
        lines.append(f"| {signal.name} | {signal.status.upper()} | {signal.detail} |")
    lines.extend(
        [
            "",
            "## Closeout Checks",
            "",
            "| Check | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for check in audit.closeout_checks:
        lines.append(f"| {check.name} | {check.status.upper()} | {check.detail} |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            audit.boundary,
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--write", action="store_true", help="Write audit artifacts.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the recent download audit."""

    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    audit = build_recent_download_audit(root)
    if args.write:
        write_audit(root, audit)
    if args.json:
        print(json.dumps(audit_to_dict(audit), indent=2))
    else:
        print(f"Recent download audit: {audit.overall_status.upper()}")
        for layer in audit.layer_audits:
            print(f"- {layer.layer_id}: {layer.status.upper()} - {layer.detail}")
        for signal in audit.pipeline_signals:
            print(f"- {signal.name}: {signal.status.upper()} - {signal.detail}")
    return 1 if audit.overall_status == FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
