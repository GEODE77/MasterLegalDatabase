"""Command-line runner for Geode ingestion pipelines."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

from geode.connectors.crs_parser import parse_crs_fixture
from geode.constants import CRS_LAYER
from geode.pipeline.writer import ensure_project_structure, write_crs_title, write_quarantine_record
from geode.schemas import QuarantineRecord
from geode.utils.file_io import relative_path
from geode.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)


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


def build_parser() -> argparse.ArgumentParser:
    """Build the pipeline CLI argument parser."""

    parser = argparse.ArgumentParser(description="Run a Project Geode ingestion pipeline.")
    parser.add_argument("--layer", choices=["crs"], required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--publication-year", required=True, type=int)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    return parser


def main() -> int:
    """Run the selected pipeline from the command line."""

    configure_logging()
    args = build_parser().parse_args()
    root = args.root.resolve()
    now = datetime.now(timezone.utc)
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


if __name__ == "__main__":
    raise SystemExit(main())
