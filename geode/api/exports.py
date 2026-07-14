"""Bulk export creation for the Geode API."""

from __future__ import annotations

import os
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from geode.api.auth import ApiPrincipal
from geode.constants import ALL_LAYERS, CONTROL_PLANE_DIR
from geode.utils.file_io import ensure_not_raw_archive

EXPORTS_DIR_NAME = "API_EXPORTS"
DEFAULT_EXPORT_FILE_TYPES = {".json", ".jsonl", ".md"}


@dataclass(frozen=True)
class ExportResult:
    """Summary of one created API export."""

    export_id: str
    path: Path
    size_bytes: int
    layers: tuple[str, ...]
    created_at: datetime

    def to_dict(self, root: Path) -> dict[str, object]:
        """Return a response-safe export summary."""

        return {
            "export_id": self.export_id,
            "path": self.path.relative_to(root).as_posix(),
            "size_bytes": self.size_bytes,
            "layers": list(self.layers),
            "created_at": self.created_at.isoformat(),
        }


def create_export(
    root: Path,
    principal: ApiPrincipal,
    layers: list[str] | None = None,
    include_crosswalks: bool = True,
) -> ExportResult:
    """Create a ZIP export of validated Geode output files."""

    if not principal.bulk_export_allowed:
        raise PermissionError("API key is not allowed to create bulk exports")
    project_root = root.resolve()
    selected_layers = _selected_layers(layers)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    export_id = f"export_{timestamp}_{uuid.uuid4().hex[:12]}"
    export_dir = project_root / CONTROL_PLANE_DIR / EXPORTS_DIR_NAME
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / f"{export_id}.zip"
    ensure_not_raw_archive(target, project_root)
    tmp_path = target.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            _write_manifest(project_root, archive)
            for layer in selected_layers:
                _write_layer(project_root, layer, archive)
            if include_crosswalks:
                _write_crosswalks(project_root, archive)
        os.replace(tmp_path, target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return ExportResult(
        export_id=export_id,
        path=target,
        size_bytes=target.stat().st_size,
        layers=tuple(selected_layers),
        created_at=datetime.now(timezone.utc),
    )


def export_path(root: Path, export_id: str) -> Path:
    """Return the path for an existing export ID."""

    if not export_id.startswith("export_") or any(char in export_id for char in "\\/"):
        raise ValueError("invalid export ID")
    project_root = root.resolve()
    path = project_root / CONTROL_PLANE_DIR / EXPORTS_DIR_NAME / f"{export_id}.zip"
    ensure_not_raw_archive(path, project_root)
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def _selected_layers(layers: list[str] | None) -> list[str]:
    """Validate requested export layers."""

    if not layers:
        return list(ALL_LAYERS)
    allowed = set(ALL_LAYERS)
    selected = []
    for layer in layers:
        if layer not in allowed:
            raise ValueError(f"unknown export layer: {layer}")
        selected.append(layer)
    return selected


def _write_manifest(root: Path, archive: zipfile.ZipFile) -> None:
    """Write control-plane files that describe the export."""

    for name in ("MASTER_MANIFEST.json", "MASTER_SCHEMA.json", "ONTOLOGY.json"):
        path = root / CONTROL_PLANE_DIR / name
        if path.exists():
            archive.write(path, path.relative_to(root).as_posix())


def _write_layer(root: Path, layer: str, archive: zipfile.ZipFile) -> None:
    """Write validated public files from one layer."""

    layer_dir = root / layer
    if not layer_dir.exists():
        return
    for path in layer_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in DEFAULT_EXPORT_FILE_TYPES:
            continue
        ensure_not_raw_archive(path, root)
        archive.write(path, path.relative_to(root).as_posix())


def _write_crosswalks(root: Path, archive: zipfile.ZipFile) -> None:
    """Write crosswalk JSONL files."""

    crosswalk_dir = root / "_CROSSWALKS"
    if not crosswalk_dir.exists():
        return
    for path in crosswalk_dir.glob("*.jsonl"):
        ensure_not_raw_archive(path, root)
        archive.write(path, path.relative_to(root).as_posix())
