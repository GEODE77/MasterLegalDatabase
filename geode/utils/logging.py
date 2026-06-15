"""Logging configuration for command-line modules."""

from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root logger once for CLI commands."""

    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")

