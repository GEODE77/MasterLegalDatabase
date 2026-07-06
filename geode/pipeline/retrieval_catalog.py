"""Build a compact retrieval catalog across Geode layer indexes."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl, load_json

RETRIEVAL_CATALOG_PATH = Path(CONTROL_PLANE_DIR) / "RETRIEVAL_CATALOG.jsonl"
RETRIEVAL_CATALOG_SUMMARY_PATH = Path(CONTROL_PLANE_DIR) / "RETRIEVAL_CATALOG_SUMMARY.json"


class RetrievalCatalogRecord(BaseModel):
    """One compact record for broad AI-first retrieval."""

    id: str
    layer: str
    entity_type: str | None = None
    title: str | None = None
    citation: str | None = None
    path: str | None = None
    meta_path: str | None = None
    source_url: str | None = None
    publication_year: int | None = None
    last_updated: str | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float | None = None
    retrieval_text: str


class RetrievalCatalogSummary(BaseModel):
    """Summary for retrieval catalog coverage."""

    generated_at: datetime
    catalog_path: str
    records_written: int = Field(ge=0)
    layers_indexed: int = Field(ge=0)
    layer_counts: dict[str, int] = Field(default_factory=dict)
    boundary: str


def build_retrieval_catalog(root: Path) -> tuple[list[RetrievalCatalogRecord], RetrievalCatalogSummary]:
    """Build compact retrieval records from layer indexes."""

    resolved_root = root.resolve()
    manifest = _load_dict(resolved_root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json")
    layers = manifest.get("data_layers") if isinstance(manifest.get("data_layers"), list) else []
    records: list[RetrievalCatalogRecord] = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        layer_id = _optional_str(layer.get("id"))
        index_file = _optional_str(layer.get("index_file"))
        if not layer_id or not index_file:
            continue
        for row in _read_jsonl(resolved_root / index_file):
            record = _catalog_record(layer_id, row)
            if record:
                records.append(record)
    layer_counts = Counter(record.layer for record in records)
    summary = RetrievalCatalogSummary(
        generated_at=datetime.now(timezone.utc),
        catalog_path=RETRIEVAL_CATALOG_PATH.as_posix(),
        records_written=len(records),
        layers_indexed=len(layer_counts),
        layer_counts=dict(sorted(layer_counts.items())),
        boundary=(
            "The retrieval catalog is a compact discovery index. It does not replace source text, "
            "metadata sidecars, validation, or crosswalk records."
        ),
    )
    return records, summary


def write_retrieval_catalog(root: Path) -> RetrievalCatalogSummary:
    """Write the retrieval catalog and summary."""

    resolved_root = root.resolve()
    records, summary = build_retrieval_catalog(resolved_root)
    atomic_write_jsonl(resolved_root / RETRIEVAL_CATALOG_PATH, records, resolved_root)
    atomic_write_json(resolved_root / RETRIEVAL_CATALOG_SUMMARY_PATH, summary, resolved_root)
    return summary


def _catalog_record(layer_id: str, row: dict[str, Any]) -> RetrievalCatalogRecord | None:
    """Convert one layer index row into a retrieval catalog record."""

    record_id = _optional_str(row.get("id"))
    if not record_id:
        return None
    tags = row.get("tags") if isinstance(row.get("tags"), list) else []
    clean_tags = [str(tag) for tag in tags if str(tag).strip()]
    title = _optional_str(row.get("title"))
    citation = _optional_str(row.get("citation"))
    entity_type = _optional_str(row.get("entity_type"))
    retrieval_text = " | ".join(
        item
        for item in [
            record_id,
            layer_id,
            entity_type,
            citation,
            title,
            " ".join(clean_tags),
        ]
        if item
    )
    return RetrievalCatalogRecord(
        id=record_id,
        layer=layer_id,
        entity_type=entity_type,
        title=title,
        citation=citation,
        path=_optional_str(row.get("path")),
        meta_path=_optional_str(row.get("meta_path")),
        source_url=_optional_str(row.get("source_url")),
        publication_year=_optional_int(row.get("publication_year")),
        last_updated=_optional_str(row.get("last_updated")),
        tags=clean_tags,
        confidence=_optional_float(row.get("confidence")),
        retrieval_text=retrieval_text,
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL rows if present."""

    if not path.exists() or path.stat().st_size == 0:
        return []
    return list(iter_jsonl(path))


def _load_dict(path: Path) -> dict[str, object]:
    """Load a JSON object, returning empty when absent."""

    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _optional_str(value: object) -> str | None:
    """Convert a value to a non-empty optional string."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    """Convert a value to an optional integer."""

    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    """Convert a value to an optional float."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> None:
    """Build or write retrieval catalog artifacts."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    summary = write_retrieval_catalog(root) if args.write else build_retrieval_catalog(root)[1]
    if args.json:
        print(summary.model_dump_json(indent=2))
        return
    print(f"Retrieval catalog records: {summary.records_written}")


if __name__ == "__main__":
    main()
