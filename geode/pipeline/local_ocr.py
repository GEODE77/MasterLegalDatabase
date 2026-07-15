"""Optional OCR plan and execution for quarantined local PDFs."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from geode.utils.file_io import atomic_write_json, iter_jsonl


REPORT_PATH = Path("_CONTROL_PLANE") / "LOCAL_OCR_REPORT.json"
DERIVED_ROOT = Path("_DERIVED") / "local_ocr"


def run_local_ocr(root: Path, *, execute: bool = False) -> dict[str, Any]:
    """Report OCR readiness or run OCR into derived files only."""

    resolved = root.resolve()
    rows = [
        row
        for row in iter_jsonl(resolved / "_CONTROL_PLANE" / "LOCAL_OCR_QUEUE.jsonl")
    ]
    executable = shutil.which("tesseract")
    results: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "source_id": row.get("source_id"),
            "authority_id": row.get("authority_id"),
            "source_category": row.get("source_category"),
            "source_path": row.get("source_path"),
            "source_hash": row.get("source_hash"),
            "status": "pending_dependency" if not executable else "ready",
            "derived_path": None,
        }
        if execute and executable:
            item.update(_execute_one(resolved, row, executable))
        results.append(item)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ocr_engine": executable,
        "execute_requested": execute,
        "items": results,
        "pending_items": sum(item["status"] != "completed" for item in results),
        "completed_items": sum(item["status"] == "completed" for item in results),
        "boundary": (
            "OCR output is derived text for review. It never modifies the preserved raw source and "
            "never promotes OCR text directly into answer-safe legal records."
        ),
    }
    atomic_write_json(resolved / REPORT_PATH, report, resolved)
    return report


def _execute_one(root: Path, row: dict[str, Any], executable: str) -> dict[str, Any]:
    """Run one PDF through Tesseract when the optional dependency exists."""

    import fitz

    source_path = Path(str(row.get("source_path") or ""))
    if not source_path.exists():
        return {"status": "missing_source"}
    source_hash = str(row.get("source_hash") or source_path.stat().st_size)
    output = root / DERIVED_ROOT / f"{source_hash}.txt"
    pages: list[str] = []
    with fitz.open(source_path) as document:
        for number, page in enumerate(document, start=1):
            with tempfile.TemporaryDirectory(prefix="geode-ocr-") as temporary:
                image_path = Path(temporary) / f"page-{number}.png"
                page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(image_path)
                result = subprocess.run(
                    [executable, str(image_path), "stdout", "-l", "eng"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    return {"status": "failed", "message": result.stderr[-500:]}
                pages.append(f"[Page {number}]\n{result.stdout.strip()}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n\n".join(pages), encoding="utf-8")
    return {"status": "completed", "derived_path": output.relative_to(root).as_posix()}


def main() -> int:
    """Run the local OCR readiness or execution command."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    report = run_local_ocr(args.root.resolve(), execute=args.execute)
    print({"pending_items": report["pending_items"], "completed_items": report["completed_items"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
