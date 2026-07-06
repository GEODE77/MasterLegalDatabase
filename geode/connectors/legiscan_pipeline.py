"""Normalize archived LegiScan bill JSON into the Geode legislation layer."""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from geode.connectors.archive_paths import raw_connector_dir
from geode.connectors.legiscan_client import download_all_sessions, download_session_report
from geode.connectors.legiscan_transformer import transform_bill
from geode.constants import CONTROL_PLANE_DIR, RAW_ARCHIVE_DIR
from geode.schemas import Bill, CrosswalkEntry, LayerIndexRecord
from geode.utils.file_io import (
    atomic_write_json,
    atomic_write_jsonl,
    atomic_write_text,
    load_json,
)
from geode.utils.hashing import sha256_text
from geode.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)

LEGISLATION_LAYER = "03_Legislation"
DATASET_DIR = "_dataset"
META_DIR = "_meta"
BILL_DATASET_NAME = "bills.jsonl"
BILL_CSV_NAME = "bills.csv"
BILL_SUMMARY_NAME = "legislation_summary.json"
BILL_META_NAME = "bills_meta.jsonl"
BILL_TO_STATUTE_NAME = "bill_to_statute.jsonl"


class LegislationPipelineSummary(BaseModel):
    """Summary for archived LegiScan normalization."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    output_root: str
    archive_dir: str
    raw_files_total: int = Field(ge=0)
    records_total: int = Field(ge=0)
    failed_files: int = Field(ge=0)
    skipped_files: int = Field(ge=0)
    bill_to_statute_rows_total: int = Field(ge=0)
    downloaded_bills: int = Field(default=0, ge=0)
    download_failed: int = Field(default=0, ge=0)
    dataset_jsonl_path: str
    dataset_csv_path: str
    index_path: str
    meta_path: str
    summary_path: str
    crosswalk_path: str
    year_files: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def write_legislation_dataset(
    output_root: Path,
    archive_dir: Path | None = None,
) -> LegislationPipelineSummary:
    """Normalize archived LegiScan JSON files into ``03_Legislation`` outputs."""

    root = output_root.resolve()
    raw_dir = archive_dir or raw_connector_dir(root / RAW_ARCHIVE_DIR, "legiscan")
    layer_dir = root / LEGISLATION_LAYER
    dataset_dir = layer_dir / DATASET_DIR
    meta_dir = layer_dir / META_DIR
    dataset_path = dataset_dir / BILL_DATASET_NAME
    csv_path = dataset_dir / BILL_CSV_NAME
    summary_path = dataset_dir / BILL_SUMMARY_NAME
    index_path = layer_dir / "_index.jsonl"
    meta_path = meta_dir / BILL_META_NAME
    crosswalk_path = root / "_CROSSWALKS" / BILL_TO_STATUTE_NAME
    ontology = load_json(root / CONTROL_PLANE_DIR / "ONTOLOGY.json")

    records, raw_total, failures = _records_from_archive(raw_dir, ontology)
    deduped = _dedupe_records(records)
    year_paths = _write_year_files(layer_dir, deduped, root)
    atomic_write_jsonl(dataset_path, [record for record, _path in deduped], root)
    _write_bill_csv(csv_path, deduped, root)
    atomic_write_jsonl(meta_path, [record for record, _path in deduped], root)
    atomic_write_jsonl(index_path, _index_rows(deduped, root), root)
    crosswalk_rows = _write_bill_crosswalks(crosswalk_path, deduped, root)
    _refresh_master_manifest(root, len(deduped))

    summary = LegislationPipelineSummary(
        generated_at=datetime.now(timezone.utc),
        output_root=root.as_posix(),
        archive_dir=raw_dir.as_posix(),
        raw_files_total=raw_total,
        records_total=len(deduped),
        failed_files=len(failures),
        skipped_files=0,
        bill_to_statute_rows_total=len(crosswalk_rows),
        dataset_jsonl_path=dataset_path.as_posix(),
        dataset_csv_path=csv_path.as_posix(),
        index_path=index_path.as_posix(),
        meta_path=meta_path.as_posix(),
        summary_path=summary_path.as_posix(),
        crosswalk_path=crosswalk_path.as_posix(),
        year_files=[path.as_posix() for path in year_paths],
        failures=failures[:100],
        warnings=[] if raw_dir.exists() else [f"missing archive dir: {raw_dir.as_posix()}"],
    )
    atomic_write_json(summary_path, summary, root)
    LOGGER.info(
        "Wrote Legislation dataset records=%s raw_files=%s crosswalk_rows=%s jsonl=%s",
        summary.records_total,
        summary.raw_files_total,
        summary.bill_to_statute_rows_total,
        summary.dataset_jsonl_path,
    )
    return summary


def run_legislation_pipeline(
    output_root: Path,
    *,
    download: bool = False,
    archive_dir: Path | None = None,
    session_year: int | None = None,
    all_sessions: bool = False,
    max_downloads: int | None = None,
    delay: float = 0.25,
    api_key: str | None = None,
) -> LegislationPipelineSummary:
    """Optionally download LegiScan JSON, then normalize archived bills."""

    root = output_root.resolve()
    raw_dir = archive_dir or raw_connector_dir(root / RAW_ARCHIVE_DIR, "legiscan")
    downloaded_bills = 0
    download_failed = 0
    if download:
        if all_sessions:
            report = download_all_sessions(
                raw_dir,
                api_key=api_key,
                delay=delay,
                max_downloads=max_downloads,
            )
            downloaded_bills = report.bills
            download_failed = report.failed
        elif session_year is not None:
            result = download_session_report(
                session_year,
                raw_dir,
                api_key=api_key,
                delay=delay,
                max_downloads=max_downloads,
            )
            downloaded_bills = len(result.raw_bills)
            download_failed = result.failed
        else:
            raise ValueError("--download requires --session-year or --all-sessions")
    summary = write_legislation_dataset(root, raw_dir).model_copy(
        update={"downloaded_bills": downloaded_bills, "download_failed": download_failed}
    )
    atomic_write_json(Path(summary.summary_path), summary, root)
    return summary


def build_parser() -> argparse.ArgumentParser:
    """Build the legislation pipeline CLI parser."""

    parser = argparse.ArgumentParser(description="Normalize archived LegiScan bills.")
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    parser.add_argument("--archive-dir", type=Path)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--session-year", type=int)
    parser.add_argument("--all-sessions", action="store_true")
    parser.add_argument("--max-downloads", type=int)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--api-key")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the legislation pipeline CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(getattr(logging, args.log_level))
    if args.max_downloads is not None and args.max_downloads < 0:
        parser.error("--max-downloads cannot be negative")
    if args.delay < 0:
        parser.error("--delay cannot be negative")
    if args.session_year is not None and args.all_sessions:
        parser.error("use either --session-year or --all-sessions, not both")
    try:
        summary = run_legislation_pipeline(
            args.output_root,
            download=args.download,
            archive_dir=args.archive_dir,
            session_year=args.session_year,
            all_sessions=args.all_sessions,
            max_downloads=args.max_downloads,
            delay=args.delay,
            api_key=args.api_key,
        )
    except Exception as exc:
        LOGGER.exception("Legislation pipeline failed: %s", exc)
        return 1
    if args.json:
        print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        print(f"Legislation records: {summary.records_total}")
        print(f"Raw bill files: {summary.raw_files_total}")
        print(f"Dataset: {summary.dataset_jsonl_path}")
    return 0


def _records_from_archive(
    archive_dir: Path,
    ontology: dict,
) -> tuple[list[tuple[Bill, Path]], int, list[str]]:
    """Read archived LegiScan bill JSON files and validate bill records."""

    if not archive_dir.exists():
        return [], 0, []
    records: list[tuple[Bill, Path]] = []
    failures: list[str] = []
    files = [
        path
        for path in sorted(archive_dir.rglob("*.json"))
        if path.name != "download_manifest.jsonl"
    ]
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            record = Bill.model_validate(transform_bill(payload, ontology))
            records.append((record, path))
        except Exception as exc:
            failures.append(f"{path.as_posix()}: {exc}")
            LOGGER.warning("LegiScan bill normalization failed path=%s error=%s", path, exc)
    return records, len(files), failures


def _dedupe_records(records: list[tuple[Bill, Path]]) -> list[tuple[Bill, Path]]:
    """Deduplicate bill records by canonical bill ID."""

    deduped: dict[str, tuple[Bill, Path]] = {}
    for record, path in records:
        deduped[record.id] = (record, path)
    return [deduped[key] for key in sorted(deduped)]


def _write_year_files(layer_dir: Path, records: list[tuple[Bill, Path]], root: Path) -> list[Path]:
    """Write one JSONL file per legislative session year."""

    grouped: dict[str, list[Bill]] = defaultdict(list)
    for record, _path in records:
        grouped[record.session].append(record)
    paths: list[Path] = []
    for session, group in sorted(grouped.items()):
        path = layer_dir / session / f"bills_{session}.jsonl"
        atomic_write_jsonl(path, group, root)
        paths.append(path)
    return paths


def _write_bill_csv(path: Path, records: list[tuple[Bill, Path]], root: Path) -> None:
    """Write a compact CSV companion for bill metadata."""

    fields = [
        "id",
        "session",
        "chamber",
        "bill_number",
        "title",
        "status",
        "status_date",
        "introduced_date",
        "statutes_amended",
        "subject_tags",
        "source_url",
        "source_path",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for record, source_path in records:
        payload = record.model_dump(mode="json")
        payload["statutes_amended"] = ";".join(payload.get("statutes_amended", []))
        payload["subject_tags"] = ";".join(payload.get("subject_tags", []))
        payload["source_path"] = source_path.as_posix()
        writer.writerow({field: payload.get(field) for field in fields})
    atomic_write_text(path, output.getvalue(), root)


def _index_rows(records: list[tuple[Bill, Path]], root: Path) -> list[LayerIndexRecord]:
    """Build legislation layer index rows."""

    now = datetime.now(timezone.utc)
    rows: list[LayerIndexRecord] = []
    for record, source_path in records:
        record_path = root / LEGISLATION_LAYER / record.session / f"bills_{record.session}.jsonl"
        meta_path = root / LEGISLATION_LAYER / META_DIR / BILL_META_NAME
        rows.append(
            LayerIndexRecord(
                id=record.id,
                layer=LEGISLATION_LAYER,
                entity_type="bill",
                title=record.title,
                citation=record.id,
                path=_relative_or_absolute(record_path, root),
                meta_path=_relative_or_absolute(meta_path, root),
                source_url=record.source_url,
                source_path=_relative_or_absolute(source_path, root),
                publication_year=int(record.session),
                last_updated=now,
                sha256=sha256_text(record.model_dump_json()),
                tags=record.subject_tags,
                confidence=record.confidence.overall,
            )
        )
    return rows


def _write_bill_crosswalks(
    path: Path,
    records: list[tuple[Bill, Path]],
    root: Path,
) -> list[CrosswalkEntry]:
    """Write bill-to-statute relationship rows."""

    today = date.today()
    rows_by_key: dict[tuple[str, str, str], CrosswalkEntry] = {}
    for record, _path in records:
        for relationship, statute_ids in (
            ("amends", record.statutes_amended),
            ("creates", record.statutes_created),
            ("repeals", record.statutes_repealed),
        ):
            for statute_id in statute_ids:
                row = CrosswalkEntry(
                    source_id=record.id,
                    source_type="bill",
                    target_id=statute_id,
                    target_type="statute_section",
                    relationship=relationship,
                    confidence=record.confidence.overall,
                    source_evidence=record.title,
                    data_retrieved=today,
                )
                rows_by_key[(record.id, statute_id, relationship)] = row
    rows = [rows_by_key[key] for key in sorted(rows_by_key)]
    atomic_write_jsonl(path, rows, root)
    return rows


def _refresh_master_manifest(root: Path, record_count: int) -> None:
    """Refresh the control-plane manifest entry for the legislation layer."""

    manifest_path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    if not manifest_path.exists():
        return
    manifest = load_json(manifest_path)
    layers = manifest.get("data_layers", []) if isinstance(manifest, dict) else []
    today = date.today().isoformat()
    if isinstance(layers, list):
        for layer in layers:
            if isinstance(layer, dict) and layer.get("id") == LEGISLATION_LAYER:
                layer["record_count"] = record_count
                layer["last_ingested"] = today if record_count else None
                layer["last_checked"] = today
                layer["staleness_days"] = 0 if record_count else None
                layer["status"] = "ready" if record_count else "empty"
                break
    atomic_write_json(manifest_path, manifest, root)


def _relative_or_absolute(path: Path, root: Path) -> str:
    """Return project-relative path when possible."""

    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
