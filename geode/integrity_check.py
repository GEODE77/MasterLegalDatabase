"""Command-line integrity-check entrypoint for Project Geode."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from geode.utils.logging import configure_logging
from geode.validation.integrity import run_integrity_check

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the integrity check CLI argument parser."""

    parser = argparse.ArgumentParser(description="Run Project Geode integrity checks.")
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    return parser


def main() -> int:
    """Run integrity checks from the command line."""

    configure_logging()
    args = build_parser().parse_args()
    result = run_integrity_check(args.root.resolve())
    for issue in result.issues:
        log = LOGGER.error if issue.severity == "error" else LOGGER.warning
        log("%s: %s", issue.path, issue.message)
    if result.valid:
        LOGGER.info("Integrity checks passed")
        return 0
    LOGGER.error("Integrity checks failed with %d issue(s)", len(result.issues))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
