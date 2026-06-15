"""Freshness report CLI for Project Geode."""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

from geode.utils.file_io import read_json
from geode.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the freshness report CLI parser."""

    parser = argparse.ArgumentParser(description="Report Project Geode layer freshness.")
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    return parser


def build_freshness_report(root: Path, today: date | None = None) -> list[dict[str, object]]:
    """Build freshness status rows from the master manifest."""

    today = today or date.today()
    manifest = read_json(root / "_CONTROL_PLANE" / "MASTER_MANIFEST.json")
    policy = manifest.get("freshness_policy", {})
    rows: list[dict[str, object]] = []
    for layer in manifest.get("data_layers", []):
        if not isinstance(layer, dict):
            continue
        last_checked = layer.get("last_checked")
        staleness_days = layer.get("staleness_days")
        if isinstance(last_checked, str) and staleness_days is None:
            checked_date = date.fromisoformat(last_checked)
            staleness_days = (today - checked_date).days
        rows.append(
            {
                "id": layer.get("id"),
                "record_count": layer.get("record_count"),
                "last_checked": last_checked,
                "staleness_days": staleness_days,
                "policy": policy,
                "status": layer.get("status"),
            }
        )
    return rows


def main() -> int:
    """Run the freshness report command."""

    configure_logging()
    args = build_parser().parse_args()
    rows = build_freshness_report(args.root.resolve())
    for row in rows:
        LOGGER.info(
            "%s records=%s staleness=%s status=%s",
            row["id"],
            row["record_count"],
            row["staleness_days"],
            row["status"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

