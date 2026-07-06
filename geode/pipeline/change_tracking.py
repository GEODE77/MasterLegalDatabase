"""Build local change-tracking and source-freshness reports."""

from __future__ import annotations

import argparse
import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR, SNAPSHOTS_DIR
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, load_json

FULL_TEXT_DIFF_PATH = Path(CONTROL_PLANE_DIR) / "FULL_TEXT_DIFF.jsonl"
FULL_TEXT_DIFF_SUMMARY_PATH = Path(CONTROL_PLANE_DIR) / "FULL_TEXT_DIFF_SUMMARY.json"
SOURCE_FRESHNESS_REPORT_PATH = Path(CONTROL_PLANE_DIR) / "SOURCE_FRESHNESS_REPORT.json"


class TextDiffRecord(BaseModel):
    """Local diff status for one canonical text file."""

    path: str
    layer: str
    current_sha256: str
    snapshot_path: str | None = None
    snapshot_sha256: str | None = None
    diff_status: str
    added_lines: int = Field(default=0, ge=0)
    removed_lines: int = Field(default=0, ge=0)
    changed: bool


class FullTextDiffSummary(BaseModel):
    """Summary of local text diff coverage."""

    generated_at: datetime
    diff_path: str
    files_checked: int = Field(ge=0)
    files_with_prior_snapshot: int = Field(ge=0)
    files_changed: int = Field(ge=0)
    files_without_snapshot: int = Field(ge=0)
    diff_ready: bool
    boundary: str


class SourceFreshnessLayer(BaseModel):
    """Freshness status for one manifest layer."""

    layer_id: str
    status: str
    record_count: int = Field(ge=0)
    last_checked: str | None = None
    last_ingested: str | None = None
    age_days: int | None = None
    freshness_status: str
    source: str | None = None


class SourceFreshnessReport(BaseModel):
    """Local source freshness report."""

    generated_at: datetime
    layers_checked: int = Field(ge=0)
    stale_layers: int = Field(ge=0)
    unknown_layers: int = Field(ge=0)
    network_refresh_performed: bool = False
    boundary: str
    layers: list[SourceFreshnessLayer]


def build_full_text_diff(root: Path) -> tuple[list[TextDiffRecord], FullTextDiffSummary]:
    """Build local current-vs-latest-snapshot diff records."""

    resolved_root = root.resolve()
    snapshot_index = _snapshot_index(resolved_root)
    records = [
        _diff_record(resolved_root, path, snapshot_index)
        for path in _canonical_text_files(resolved_root)
    ]
    with_snapshot = sum(record.snapshot_path is not None for record in records)
    changed = sum(record.changed for record in records)
    without_snapshot = sum(record.snapshot_path is None for record in records)
    summary = FullTextDiffSummary(
        generated_at=datetime.now(timezone.utc),
        diff_path=FULL_TEXT_DIFF_PATH.as_posix(),
        files_checked=len(records),
        files_with_prior_snapshot=with_snapshot,
        files_changed=changed,
        files_without_snapshot=without_snapshot,
        diff_ready=with_snapshot > 0,
        boundary=(
            "This is a local current-vs-snapshot diff foundation. It does not fetch new law and "
            "does not prove official source changes unless snapshots exist."
        ),
    )
    return records, summary


