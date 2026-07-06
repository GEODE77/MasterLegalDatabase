"""Step 1 readiness gate for Project Geode."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from geode.constants import ALL_LAYERS, CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, iter_jsonl, load_json

STEP1_REPORT_NAME = "STEP1_READINESS_REPORT.json"
LayerStatusLevel = Literal["empty", "blocked", "partial", "ready", "complete"]


@dataclass(frozen=True)
class LayerExpectation:
    """Completion expectations for one Step 1 source layer."""

    layer_id: str
    raw_archive_dirs: tuple[str, ...]
    requires_records: bool = True
    requires_raw_archive: bool = True
    minimum_ready_records: int = 1


LAYER_EXPECTATIONS = (
    LayerExpectation("01_Statutes_CRS", ("_RAW_ARCHIVE/crs",)),
    LayerExpectation("02_Regulations_CCR", ("_RAW_ARCHIVE/ccr",)),
    LayerExpectation(
        "03_Legislation",
        ("_RAW_ARCHIVE/legiscan", "_RAW_ARCHIVE/legiscan_documents"),
    ),
    LayerExpectation("04_Rulemaking", ("_RAW_ARCHIVE/register", "_RAW_ARCHIVE/edocket")),
    LayerExpectation("05_Executive_Orders", ("_RAW_ARCHIVE/exec_orders",)),
    LayerExpectation("06_Session_Laws", ("_RAW_ARCHIVE/crs",), minimum_ready_records=400),
    LayerExpectation("07_Supplementary", ("_RAW_ARCHIVE/supplementary",), minimum_ready_records=10),
)


class Step1LayerStatus(BaseModel):
    """Readiness status for one corpus layer."""

    layer_id: str
    status_level: LayerStatusLevel
    manifest_record_count: int = Field(ge=0)
    manifest_status: str | None = None
    index_record_count: int = Field(ge=0)
    raw_archive_file_count: int = Field(ge=0)
    ready: bool
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Step1ReadinessReport(BaseModel):
    """Overall Step 1 readiness report."""

    generated_at: datetime
    ready_for_step_2: bool
    complete_layers: int = Field(ge=0)
    ready_layers: int = Field(ge=0)
    partial_layers: int = Field(ge=0)
    blocked_layers: int = Field(ge=0)
    empty_layers: int = Field(ge=0)
    layer_count: int = Field(ge=0)
    layers: list[Step1LayerStatus]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_step: str


def build_step1_readiness_report(root: Path) -> Step1ReadinessReport:
    """Build the Step 1 completion gate from manifest, indexes, and raw archive evidence."""

    resolved_root = root.resolve()
    manifest = _load_manifest(resolved_root)
    manifest_layers = _manifest_layers_by_id(manifest)
    layer_statuses = [
        _build_layer_status(resolved_root, expectation, manifest_layers)
        for expectation in LAYER_EXPECTATIONS
    ]
    blockers = [
        f"{status.layer_id}: {blocker}"
        for status in layer_statuses
        for blocker in status.blockers
    ]
    warnings = [
        f"{status.layer_id}: {warning}"
        for status in layer_statuses
        for warning in status.warnings
    ]
    missing_manifest_layers = sorted(set(ALL_LAYERS) - set(manifest_layers))
    for layer_id in missing_manifest_layers:
        blockers.append(f"{layer_id}: missing from MASTER_MANIFEST.json")

    complete_layers = sum(status.status_level == "complete" for status in layer_statuses)
    ready_layers = sum(
        status.status_level in {"ready", "complete"} for status in layer_statuses
    )
    partial_layers = sum(status.status_level == "partial" for status in layer_statuses)
    blocked_layers = sum(status.status_level == "blocked" for status in layer_statuses)
    empty_layers = sum(status.status_level == "empty" for status in layer_statuses)
    ready_for_step_2 = not blockers and ready_layers == len(LAYER_EXPECTATIONS)
    next_step = (
        "Step 2 can begin: build query and retrieval over the completed corpus."
        if ready_for_step_2
        else (
            "Continue Step 1: resolve blocked or empty layers, then finish partial "
            "coverage before Step 2 becomes the main workstream."
        )
    )
    return Step1ReadinessReport(
        generated_at=datetime.now(timezone.utc),
        ready_for_step_2=ready_for_step_2,
        complete_layers=complete_layers,
        ready_layers=ready_layers,
        partial_layers=partial_layers,
        blocked_layers=blocked_layers,
        empty_layers=empty_layers,
        layer_count=len(layer_statuses),
        layers=layer_statuses,
        blockers=blockers,
        warnings=warnings,
        next_step=next_step,
    )


def write_step1_readiness_report(root: Path) -> Step1ReadinessReport:
    """Write the Step 1 readiness report to the control plane."""

    resolved_root = root.resolve()
    report = build_step1_readiness_report(resolved_root)
    target = resolved_root / CONTROL_PLANE_DIR / STEP1_REPORT_NAME
    atomic_write_json(target, report, resolved_root)
    return report


def _build_layer_status(
    root: Path,
    expectation: LayerExpectation,
    manifest_layers: dict[str, dict[str, Any]],
) -> Step1LayerStatus:
    """Build readiness status for one layer."""

    manifest_layer = manifest_layers.get(expectation.layer_id, {})
    manifest_count = _safe_int(manifest_layer.get("record_count"))
    manifest_status = _safe_string(manifest_layer.get("status"))
    index_path = root / expectation.layer_id / "_index.jsonl"
    index_count = _count_jsonl_rows(index_path)
    raw_count = sum(_count_raw_files(root / raw_dir) for raw_dir in expectation.raw_archive_dirs)
    blockers: list[str] = []
    warnings: list[str] = []

    if expectation.requires_records and index_count == 0:
        blockers.append("layer index has no structured records")
    if expectation.requires_records and manifest_count == 0:
        blockers.append("MASTER_MANIFEST reports zero records")
    if expectation.requires_raw_archive and raw_count == 0:
        blockers.append("raw archive has no source files")
    if manifest_status not in {"ready", "complete"}:
        blockers.append(f"manifest status is {manifest_status or 'missing'}")
    if manifest_count != index_count:
        warnings.append(
            f"manifest count {manifest_count} does not match index count {index_count}"
        )
    status_level = _status_level(
        expectation=expectation,
        manifest_status=manifest_status,
        index_count=index_count,
        manifest_count=manifest_count,
        raw_count=raw_count,
        blockers=blockers,
    )

    return Step1LayerStatus(
        layer_id=expectation.layer_id,
        status_level=status_level,
        manifest_record_count=manifest_count,
        manifest_status=manifest_status,
        index_record_count=index_count,
        raw_archive_file_count=raw_count,
        ready=not blockers,
        blockers=blockers,
        warnings=warnings,
    )


def _status_level(
    *,
    expectation: LayerExpectation,
    manifest_status: str | None,
    index_count: int,
    manifest_count: int,
    raw_count: int,
    blockers: list[str],
) -> LayerStatusLevel:
    """Return the human-facing Step 1 status level for one layer."""

    if blockers:
        if index_count == 0 and manifest_count == 0 and raw_count == 0:
            return "empty"
        return "blocked"
    if manifest_status == "complete":
        return "complete"
    if index_count < expectation.minimum_ready_records:
        return "partial"
    return "ready"


def _load_manifest(root: Path) -> dict[str, Any]:
    """Load the master manifest as an object."""

    path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _manifest_layers_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return manifest layers keyed by layer ID."""

    layers = manifest.get("data_layers")
    if not isinstance(layers, list):
        return {}
    return {
        str(layer.get("id")): layer
        for layer in layers
        if isinstance(layer, dict) and layer.get("id")
    }


