"""Command-line runner for Geode ingestion pipelines."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from geode.connectors.crs_bulk import run_crs_bulk_pipeline
from geode.connectors.crs_parser import parse_crs_fixture
from geode.constants import CRS_LAYER
from geode.pipeline.ccr import run_ccr_pipeline
from geode.pipeline.writer import ensure_project_structure, write_crs_title, write_quarantine_record
from geode.schemas import QuarantineRecord
from geode.utils.file_io import relative_path
from geode.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)


class PipelineConfigurationError(ValueError):
    """Raised when the bill pipeline cannot determine safe inputs."""


def _require_raw_archive_input(root: Path, input_path: Path) -> Path:
    """Require pipeline input to live under `_RAW_ARCHIVE/crs`."""

    resolved = input_path.resolve()
    raw_root = (root / "_RAW_ARCHIVE" / "crs").resolve()
    if not resolved.is_relative_to(raw_root):
        raise ValueError("CRS pipeline input must live under _RAW_ARCHIVE/crs")
    return resolved


def run_crs_pipeline(root: Path, input_path: Path, title: str, publication_year: int) -> list[Path]:
    """Run fixture-first CRS ingestion and return written output paths."""

    ensure_project_structure(root)
    candidate_input = input_path if input_path.is_absolute() else root / input_path
    archive_input = _require_raw_archive_input(root, candidate_input)
    document = parse_crs_fixture(archive_input, title, publication_year)
    return write_crs_title(root, document)


def run_bill_pipeline(
    root: Path,
    *,
    sample: bool = False,
    scrape: bool = False,
    session: str | None = None,
    dry_run: bool = False,
    taxonomy_dir: str = "taxonomies",
    fmt: str = "markdown",
) -> int:
    """Run the deterministic Colorado bill pipeline.

    Args:
        root: Project root.
        sample: Seed and use generated sample extracted-text JSON.
        scrape: Download live bill PDFs before extraction.
        session: Colorado legislative session identifier for scrape mode.
        dry_run: Print architecture and planned stages without execution.
        taxonomy_dir: Directory containing deterministic taxonomy files.
        fmt: Final formatter output format.

    Returns:
        Process exit code.
    """

    _configure_console_output()
    paths = _bill_pipeline_paths(root, taxonomy_dir)
    selection_warning = None
    try:
        mode, start_stage = _select_bill_pipeline_mode(paths, sample, scrape, session)
    except PipelineConfigurationError as exc:
        if not dry_run or not str(exc).startswith("No existing pipeline input found."):
            raise
        mode = "RESUME"
        start_stage = 2
        selection_warning = str(exc)
    stages = _planned_stages(start_stage, include_scrape=scrape)

    if dry_run:
        _print_architecture()
        _print_dry_run(mode, stages, paths, sample, selection_warning)
        return 0

    if sample:
        print("═══ SAMPLE MODE: Using generated test data (5 bills) ═══")
        _seed_sample_data(paths)
    elif scrape:
        print(f"═══ LIVE MODE: Downloading and processing session {session} ═══")

    stage_summaries: dict[str, Any] = {}
    timings: dict[str, float] = {}

    for stage in stages:
        summary = _run_stage(stage, paths, session=session, fmt=fmt)
        stage_summaries[stage["name"]] = summary["result"]
        timings[stage["name"]] = summary["seconds"]

    _print_pipeline_summary(mode, stage_summaries, timings, paths)
    if sample:
        if _has_stage_warnings(stage_summaries):
            print(
                "Pipeline completed with warnings. Resolve failed or skipped stages "
                "before running real bills."
            )
            print("For real bills: python -m geode.pipeline.run --scrape --session 2025a")
        else:
            print(
                "Pipeline tested successfully. For real bills: "
                "python -m geode.pipeline.run --scrape --session 2025a"
            )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the pipeline CLI argument parser."""

    parser = argparse.ArgumentParser(description="Run a Project Geode ingestion pipeline.")
    parser.add_argument(
        "--layer",
        choices=["crs", "bills", "ccr"],
        help='Pipeline layer. Use "crs" for fixture CRS ingestion.',
    )
    parser.add_argument("--input", type=Path)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--publication-year", type=int)
    parser.add_argument(
        "--bulk",
        action="store_true",
        help="For --layer crs, process every supported source file under _RAW_ARCHIVE/crs.",
    )
    parser.add_argument(
        "--skip-crs-crosswalks",
        action="store_true",
        help="For --layer crs --bulk, skip statute-to-regulation crosswalk rebuild.",
    )
    parser.add_argument(
        "--rule-id",
        help="CCR rule identifier (numeric). Required for --layer ccr.",
    )
    parser.add_argument(
        "--normalize-text",
        action="store_true",
        help="For --layer ccr, convert downloaded CCR archive files into regulation records.",
    )
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="For --layer ccr --normalize-text, process the CCR pilot set only.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        help="Optional cap for CCR text normalization.",
    )
    parser.add_argument(
        "--record-id",
        action="append",
        default=[],
        help="Canonical CCR ID to process during CCR text normalization.",
    )
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument(
        "--output-dir",
        default="data",
        help='Legacy single-rule CCR output directory. Default: "data".',
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Seed generated sample bill data and run deterministic bill stages.",
    )
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Download live Colorado bill PDFs before running bill stages.",
    )
    parser.add_argument(
        "--session",
        help='Session identifier for --scrape, e.g. "2025a".',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print architecture and planned bill stages without executing.",
    )
    parser.add_argument(
        "--taxonomy-dir",
        default="taxonomies",
        help='Taxonomy directory for industry tagging. Default: "taxonomies".',
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "both"],
        default="markdown",
        help='Final bill output format. Default: "markdown".',
    )
    return parser


