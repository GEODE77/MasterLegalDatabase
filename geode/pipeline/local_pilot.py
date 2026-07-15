"""Materialize validated local authority identities for the bounded pilot."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

from geode.schemas import ConfidenceScores, LayerIndexRecord, LocalAuthority
from geode.utils.file_io import atomic_write_jsonl, iter_jsonl, load_json


def materialize_pilot_authorities(root: Path) -> dict[str, int]:
    """Write registered county and district identities and their indexes."""

    resolved_root = root.resolve()
    registry = load_json(resolved_root / "_CONTROL_PLANE" / "LOCAL_SOURCE_REGISTRY.json")
    pilot = registry["pilot"]
    counts: dict[str, int] = {}
    for level, layer, entries_key in (
        ("county", "08_County_Authorities", "counties"),
        ("district", "09_District_Authorities", "districts"),
    ):
        records = [_authority_from_entry(entry) for entry in pilot.get(entries_key, [])]
        metadata_path = resolved_root / layer / "_meta" / "local_authorities.jsonl"
        atomic_write_jsonl(metadata_path, records, resolved_root)
        indexes = [_index_record(record, metadata_path, resolved_root, layer) for record in records]
        index_path = resolved_root / layer / "_index.jsonl"
        existing_rules = [row for row in iter_jsonl(index_path) if row.get("entity_type") == "local_rule"]
        atomic_write_jsonl(index_path, [*indexes, *existing_rules], resolved_root)
        counts[level] = len(records)
    return counts


def _authority_from_entry(entry: dict[str, object]) -> LocalAuthority:
    """Convert one registry entry into a validated local authority identity."""

    return LocalAuthority(
        id=str(entry["authority_id"]),
        authority_level=str(entry["authority_level"]),
        authority_type=str(entry["authority_type"]),
        name=str(entry["name"]),
        county_names=[str(value) for value in entry.get("county_names", [])],
        district_family=entry.get("district_family"),
        official_url=str(entry["url"]),
        source_url=str(entry["url"]),
        boundary_description="; ".join(str(value) for value in entry.get("known_gaps", [])),
        data_retrieved=date.today(),
        confidence=ConfidenceScores(overall=0.65, route="flag_accept"),
    )


def _index_record(record: LocalAuthority, metadata_path: Path, root: Path, layer: str) -> LayerIndexRecord:
    """Create a machine-readable index row for one local authority."""

    relative_meta = metadata_path.resolve().relative_to(root.resolve()).as_posix()
    source_hash = hashlib.sha256(str(record.source_url).encode("utf-8")).hexdigest()
    return LayerIndexRecord(
        id=record.id,
        layer=layer,
        entity_type=record.entity_type,
        title=record.name,
        citation=record.id,
        path=relative_meta,
        meta_path=relative_meta,
        source_url=record.source_url,
        source_path=f"_RAW_ARCHIVE/local/{record.authority_level}/{record.id}",
        last_updated=datetime.now(timezone.utc),
        sha256=source_hash,
        tags=[record.authority_type, *(record.county_names or [])],
        confidence=record.confidence.overall,
        authority_id=record.id,
        authority_name=record.name,
        authority_level=record.authority_level,
        authority_type=record.authority_type,
        district_family=record.district_family,
        county_names=record.county_names,
        geographic_scope=record.county_names,
    )
