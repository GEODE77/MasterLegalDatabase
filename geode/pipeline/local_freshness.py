"""Build per-source freshness status for local authority downloads."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from geode.utils.file_io import atomic_write_json, iter_jsonl


REPORT_PATH = Path("_CONTROL_PLANE") / "LOCAL_SOURCE_FRESHNESS.json"


def build_local_source_freshness(
    root: Path,
    *,
    today: date | None = None,
    attention_after_days: int = 90,
    stale_after_days: int = 180,
) -> dict[str, Any]:
    """Build freshness status for each registered local source ID."""

    if attention_after_days < 0 or stale_after_days < attention_after_days:
        raise ValueError("freshness thresholds are invalid")
    resolved = root.resolve()
    reference = today or date.today()
    latest: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(resolved / "_CONTROL_PLANE" / "LOCAL_DOWNLOAD_MANIFEST.jsonl"):
        source_id = str(row.get("source_id") or "")
        if not source_id or row.get("status") != "downloaded":
            continue
        previous = latest.get(source_id)
        if previous is None or str(row.get("retrieved_at") or "") > str(previous.get("retrieved_at") or ""):
            latest[source_id] = row
    records: list[dict[str, Any]] = []
    for source_id, row in sorted(latest.items()):
        retrieved = _parse_date(row.get("retrieved_at"))
        age = (reference - retrieved).days if retrieved else None
        if age is None:
            status = "unknown"
        elif age > stale_after_days:
            status = "stale"
        elif age > attention_after_days:
            status = "attention"
        else:
            status = "fresh"
        raw_path = Path(str(row.get("raw_path") or ""))
        records.append(
            {
                "source_id": source_id,
                "authority_id": row.get("authority_id"),
                "authority_level": row.get("authority_level"),
                "source_category": row.get("category"),
                "requested_url": row.get("requested_url"),
                "retrieved_at": row.get("retrieved_at"),
                "age_days": age,
                "status": status,
                "raw_path": row.get("raw_path"),
                "raw_exists": raw_path.exists(),
                "source_hash": row.get("sha256"),
            }
        )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today": reference.isoformat(),
        "attention_after_days": attention_after_days,
        "stale_after_days": stale_after_days,
        "sources_checked": len(records),
        "status_counts": _counts(records),
        "records": records,
        "network_refresh_performed": False,
        "boundary": "This report measures local download age and file presence; it does not prove live official freshness.",
    }
    return report


def write_local_source_freshness(root: Path, **kwargs: Any) -> dict[str, Any]:
    """Build and write the local per-source freshness report."""

    resolved = root.resolve()
    report = build_local_source_freshness(resolved, **kwargs)
    atomic_write_json(resolved / REPORT_PATH, report, resolved)
    return report


def _parse_date(value: object) -> date | None:
    """Parse an ISO timestamp or date."""

    if not value:
        return None
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None


def _counts(records: list[dict[str, Any]]) -> dict[str, int]:
    """Count freshness statuses."""

    counts: dict[str, int] = {}
    for record in records:
        status = str(record["status"])
        counts[status] = counts.get(status, 0) + 1
    return counts


def main() -> int:
    """Run the local freshness report command."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = write_local_source_freshness(args.root.resolve())
    print(report["status_counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