def _bill_pipeline_paths(root: Path, taxonomy_dir: str) -> dict[str, Path]:
    """Build canonical bill pipeline paths rooted at the project directory."""

    data_dir = root / "data"
    structured_output = data_dir / "structured_output"
    return {
        "root": root,
        "data": data_dir,
        "raw_pdfs": data_dir / "raw_pdfs",
        "extracted_text": data_dir / "extracted_text",
        "sample": data_dir / "sample",
        "structured_output": structured_output,
        "bills": structured_output / "bills",
        "indices": structured_output / "indices",
        "taxonomy_dir": root / taxonomy_dir,
    }


def _select_bill_pipeline_mode(
    paths: dict[str, Path],
    sample: bool,
    scrape: bool,
    session: str | None,
) -> tuple[str, int]:
    """Choose bill pipeline mode and first stage."""

    if sample and scrape:
        raise PipelineConfigurationError("Use either --sample or --scrape, not both.")
    if scrape and not session:
        raise PipelineConfigurationError("--scrape requires --session.")
    if sample:
        return ("SAMPLE", 2)
    if scrape:
        return ("LIVE", 0)
    if _has_files(paths["extracted_text"], "*.json"):
        return ("RESUME", 2)
    if _has_files(paths["raw_pdfs"], "*.pdf"):
        return ("RESUME", 1)
    raise PipelineConfigurationError(
        "No existing pipeline input found. Use --sample for generated test data "
        "or --scrape --session 2025a for live bill PDFs."
    )


def _planned_stages(start_stage: int, *, include_scrape: bool) -> list[dict[str, Any]]:
    """Return bill pipeline stages to run."""

    all_stages: list[dict[str, Any]] = [
        {"number": 0, "name": "SCRAPE", "header": "═══ SCRAPE ═══"},
        {"number": 1, "name": "EXTRACT", "header": "═══ EXTRACT ═══"},
        {"number": 2, "name": "PARSE", "header": "═══ PARSE ═══"},
        {"number": 3, "name": "ENRICH", "header": "═══ ENRICH ═══"},
        {"number": 4, "name": "VALIDATE", "header": "═══ VALIDATE ═══"},
        {"number": 5, "name": "GRAPH", "header": "═══ GRAPH ═══"},
        {"number": 6, "name": "FORMAT", "header": "═══ FORMAT ═══"},
        {"number": 7, "name": "TAGGING", "header": "═══ TAGGING ═══"},
    ]
    return [
        stage
        for stage in all_stages
        if stage["number"] >= start_stage and (include_scrape or stage["number"] != 0)
    ]


def _run_stage(
    stage: dict[str, Any],
    paths: dict[str, Path],
    *,
    session: str | None,
    fmt: str,
) -> dict[str, Any]:
    """Run one bill pipeline stage and capture summary/timing."""

    print(stage["header"])
    started = time.perf_counter()
    try:
        result = _stage_callable(stage["name"], paths, session=session, fmt=fmt)()
    except ImportError as exc:
        result = {"skipped": True, "reason": str(exc)}
        LOGGER.warning("%s skipped: %s", stage["name"], exc)
    except Exception as exc:
        result = {"failed": 1, "error": str(exc)}
        LOGGER.warning("%s failed: %s", stage["name"], exc)

    elapsed = time.perf_counter() - started
    _print_summary(result)
    return {"result": result, "seconds": elapsed}


