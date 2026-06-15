"""Command-line validation entrypoint for Project Geode."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from geode.constants import ALL_LAYERS
from geode.utils.logging import configure_logging
from geode.validation.checks import validate_project

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the validation CLI argument parser."""

    parser = argparse.ArgumentParser(description="Validate Project Geode corpus files.")
    parser.add_argument("--layer", choices=[*ALL_LAYERS, "all"], required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    return parser


def main() -> int:
    """Run validation from the command line."""

    configure_logging()
    args = build_parser().parse_args()
    result = validate_project(args.root.resolve(), args.layer)
    for issue in result.issues:
        log = LOGGER.error if issue.severity == "error" else LOGGER.warning
        log("%s: %s", issue.path, issue.message)
    if result.valid:
        LOGGER.info("Validation passed for %s", args.layer)
        return 0
    LOGGER.error("Validation failed for %s with %d issue(s)", args.layer, len(result.issues))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

