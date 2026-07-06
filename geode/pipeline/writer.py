"""Writers for validated Geode pipeline outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from geode.constants import ALL_LAYERS, CONTROL_PLANE_DIR, CRS_LAYER, QUARANTINE_DIR
from geode.schemas import (
    CRSTitleDocument,
    CrosswalkEntry,
    LayerIndexRecord,
    QuarantineRecord,
    TimelineEvent,
    UpdateLogRecord,
)
from geode.schemas.validators import crs_title_stem
from geode.utils.file_io import (
    append_jsonl_record_atomic,
    atomic_write_json,
    atomic_write_jsonl,
    atomic_write_text,
    iter_jsonl,
    load_json,
    relative_path,
)
from geode.utils.hashing import sha256_text
from geode.validation.checks import run_all_checks


class WriteResult(BaseModel):
    """Result from an atomic generic record write."""

    model_config = ConfigDict(extra="forbid")

    record_id: str
    layer: str
    output_paths: list[str]
    success: bool = True
    validation_errors: list[str] = Field(default_factory=list)


def ensure_project_structure(root: Path) -> None:
    """Create the expected Geode directory structure."""

    directories = [
        root / CONTROL_PLANE_DIR,
        root / CRS_LAYER / "_meta",
        root / "02_Regulations_CCR" / "_meta",
        root / "03_Legislation",
        root / "04_Rulemaking",
        root / "05_Executive_Orders",
        root / "06_Session_Laws",
        root / "07_Supplementary" / "ag_opinions",
        root / "07_Supplementary" / "coprrr_reviews",
        root / "_CROSSWALKS",
        root / "_RAW_ARCHIVE" / "crs",
        root / "_RAW_ARCHIVE" / "ccr",
        root / "_RAW_ARCHIVE" / "legiscan",
        root / "_RAW_ARCHIVE" / "register",
        root / "_RAW_ARCHIVE" / "exec_orders",
        root / "_RAW_ARCHIVE" / "supplementary",
        root / QUARANTINE_DIR,
        root / "_SNAPSHOTS",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def render_crs_markdown(document: CRSTitleDocument) -> str:
    """Render a CRS title document as Markdown with YAML frontmatter."""

    lines = [
        "---",
        f'entity_id: "{document.entity_id}"',
        f'title_number: "{document.title_number}"',
        f'title_name: "{document.title_name}"',
        f"publication_year: {document.publication_year}",
        f'source_url: "{str(document.source_document.source_url).rstrip("/")}"',
        f'source_path: "{document.source_document.raw_path}"',
        f"record_count: {len(document.sections)}",
        f'generated_at: "{document.generated_at.isoformat()}"',
        "---",
        "",
        f"# Title {document.title_number} - {document.title_name}",
        "",
    ]

    current_article: tuple[str, str] | None = None
    current_part: tuple[str | None, str | None] | None = None
    for section in document.sections:
        article = (section.article_number, section.article_name)
        if article != current_article:
            lines.extend([f"## Article {section.article_number} - {section.article_name}", ""])
            current_article = article
            current_part = None
        part = (section.part_number, section.part_name)
        if section.part_number and part != current_part:
            lines.extend([f"### Part {section.part_number} - {section.part_name}", ""])
            current_part = part
        lines.extend(
            [
                (
                    f"#### {section.title_number}-{section.article_number}-"
                    f"{section.section_number}. {section.heading}"
                ),
                "",
                section.text,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_record(record: dict[str, Any], layer_config: dict[str, Any]) -> WriteResult:
    """Write one validated corpus record through the seven-step atomic contract."""

    root = Path(layer_config.get("root", Path.cwd())).resolve()
    ensure_project_structure(root)
    layer = str(layer_config["layer"])
    record_id = str(record.get("id", record.get("entity_id", "")))
    validation = run_all_checks(record, root, allow_existing=True)
    if not validation.valid:
        errors = [issue.message for issue in validation.issues if issue.severity == "error"]
        raise ValueError(f"record failed validation before write: {errors}")

    now = datetime.now(timezone.utc)
    content_path = _configured_path(
        root,
        layer_config.get("content_path", layer_config.get("markdown_path")),
        default=root / layer / f"{_safe_stem(record_id)}.md",
    )
    meta_path = _configured_path(
        root,
        layer_config.get("meta_path"),
        default=root / layer / "_meta" / f"{_safe_stem(record_id)}_meta.jsonl",
    )
    index_path = _configured_path(
        root,
        layer_config.get("index_path"),
        default=root / layer / "_index.jsonl",
    )
    timeline_path = root / CONTROL_PLANE_DIR / "MASTER_TIMELINE_INDEX.jsonl"
    update_log_path = root / CONTROL_PLANE_DIR / "UPDATE_LOG.jsonl"
    manifest_path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    crosswalk_specs = list(record.get("crosswalks", layer_config.get("crosswalks", [])))
    timeline_events = list(record.get("timeline_events", layer_config.get("timeline_events", [])))
    crosswalk_paths = [
        root / "_CROSSWALKS" / str(spec.get("file", "crosswalk.jsonl"))
        for spec in crosswalk_specs
        if isinstance(spec, dict)
    ]
    touched_paths = [
        content_path,
        meta_path,
        index_path,
        *crosswalk_paths,
        timeline_path,
        update_log_path,
        manifest_path,
    ]
    originals = _capture_originals(touched_paths)
    output_paths: list[Path] = []
    try:
        markdown = _render_record_markdown(record)
        atomic_write_text(content_path, markdown, root)
        output_paths.append(content_path)
        _maybe_fail(layer_config, 1)

        _upsert_jsonl(meta_path, _corpus_record(record), root)
        output_paths.append(meta_path)
        _maybe_fail(layer_config, 2)

        _upsert_jsonl(index_path, _index_record(record, layer, content_path, meta_path, root), root)
        output_paths.append(index_path)
        _maybe_fail(layer_config, 3)

        for spec, path in zip(crosswalk_specs, crosswalk_paths, strict=False):
            crosswalk_record = CrosswalkEntry.model_validate(spec.get("record", spec))
            _upsert_jsonl(path, crosswalk_record.model_dump(mode="json"), root, key="source_id")
            output_paths.append(path)
        _maybe_fail(layer_config, 4)

        for event in timeline_events:
            timeline_event = TimelineEvent.model_validate(event)
            _upsert_jsonl(
                timeline_path,
                timeline_event.model_dump(mode="json"),
                root,
                key="id",
            )
        output_paths.append(timeline_path)
        _maybe_fail(layer_config, 5)

        _refresh_manifest(root, manifest_path, layer, index_path, now)
        output_paths.append(manifest_path)
        _maybe_fail(layer_config, 6)

        event = UpdateLogRecord(
            event_id=f"UL-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{_safe_stem(record_id)}",
            timestamp=now,
            event_type="record_written",
            layer=layer,
            entity_id=record_id,
            action="write_record",
            source_path=str(record.get("source_path", "")) or None,
            output_paths=[relative_path(path, root) for path in output_paths],
            record_count=1,
            sha256=sha256_text(markdown),
            message=f"Wrote {record_id} to {layer}.",
        )
        append_jsonl_record_atomic(update_log_path, event, root)
        output_paths.append(update_log_path)
        _maybe_fail(layer_config, 7)
    except Exception:
        _rollback(originals)
        raise

    unique_paths = []
    for path in output_paths:
        if path not in unique_paths:
            unique_paths.append(path)
    return WriteResult(
        record_id=record_id,
        layer=layer,
        output_paths=[relative_path(path, root) for path in unique_paths],
    )


def write_to_quarantine(
    record: dict[str, Any],
    reason: str,
    root: Path | None = None,
) -> Path:
    """Write a failed record to the quarantine log."""

    root = (root or Path.cwd()).resolve()
    now = datetime.now(timezone.utc)
    quarantine = QuarantineRecord(
        event_id=f"QR-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{_safe_stem(str(record.get('id', 'x')))}",
        timestamp=now,
        source_path=str(record.get("source_path", "")) or "unknown",
        layer=str(record.get("layer", CRS_LAYER)),
        reason=reason,
        confidence=float(record.get("confidence", {}).get("overall", 0.0))
        if isinstance(record.get("confidence"), dict)
        else float(record.get("confidence", 0.0) or 0.0),
    )
    return write_quarantine_record(root, quarantine)


def _configured_path(root: Path, value: object, default: Path) -> Path:
    """Resolve a configured output path under the project root."""

    if value is None:
        return default
    path = Path(str(value))
    if path.is_absolute():
        return path
    return root / path


def _safe_stem(value: str) -> str:
    """Return a filesystem-safe stem for a corpus ID."""

    return "".join(char if char.isalnum() else "_" for char in value).strip("_") or "record"


def _corpus_record(record: dict[str, Any]) -> dict[str, Any]:
    """Drop writer-only fields from a persisted metadata record."""

    return {
        key: value
        for key, value in record.items()
        if key not in {"crosswalks", "timeline_events", "layer", "publication_year", "source_path"}
    }


def _render_record_markdown(record: dict[str, Any]) -> str:
    """Render a generic legal record as Markdown with YAML frontmatter."""

    record_id = str(record.get("id", record.get("entity_id", "")))
    title = str(record.get("title", record.get("section_heading", record_id)))
    full_text = str(record.get("full_text", record.get("text", ""))).rstrip()
    frontmatter = [
        "---",
        f'id: "{record_id}"',
        f'entity_type: "{record.get("entity_type", "")}"',
        f'title: "{title}"',
        f'source_url: "{record.get("source_url", "")}"',
        "---",
        "",
    ]
    return "\n".join([*frontmatter, f"#### {record_id}. {title}", "", full_text, ""])


def _index_record(
    record: dict[str, Any],
    layer: str,
    content_path: Path,
    meta_path: Path,
    root: Path,
) -> dict[str, Any]:
    """Build an index row for a generic corpus record."""

    now = datetime.now(timezone.utc)
    full_text = str(record.get("full_text", record.get("text", "")))
    title = str(record.get("title", record.get("section_heading", record.get("id", ""))))
    confidence = record.get("confidence", 0.0)
    if isinstance(confidence, dict):
        confidence_value = float(confidence.get("overall", 0.0))
    else:
        confidence_value = float(confidence or 0.0)
    return {
        "id": record.get("id", record.get("entity_id")),
        "layer": layer,
        "entity_type": record.get("entity_type", ""),
        "title": title,
        "citation": record.get("ccr_number", record.get("id")),
        "path": relative_path(content_path, root),
        "meta_path": relative_path(meta_path, root),
        "source_url": record.get("source_url"),
        "source_path": record.get("source_path", ""),
        "publication_year": record.get("publication_year"),
        "last_updated": now.isoformat(),
        "sha256": sha256_text(full_text),
        "tags": record.get("subject_tags", []),
        "confidence": confidence_value,
    }


def _upsert_jsonl(
    path: Path,
    record: dict[str, Any],
    root: Path,
    key: str = "id",
) -> None:
    """Append or replace one JSONL record by key."""

    rows = []
    record_key = record.get(key)
    replaced = False
    if path.exists():
        for row in iter_jsonl(path):
            if row.get(key) == record_key:
                rows.append(record)
                replaced = True
            else:
                rows.append(row)
    if not replaced:
        rows.append(record)
    atomic_write_jsonl(path, rows, root)


def _refresh_manifest(
    root: Path,
    manifest_path: Path,
    layer: str,
    index_path: Path,
    now: datetime,
) -> None:
    """Refresh the manifest entry for one layer."""

    manifest = _load_manifest(root, now)
    try:
        record_count = sum(1 for _ in iter_jsonl(index_path))
    except FileNotFoundError:
        record_count = 0
    layers = manifest.get("data_layers", [])
    if isinstance(layers, list):
        for layer_entry in layers:
            if isinstance(layer_entry, dict) and layer_entry.get("id") == layer:
                layer_entry["record_count"] = record_count
                layer_entry["last_ingested"] = now.date().isoformat()
                layer_entry["last_checked"] = now.date().isoformat()
                layer_entry["staleness_days"] = 0
                layer_entry["status"] = "ready" if record_count else "empty"
                break
    atomic_write_json(manifest_path, manifest, root)


def _capture_originals(paths: list[Path]) -> dict[Path, bytes | None]:
    """Capture original file bytes before a multi-file transaction."""

    originals: dict[Path, bytes | None] = {}
    for path in paths:
        if path not in originals:
            originals[path] = path.read_bytes() if path.exists() else None
    return originals


def _rollback(originals: dict[Path, bytes | None]) -> None:
    """Restore captured file bytes after a failed write transaction."""

    for path, content in originals.items():
        if content is None:
            if path.exists():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _maybe_fail(layer_config: dict[str, Any], step: int) -> None:
    """Test hook for rollback verification."""

    if layer_config.get("fail_after_step") == step:
        raise RuntimeError(f"forced writer failure after step {step}")


def _read_existing_index(index_path: Path) -> list[LayerIndexRecord]:
    """Read existing layer index records if the index file exists."""

    if not index_path.exists():
        return []
    return [LayerIndexRecord.model_validate(row) for row in iter_jsonl(index_path)]


def _load_manifest(root: Path, now: datetime) -> dict[str, object]:
    """Load the master manifest or create a default one."""

    manifest_path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    if manifest_path.exists():
        return load_json(manifest_path)
    return {
        "project": {
            "name": "Project Geode",
            "description": "AI-first Colorado legal authority corpus.",
            "version": "0.1.0",
            "created_date": now.date().isoformat(),
        },
        "data_layers": [
            {
                "id": layer,
                "path": layer,
                "entity_type": "statute_section" if layer == CRS_LAYER else "unknown",
                "record_count": 0,
                "source": "crs" if layer == CRS_LAYER else "unknown",
                "format": ["jsonl"],
                "last_ingested": None,
                "currency": None,
                "index_file": f"{layer}/_index.jsonl",
                "known_gaps": [],
                "last_checked": None,
                "staleness_days": None,
                "status": "empty",
            }
            for layer in ALL_LAYERS
        ],
        "crosswalks_available": [],
        "freshness_policy": {},
        "system_info": {
            "pipeline_version": "0.1.0",
            "schema_version": "1.0",
            "ontology_version": "1.0",
        },
    }


def write_crs_title(root: Path, document: CRSTitleDocument) -> list[Path]:
    """Write validated CRS title outputs and update control-plane files."""

    ensure_project_structure(root)
    now = datetime.now(timezone.utc)
    stem = crs_title_stem(document.title_number)
    title_path = root / CRS_LAYER / f"{stem}.md"
    meta_path = root / CRS_LAYER / "_meta" / f"{stem}_meta.jsonl"
    index_path = root / CRS_LAYER / "_index.jsonl"
    manifest_path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    update_log_path = root / CONTROL_PLANE_DIR / "UPDATE_LOG.jsonl"

    markdown = render_crs_markdown(document)
    atomic_write_text(title_path, markdown, root)
    atomic_write_jsonl(meta_path, document.sections, root)

    existing_records = [
        record
        for record in _read_existing_index(index_path)
        if not record.entity_id.startswith(f"CRS-{document.title_number}-")
    ]
    new_records = [
        LayerIndexRecord(
            entity_id=section.entity_id,
            layer=CRS_LAYER,
            entity_type="statute_section",
            title=f"{section.entity_id}: {section.heading}",
            citation=section.entity_id,
            path=relative_path(title_path, root),
            meta_path=relative_path(meta_path, root),
            source_url=section.source_url,
            source_path=section.source_path,
            publication_year=section.publication_year,
            last_updated=now,
            sha256=sha256_text(section.text),
            tags=["statute", f"title_{document.title_number}"],
            confidence=section.confidence_overall,
        )
        for section in document.sections
    ]
    atomic_write_jsonl(index_path, [*existing_records, *new_records], root)

    manifest = _load_manifest(root, now)
    layers = manifest.get("data_layers", [])
    if isinstance(layers, list):
        for layer in layers:
            if isinstance(layer, dict) and layer.get("id") == CRS_LAYER:
                layer["record_count"] = len([*existing_records, *new_records])
                layer["last_ingested"] = now.date().isoformat()
                layer["currency"] = str(document.publication_year)
                layer["last_checked"] = now.date().isoformat()
                layer["staleness_days"] = 0
                layer["status"] = "ready"
                break
    atomic_write_json(manifest_path, manifest, root)

    output_paths = [title_path, meta_path, index_path, manifest_path]
    event = UpdateLogRecord(
        event_id=f"UL-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{stem}",
        timestamp=now,
        event_type="crs_title_ingested",
        layer=CRS_LAYER,
        entity_id=document.entity_id,
        action="write_crs_title",
        source_path=document.source_document.raw_path,
        output_paths=[relative_path(path, root) for path in output_paths],
        record_count=len(document.sections),
        sha256=sha256_text(markdown),
        message=f"Ingested CRS Title {document.title_number}.",
    )
    append_jsonl_record_atomic(update_log_path, event, root)
    return output_paths + [update_log_path]


def write_quarantine_record(root: Path, record: QuarantineRecord) -> Path:
    """Append a quarantine record for a failed ingestion."""

    ensure_project_structure(root)
    target = root / QUARANTINE_DIR / "quarantine_log.jsonl"
    append_jsonl_record_atomic(target, record, root)
    return target