def _stage_callable(
    name: str,
    paths: dict[str, Path],
    *,
    session: str | None,
    fmt: str,
) -> Callable[[], Any]:
    """Return the callable for one bill pipeline stage."""

    if name == "SCRAPE":
        from scripts.scraper import download_session

        return lambda: {
            "downloaded": len(
                download_session(str(session), output_dir=str(paths["raw_pdfs"]))
            )
        }
    if name == "EXTRACT":
        from scripts.extractor import extract_all

        return lambda: extract_all(
            input_dir=str(paths["raw_pdfs"]),
            output_dir=str(paths["extracted_text"]),
        )
    if name == "PARSE":
        from scripts.bill_parser import parse_all

        return lambda: parse_all(
            input_dir=str(paths["extracted_text"]),
            output_dir=str(paths["structured_output"]),
        )
    if name == "ENRICH":
        from scripts.entity_extractor import enrich_all

        return lambda: enrich_all(str(paths["structured_output"]))
    if name == "VALIDATE":
        from scripts.validator import validate_all

        return lambda: validate_all(str(paths["structured_output"]))
    if name == "GRAPH":
        from scripts.graph_builder import _build_and_export

        return lambda: _build_and_export(
            input_dir=str(paths["structured_output"]),
            output_path=str(paths["indices"] / "bill_graph.json"),
        )
    if name == "FORMAT":
        from scripts.formatter import write_all

        return lambda: write_all(
            input_dir=str(paths["structured_output"]),
            output_dir=str(paths["bills"]),
            fmt=fmt,
        )
    if name == "TAGGING":
        try:
            from geode.scoring.industry_tagger import tag_all
        except ImportError as exc:
            def skipped(exc: ImportError = exc) -> dict[str, Any]:
                print(f"TAGGING skipped — industry tagger not available: {exc}")
                return {"skipped": True, "reason": str(exc)}

            return skipped

        return lambda: tag_all(
            input_dir=str(paths["structured_output"]),
            taxonomy_dir=str(paths["taxonomy_dir"]),
            output_dir=str(paths["indices"]),
        )
    raise ValueError(f"Unknown pipeline stage: {name}")


def _seed_sample_data(paths: dict[str, Path]) -> None:
    """Generate sample files when needed, then seed parser input."""

    from scripts.generate_sample_data import SAMPLE_BILLS, generate_all_samples, seed_pipeline

    if len(list(paths["sample"].glob("*_extracted.json"))) < len(SAMPLE_BILLS):
        generate_all_samples(str(paths["sample"]), count=len(SAMPLE_BILLS))
    seed_summary = seed_pipeline(
        sample_dir=str(paths["sample"]),
        target_dir=str(paths["extracted_text"]),
    )
    _print_summary({"sample_seed": seed_summary})


def _has_files(directory: Path, pattern: str) -> bool:
    """Return whether a directory contains files matching a pattern."""

    return directory.exists() and any(directory.glob(pattern))


def _print_architecture() -> None:
    """Print the deterministic bill data architecture."""

    print(
        """data/
├── raw_pdfs/              ← Stage 0 (--scrape): Downloaded bill PDFs
├── extracted_text/        ← Stage 1 output or seeded sample extractor JSON
├── sample/                ← Generated test data
└── structured_output/
    ├── *_parsed.json      ← Parsed, enriched, validated working files
    ├── validation_report.json
    ├── bills/             ← Layer 1: Canonical AI-readable bill files
    └── indices/           ← Layer 2: Queryable graph and tagging indices
        ├── industry_index.json
        ├── theme_index.json
        ├── crs_title_index.json
        └── bill_graph.json
taxonomies/
├── crs_title_map.json
├── naics_hierarchy.json
├── keyword_to_naics.json
└── committee_to_naics.json"""
    )


def _print_dry_run(
    mode: str,
    stages: list[dict[str, Any]],
    paths: dict[str, Path],
    sample: bool,
    warning: str | None = None,
) -> None:
    """Print dry-run details without executing stages."""

    print(f"Mode: {mode}")
    if warning:
        print(f"Input note: {warning}")
    print("Stages that would run:")
    for stage in stages:
        print(f"- {stage['name']}")
    print("Required input directories:")
    for key in ("raw_pdfs", "extracted_text", "sample", "structured_output", "taxonomy_dir"):
        print(f"- {key}: {paths[key]}")
    if sample:
        print("Sample data will be generated if needed and seeded automatically.")