def _count_jsonl_rows(path: Path) -> int:
    """Count JSONL rows, returning zero for missing or empty files."""

    if not path.exists() or path.stat().st_size == 0:
        return 0
    return sum(1 for _ in iter_jsonl(path))


def _count_raw_files(path: Path) -> int:
    """Count source-like files in a raw archive directory without mutating it."""

    if not path.exists():
        return 0
    ignored_names = {
        "download_failures.jsonl",
        "download_manifest.jsonl",
        "manifest.jsonl",
    }
    return sum(
        1
        for item in path.rglob("*")
        if item.is_file()
        and item.name not in ignored_names
        and item.suffix.lower() != ".tmp"
        and item.stat().st_size > 0
    )


def _safe_int(value: object) -> int:
    """Return a non-negative integer from manifest data."""

    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _safe_string(value: object) -> str | None:
    """Return a stripped string or None."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description="Report whether Project Geode Step 1 is complete.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    """Run the Step 1 readiness command."""

    args = _build_parser().parse_args()
    report = (
        write_step1_readiness_report(args.root)
        if args.write
        else build_step1_readiness_report(args.root)
    )
    if args.json:
        print(report.model_dump_json(indent=2))
        return
    print(f"Ready for Step 2: {report.ready_for_step_2}")
    print(f"Ready layers: {report.ready_layers}/{report.layer_count}")
    print(f"Partial layers: {report.partial_layers}/{report.layer_count}")
    print(f"Blocked layers: {report.blocked_layers}/{report.layer_count}")
    print(f"Empty layers: {report.empty_layers}/{report.layer_count}")
    for blocker in report.blockers:
        print(f"BLOCKED: {blocker}")


if __name__ == "__main__":
    main()