def build_source_freshness_report(root: Path) -> SourceFreshnessReport:
    """Build freshness status from the local manifest."""

    resolved_root = root.resolve()
    manifest = _load_dict(resolved_root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json")
    layers = manifest.get("data_layers") if isinstance(manifest.get("data_layers"), list) else []
    today = date.today()
    records: list[SourceFreshnessLayer] = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        last_checked = _optional_str(layer.get("last_checked"))
        last_ingested = _optional_str(layer.get("last_ingested"))
        reference_date = _parse_date(last_checked or last_ingested)
        age_days = (today - reference_date).days if reference_date else None
        freshness_status = _freshness_status(age_days)
        records.append(
            SourceFreshnessLayer(
                layer_id=_as_str(layer.get("id"), "unknown_layer"),
                status=_as_str(layer.get("status"), "unknown"),
                record_count=int(layer.get("record_count") or 0),
                last_checked=last_checked,
                last_ingested=last_ingested,
                age_days=age_days,
                freshness_status=freshness_status,
                source=_optional_str(layer.get("source")),
            )
        )
    report = SourceFreshnessReport(
        generated_at=datetime.now(timezone.utc),
        layers_checked=len(records),
        stale_layers=sum(record.freshness_status == "stale" for record in records),
        unknown_layers=sum(record.freshness_status == "unknown" for record in records),
        boundary=(
            "Freshness is computed from local manifest dates only. No external source refresh was "
            "performed by this report."
        ),
        layers=records,
    )
    return report


def write_change_tracking(root: Path) -> tuple[FullTextDiffSummary, SourceFreshnessReport]:
    """Write full text diff and source freshness artifacts."""

    resolved_root = root.resolve()
    diff_records, diff_summary = build_full_text_diff(resolved_root)
    freshness = build_source_freshness_report(resolved_root)
    atomic_write_jsonl(resolved_root / FULL_TEXT_DIFF_PATH, diff_records, resolved_root)
    atomic_write_json(resolved_root / FULL_TEXT_DIFF_SUMMARY_PATH, diff_summary, resolved_root)
    atomic_write_json(resolved_root / SOURCE_FRESHNESS_REPORT_PATH, freshness, resolved_root)
    return diff_summary, freshness


def _canonical_text_files(root: Path) -> list[Path]:
    """Return canonical legal text files to diff."""

    patterns = [
        "01_Statutes_CRS/*.md",
        "02_Regulations_CCR/_rules/*.md",
        "02_Regulations_CCR/ccr_dept_*.md",
    ]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(path for path in root.glob(pattern) if path.is_file())
    return sorted(files)


def _diff_record(
    root: Path,
    current_path: Path,
    snapshot_index: dict[str, Path],
) -> TextDiffRecord:
    """Build one diff record."""

    relative = current_path.resolve().relative_to(root).as_posix()
    current_text = current_path.read_text(encoding="utf-8", errors="replace")
    snapshot_path = snapshot_index.get(relative)
    if not snapshot_path:
        return TextDiffRecord(
            path=relative,
            layer=relative.split("/", 1)[0],
            current_sha256=_sha256_text(current_text),
            diff_status="no_prior_snapshot",
            changed=False,
        )
    snapshot_text = snapshot_path.read_text(encoding="utf-8", errors="replace")
    added, removed = _line_change_counts(snapshot_text, current_text)
    changed = _sha256_text(snapshot_text) != _sha256_text(current_text)
    return TextDiffRecord(
        path=relative,
        layer=relative.split("/", 1)[0],
        current_sha256=_sha256_text(current_text),
        snapshot_path=snapshot_path.resolve().relative_to(root).as_posix(),
        snapshot_sha256=_sha256_text(snapshot_text),
        diff_status="changed" if changed else "unchanged",
        added_lines=added,
        removed_lines=removed,
        changed=changed,
    )


def _snapshot_index(root: Path) -> dict[str, Path]:
    """Return latest snapshot paths keyed by canonical relative path."""

    snapshot_root = root / SNAPSHOTS_DIR
    if not snapshot_root.exists():
        return {}
    index: dict[str, Path] = {}
    for snapshot_dir in sorted(snapshot_root.glob("snapshot_*")):
        if not snapshot_dir.is_dir():
            continue
        for candidate in snapshot_dir.rglob("*"):
            if not candidate.is_file():
                continue
            relative = candidate.resolve().relative_to(snapshot_dir.resolve()).as_posix()
            index[relative] = candidate
    return index


def _line_change_counts(before: str, after: str) -> tuple[int, int]:
    """Return simple added and removed line counts."""

    before_lines = before.splitlines()
    after_lines = after.splitlines()
    before_counts: dict[str, int] = {}
    after_counts: dict[str, int] = {}
    for line in before_lines:
        before_counts[line] = before_counts.get(line, 0) + 1
    for line in after_lines:
        after_counts[line] = after_counts.get(line, 0) + 1
    all_lines = set(before_counts) | set(after_counts)
    added = sum(max(after_counts.get(line, 0) - before_counts.get(line, 0), 0) for line in all_lines)
    removed = sum(max(before_counts.get(line, 0) - after_counts.get(line, 0), 0) for line in all_lines)
    return added, removed


def _freshness_status(age_days: int | None) -> str:
    """Return a simple local freshness label."""

    if age_days is None:
        return "unknown"
    if age_days > 30:
        return "stale"
    if age_days > 7:
        return "watch"
    return "fresh"


def _parse_date(value: str | None) -> date | None:
    """Parse a date or datetime string."""

    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _load_dict(path: Path) -> dict[str, object]:
    """Load a JSON object, returning empty when absent."""

    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _sha256_text(value: str) -> str:
    """Return SHA-256 for text content."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _optional_str(value: object) -> str | None:
    """Convert a value to a non-empty optional string."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_str(value: object, fallback: str) -> str:
    """Convert a value to a non-empty string."""

    text = _optional_str(value)
    return text or fallback


def main() -> None:
    """Build or write change-tracking artifacts."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    if args.write:
        diff_summary, freshness = write_change_tracking(root)
    else:
        _, diff_summary = build_full_text_diff(root)
        freshness = build_source_freshness_report(root)
    payload = {
        "diff": diff_summary.model_dump(mode="json"),
        "freshness": freshness.model_dump(mode="json"),
    }
    if args.json:
        import json

        print(json.dumps(payload, indent=2))
        return
    print(f"Text files checked: {diff_summary.files_checked}")
    print(f"Freshness layers checked: {freshness.layers_checked}")


if __name__ == "__main__":
    main()