def _print_pipeline_summary(
    mode: str,
    stage_summaries: dict[str, Any],
    timings: dict[str, float],
    paths: dict[str, Path],
) -> None:
    """Print final bill pipeline summary."""

    print("═══ FINAL SUMMARY ═══")
    print(f"Mode used: {mode}")
    print(f"Final bill output directory: {paths['bills']}")
    print(f"Final bill files: {len(list(paths['bills'].glob('*_final.*'))) if paths['bills'].exists() else 0}")
    tagging = stage_summaries.get("TAGGING")
    if isinstance(tagging, dict) and not tagging.get("skipped"):
        print(f"Tagged bills: {tagging.get('tagged', 0)}")
        print(f"Scope breakdown: {tagging.get('scope_breakdown', {})}")
        print(f"Confidence breakdown: {tagging.get('confidence_breakdown', {})}")
    if paths["indices"].exists():
        index_files = sorted(path.name for path in paths["indices"].glob("*.json"))
        print(f"Index files generated: {index_files}")
    print("Stage timings:")
    for stage_name, seconds in timings.items():
        print(f"- {stage_name}: {seconds:.2f}s")


def _has_stage_warnings(stage_summaries: dict[str, Any]) -> bool:
    """Return whether any stage reported a failure or skip."""

    for summary in stage_summaries.values():
        if not isinstance(summary, dict):
            continue
        failed = summary.get("failed", 0)
        if summary.get("skipped") or (isinstance(failed, int | float) and failed > 0):
            return True
    return False


def _print_summary(summary: Any) -> None:
    """Print a stage summary in a stable readable form."""

    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))


def _validate_crs_args(args: argparse.Namespace) -> None:
    """Require legacy CRS ingestion arguments when --layer crs is selected."""

    missing = [
        name
        for name in ("input", "title", "publication_year")
        if getattr(args, name) is None
    ]
    if missing:
        missing_flags = ", ".join(f"--{name.replace('_', '-')}" for name in missing)
        raise PipelineConfigurationError(f"--layer crs requires {missing_flags}.")


def main() -> int:
    """Run the selected pipeline from the command line."""

    _configure_console_output()
    configure_logging()
    args = build_parser().parse_args()
    root = args.root.resolve()
    now = datetime.now(timezone.utc)

    if args.layer == "ccr":
        if args.normalize_text or args.pilot:
            from geode.pipeline.ccr_text import normalize_ccr_text_records

            summary = normalize_ccr_text_records(
                root,
                max_items=args.max_items,
                record_ids=args.record_id,
                pilot_only=args.pilot,
                dry_run=args.dry_run,
            )
            _print_summary(summary.model_dump(mode="json"))
            return 0 if summary.failed == 0 else 2
        if not args.rule_id:
            LOGGER.error("--layer ccr requires --rule-id.")
            return 2
        return run_ccr_pipeline(
            root=args.root,
            rule_id=args.rule_id,
            output_dir=args.output_dir,
            taxonomy_dir=args.taxonomy_dir,
            dry_run=args.dry_run,
            fmt=args.format,
        )

    if args.layer == "crs":
        if args.bulk:
            summary = run_crs_bulk_pipeline(
                root,
                input_dir=args.input_dir,
                publication_year=args.publication_year,
                dry_run=args.dry_run,
                rebuild_crosswalks=not args.skip_crs_crosswalks,
            )
            _print_summary(summary.model_dump(mode="json"))
            return 0 if summary.failed_files == 0 else 1
        try:
            _validate_crs_args(args)
        except PipelineConfigurationError as exc:
            LOGGER.error("%s", exc)
            return 2
        return _run_crs_command(args, root, now)

    try:
        return run_bill_pipeline(
            root,
            sample=args.sample,
            scrape=args.scrape,
            session=args.session,
            dry_run=args.dry_run,
            taxonomy_dir=args.taxonomy_dir,
            fmt=args.format,
        )
    except PipelineConfigurationError as exc:
        LOGGER.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        LOGGER.warning("Pipeline interrupted by user.")
        return 130


def _run_crs_command(args: argparse.Namespace, root: Path, now: datetime) -> int:
    """Run the legacy CRS fixture pipeline command."""

    try:
        outputs = run_crs_pipeline(root, args.input, args.title, args.publication_year)
    except Exception as exc:
        source_path = args.input.as_posix()
        try:
            if args.input.exists():
                source_path = relative_path(args.input.resolve(), root)
        except ValueError:
            source_path = args.input.as_posix()
        write_quarantine_record(
            root,
            QuarantineRecord(
                event_id=f"QR-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{args.title}",
                timestamp=now,
                source_path=source_path,
                layer=CRS_LAYER,
                reason=str(exc),
                confidence=0.0,
                reviewed=False,
            ),
        )
        LOGGER.error("Pipeline failed: %s", exc)
        return 1

    LOGGER.info("Pipeline wrote %d files", len(outputs))
    return 0


def _configure_console_output() -> None:
    """Prefer UTF-8 console output for requested box-drawing headers."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
