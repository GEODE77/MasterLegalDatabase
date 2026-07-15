"""Safe file I/O helpers for Geode corpus writes."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Generator, Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from geode.constants import RAW_ARCHIVE_DIR, SNAPSHOTS_DIR

ATOMIC_REPLACE_ATTEMPTS = 20
ATOMIC_REPLACE_DELAY_SECONDS = 0.25


class RawArchiveWriteError(ValueError):
    """Raised when generated code tries to write inside `_RAW_ARCHIVE`."""


def relative_path(path: Path, root: Path) -> str:
    """Return a POSIX-style path relative to the project root."""

    return path.resolve().relative_to(root.resolve()).as_posix()


def ensure_not_raw_archive(path: Path, root: Path) -> None:
    """Block writes to the immutable raw archive."""

    resolved = path.resolve()
    raw_root = (root / RAW_ARCHIVE_DIR).resolve()
    if resolved == raw_root or resolved.is_relative_to(raw_root):
        raise RawArchiveWriteError(f"refusing to write inside immutable archive: {path}")


def snapshot_existing_file(
    target: Path,
    root: Path,
    timestamp: datetime | None = None,
) -> Path | None:
    """Copy an existing target into `_SNAPSHOTS` before overwrite."""

    if not target.exists():
        return None

    timestamp = timestamp or datetime.now(timezone.utc)
    stamp = timestamp.strftime("%Y-%m-%dT%H%M%S%fZ")
    relative = target.resolve().relative_to(root.resolve())
    snapshot_path = root / SNAPSHOTS_DIR / f"snapshot_{stamp}" / relative
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_bytes(target.read_bytes())
    return snapshot_path


def atomic_write_text(target: Path, content: str, root: Path) -> None:
    """Write UTF-8 text atomically, snapshotting any previous version."""

    ensure_not_raw_archive(target, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot_existing_file(target, root)
    tmp_path = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8", newline="\n")
        _replace_with_retry(tmp_path, target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _replace_with_retry(source: Path, target: Path) -> None:
    """Replace a file, tolerating short-lived Windows/OneDrive file locks."""

    for attempt in range(1, ATOMIC_REPLACE_ATTEMPTS + 1):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == ATOMIC_REPLACE_ATTEMPTS:
                raise
            time.sleep(ATOMIC_REPLACE_DELAY_SECONDS * attempt)


JsonRecord = BaseModel | dict[str, Any]


def _model_to_json(record: JsonRecord) -> str:
    """Serialize a validated Pydantic model as compact JSON."""

    if isinstance(record, BaseModel):
        return record.model_dump_json(exclude_none=False)
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"))


def atomic_write_json(target: Path, payload: BaseModel | dict[str, Any], root: Path) -> None:
    """Write one JSON control-plane file atomically."""

    if isinstance(payload, BaseModel):
        data = payload.model_dump(mode="json", exclude_none=False)
    else:
        data = payload
    content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(target, content, root)


def atomic_write_jsonl(target: Path, records: Iterable[JsonRecord], root: Path) -> None:
    """Write validated Pydantic records to JSONL with no blank lines."""

    lines = [_model_to_json(record) for record in records]
    content = "\n".join(lines)
    if content:
        content += "\n"
    atomic_write_text(target, content, root)


def append_jsonl_record_atomic(target: Path, record: JsonRecord, root: Path) -> None:
    """Append one validated JSONL record using atomic replacement."""

    existing_lines: list[str] = []
    if target.exists():
        lines = target.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                raise ValueError(f"blank JSONL line at {target}:{line_number}")
            json.loads(line)
            existing_lines.append(line)

    existing_lines.append(_model_to_json(record))
    atomic_write_text(target, "\n".join(existing_lines) + "\n", root)


def iter_jsonl(path: Path) -> Generator[dict[str, Any], None, None]:
    """Yield one JSON object per line without loading the full file."""

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                raise ValueError(f"blank JSONL line at {path}:{line_number}")
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL row must be an object at {path}:{line_number}")
            yield payload


def load_json(path: Path) -> Any:
    """Load a single JSON value from a control-plane file."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Read JSONL records as a streaming iterator."""

    return iter_jsonl(path)


def write_jsonl(path: Path, records: Iterable[dict[str, Any]], root: Path | None = None) -> None:
    """Write JSONL records atomically."""

    atomic_write_jsonl(path, records, root or Path.cwd())


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from a file."""

    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def write_json(path: Path, data: dict[str, Any], root: Path | None = None) -> None:
    """Write a JSON object atomically."""

    atomic_write_json(path, data, root or Path.cwd())


def append_jsonl(path: Path, record: dict[str, Any], root: Path | None = None) -> None:
    """Append a single JSONL record using atomic replacement."""

    append_jsonl_record_atomic(path, record, root or Path.cwd())
