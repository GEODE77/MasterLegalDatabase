"""Safely archive unreferenced generated local metadata versions."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from geode.pipeline.local_review import _metadata_version_audit
from geode.utils.file_io import atomic_write_json


def archive_unreferenced_metadata(root: Path, *, execute: bool = False) -> dict[str, Any]:
    """Plan or perform a reversible archive of inactive local metadata versions."""

    resolved = root.resolve()
    index_rows = []
    for layer in ("08_County_Authorities", "09_District_Authorities"):
        index_path = resolved / layer / "_index.jsonl"
        if index_path.exists():
            from geode.utils.file_io import iter_jsonl

            index_rows.extend(iter_jsonl(index_path))
    audit = _metadata_version_audit(resolved, index_rows)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_root = resolved / "_SNAPSHOTS" / f"local_metadata_versions_{timestamp}"
    archived: list[dict[str, str]] = []
    for item in audit["unreferenced_versioned_files"]:
        source = resolved / str(item["path"])
        target = archive_root / str(item["path"])
        if execute:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
        archived.append(
            {
                "source": str(item["path"]),
                "target": target.relative_to(resolved).as_posix(),
                "status": "archived" if execute else "planned",
            }
        )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execute_requested": execute,
        "archive_root": archive_root.relative_to(resolved).as_posix(),
        "items": archived,
        "boundary": "Only unreferenced generated metadata is moved. No raw source is deleted or modified.",
    }
    atomic_write_json(resolved / "_CONTROL_PLANE" / "LOCAL_METADATA_ARCHIVE_REPORT.json", report, resolved)
    return report


def main() -> int:
    """Run metadata archive planning or execution."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    report = archive_unreferenced_metadata(args.root.resolve(), execute=args.execute)
    print({"items": len(report["items"]), "executed": report["execute_requested"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
