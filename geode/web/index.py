"""Build the local read index used by Geode retrieval."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geode.constants import ALL_LAYERS, CONTROL_PLANE_DIR
from geode.utils.file_io import ensure_not_raw_archive, iter_jsonl
from geode.utils.hashing import sha256_text
from geode.web.db import IndexRun

MAX_DIRECT_TEXT_BYTES = 100_000
CHUNK_TARGET_CHARS = 1_800


@dataclass(frozen=True)
class IndexBuildResult:
    """Stable count summary from a read-index build."""

    entity_count: int
    alias_count: int
    chunk_count: int
    relation_count: int
    timeline_count: int


def build_index(root: Path, database_path: Path, rebuild: bool = False) -> IndexBuildResult:
    """Build a read-optimized SQLite index from Geode's structured corpus."""

    project_root = root.resolve()
    target = database_path.resolve()
    ensure_not_raw_archive(target, project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target) as connection:
        connection.row_factory = sqlite3.Row
        _create_schema(connection)
        if rebuild:
            _clear_schema(connection)
        counts = _index_corpus(connection, project_root)
        connection.execute(
            """
            INSERT INTO index_runs (
                entity_count, alias_count, chunk_count, relation_count, timeline_count
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                counts.entity_count,
                counts.alias_count,
                counts.chunk_count,
                counts.relation_count,
                counts.timeline_count,
            ),
        )
    if rebuild:
        with sqlite3.connect(target) as vacuum_connection:
            vacuum_connection.execute("VACUUM")
    return IndexBuildResult(
        entity_count=counts.entity_count,
        alias_count=counts.alias_count,
        chunk_count=counts.chunk_count,
        relation_count=counts.relation_count,
        timeline_count=counts.timeline_count,
    )


def _create_schema(connection: sqlite3.Connection) -> None:
    """Create read-index tables."""

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS entities (
            geode_id TEXT PRIMARY KEY,
            layer TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            title TEXT NOT NULL,
            citation TEXT,
            path TEXT NOT NULL,
            source_url TEXT NOT NULL,
            publication_year INTEGER,
            sha256 TEXT NOT NULL,
            confidence REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS aliases (
            alias TEXT PRIMARY KEY,
            geode_id TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunks (
            geode_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            normalized_text TEXT NOT NULL,
            path TEXT NOT NULL,
            PRIMARY KEY (geode_id, chunk_index)
        );
        CREATE TABLE IF NOT EXISTS relations (
            source_geode_id TEXT NOT NULL,
            target_geode_id TEXT NOT NULL,
            relationship TEXT NOT NULL,
            confidence REAL NOT NULL,
            evidence TEXT,
            PRIMARY KEY (source_geode_id, target_geode_id, relationship)
        );
        CREATE TABLE IF NOT EXISTS timeline_events (
            event_id TEXT PRIMARY KEY,
            event_date TEXT NOT NULL,
            event_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            description TEXT NOT NULL,
            file_path TEXT
        );
        CREATE TABLE IF NOT EXISTS source_versions (
            geode_id TEXT NOT NULL,
            version_label TEXT NOT NULL,
            path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            PRIMARY KEY (geode_id, version_label)
        );
        CREATE TABLE IF NOT EXISTS index_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_count INTEGER NOT NULL,
            alias_count INTEGER NOT NULL,
            chunk_count INTEGER NOT NULL,
            relation_count INTEGER NOT NULL,
            timeline_count INTEGER NOT NULL
        );
        """
    )


def _clear_schema(connection: sqlite3.Connection) -> None:
    """Clear existing read-index rows."""

    for table in [
        "entities",
        "aliases",
        "chunks",
        "relations",
        "timeline_events",
        "source_versions",
        "index_runs",
    ]:
        connection.execute(f"DELETE FROM {table}")


def _index_corpus(connection: sqlite3.Connection, root: Path) -> IndexRun:
    """Index entities, relations, and timeline rows."""

    entity_count = 0
    alias_count = 0
    chunk_count = 0
    meta_cache: dict[Path, dict[str, str]] = {}
    for layer in ALL_LAYERS:
        index_path = root / layer / "_index.jsonl"
        if not index_path.exists():
            continue
        for row in iter_jsonl(index_path):
            indexed = _index_entity(connection, root, layer, row, meta_cache)
            entity_count += 1
            alias_count += indexed["aliases"]
            chunk_count += indexed["chunks"]

    relation_count = _index_relations(connection, root)
    timeline_count = _index_timeline(connection, root)
    return IndexRun(entity_count, alias_count, chunk_count, relation_count, timeline_count)


def _index_entity(
    connection: sqlite3.Connection,
    root: Path,
    layer: str,
    row: dict[str, Any],
    meta_cache: dict[Path, dict[str, str]],
) -> dict[str, int]:
    """Index one layer-index row."""

    geode_id = str(row.get("id") or row.get("entity_id"))
    path = _preferred_text_path(root, row)
    text = _entity_text(root, path, geode_id, _metadata_text(row, geode_id), row, meta_cache)
    digest = str(row.get("sha256") or sha256_text(text or geode_id))
    title = str(row.get("title") or row.get("citation") or geode_id)
    citation = row.get("citation")
    confidence = _confidence_value(row.get("confidence"))
    connection.execute(
        """
        INSERT OR REPLACE INTO entities (
            geode_id, layer, entity_type, title, citation, path, source_url,
            publication_year, sha256, confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            geode_id,
            layer,
            str(row.get("entity_type") or ""),
            title,
            str(citation) if citation is not None else None,
            path,
            str(row.get("source_url") or ""),
            row.get("publication_year"),
            digest,
            confidence,
        ),
    )
    alias_count = _insert_aliases(connection, geode_id, [geode_id, title, citation])
    chunk_count = _insert_chunks(connection, geode_id, path, text)
    connection.execute(
        """
        INSERT OR REPLACE INTO source_versions (geode_id, version_label, path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        (geode_id, "current", path, digest),
    )
    return {"aliases": alias_count, "chunks": chunk_count}


def _entity_text(
    root: Path,
    path: str,
    geode_id: str,
    fallback: str,
    row: dict[str, Any],
    meta_cache: dict[Path, dict[str, str]],
) -> str:
    """Return searchable text for one entity from its content path."""

    meta_text = _meta_text(root, row, geode_id, meta_cache)
    if meta_text:
        return meta_text
    if not path:
        return fallback
    source = root / path
    if not source.exists():
        return fallback
    if source.suffix.casefold() == ".jsonl":
        return _jsonl_record_text(source, geode_id, fallback)
    if source.suffix.casefold() == ".json":
        return _json_file_text(source, fallback)
    if source.stat().st_size > MAX_DIRECT_TEXT_BYTES:
        return fallback
    return _strip_frontmatter(source.read_text(encoding="utf-8", errors="ignore"))


def _preferred_text_path(root: Path, row: dict[str, Any]) -> str:
    """Return the best available content path for a layer-index row."""

    geode_id = str(row.get("id") or row.get("entity_id") or "")
    if row.get("layer") == "02_Regulations_CCR" or geode_id.endswith("_CCR"):
        rule_path = root / "02_Regulations_CCR" / "_rules" / f"{geode_id}.md"
        if rule_path.exists():
            return rule_path.resolve().relative_to(root).as_posix()
    return str(row.get("path") or row.get("content_path") or row.get("file_path") or "")


def _meta_text(
    root: Path,
    row: dict[str, Any],
    geode_id: str,
    meta_cache: dict[Path, dict[str, str]],
) -> str | None:
    """Return record-level full text from a metadata sidecar when present."""

    meta_path = row.get("meta_path")
    if not isinstance(meta_path, str) or not meta_path.endswith(".jsonl"):
        return None
    path = root / meta_path
    if not path.exists():
        return None
    if path not in meta_cache:
        records: dict[str, str] = {}
        for payload in iter_jsonl(path):
            record_id = payload.get("id") or payload.get("entity_id")
            if isinstance(record_id, str):
                records[record_id] = _structured_record_text(payload)
        meta_cache[path] = records
    return meta_cache[path].get(geode_id)


def _jsonl_record_text(path: Path, geode_id: str, fallback: str) -> str:
    """Return useful searchable text for one row inside a JSONL file."""

    for payload in iter_jsonl(path):
        record_id = payload.get("id") or payload.get("entity_id")
        if record_id == geode_id:
            return _structured_record_text(payload) or fallback
    return fallback


def _json_file_text(path: Path, fallback: str) -> str:
    """Return useful searchable text from one structured JSON file."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    if not isinstance(payload, dict):
        return fallback
    values = [value for value in payload.values() if isinstance(value, str)]
    return " ".join(values) or fallback


def _structured_record_text(payload: dict[str, Any]) -> str:
    """Return stable human-readable text from one structured corpus record."""

    priority_fields = [
        "id",
        "citation",
        "title",
        "summary",
        "full_text",
        "text",
        "description",
        "order_number",
        "bill_id",
        "chapter",
        "effective_date",
        "signed_date",
        "issued_date",
        "governor",
        "attorney_general",
        "source_url",
    ]
    values: list[str] = []
    for field in priority_fields:
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    for field in ["statutes_cited", "statutes_affected", "statutes_interpreted", "subject_tags"]:
        value = payload.get(field)
        if isinstance(value, list):
            values.extend(str(item) for item in value if item)
    return "\n\n".join(dict.fromkeys(values))


def _strip_frontmatter(value: str) -> str:
    """Remove simple YAML frontmatter from Markdown text."""

    if not value.startswith("---"):
        return value
    marker = value.find("---", 3)
    if marker == -1:
        return value
    return value[marker + 3 :].strip()


def _metadata_text(row: dict[str, Any], geode_id: str) -> str:
    """Return compact metadata text for first-pass retrieval."""

    values = [
        geode_id,
        row.get("title"),
        row.get("citation"),
        row.get("entity_type"),
        row.get("summary"),
        row.get("source_url"),
    ]
    tags = row.get("tags") or row.get("subject_tags") or []
    if isinstance(tags, list):
        values.extend(tags)
    return " ".join(str(value) for value in values if value)


def _insert_aliases(
    connection: sqlite3.Connection,
    geode_id: str,
    values: list[object],
) -> int:
    """Insert normalized aliases for one entity."""

    aliases: set[str] = set()
    for value in values:
        if value is None:
            continue
        aliases.update(_alias_variants(str(value)))
    aliases.discard("")
    for alias in aliases:
        connection.execute(
            "INSERT OR REPLACE INTO aliases (alias, geode_id) VALUES (?, ?)",
            (alias, geode_id),
        )
    return len(aliases)


def _insert_chunks(
    connection: sqlite3.Connection,
    geode_id: str,
    path: str,
    text: str,
) -> int:
    """Insert simple searchable chunks for one entity."""

    chunks = _chunk_text(text)
    if not chunks:
        return 0
    for index, chunk in enumerate(chunks):
        connection.execute(
            """
            INSERT OR REPLACE INTO chunks (geode_id, chunk_index, text, normalized_text, path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (geode_id, index, chunk, _normalize_alias(chunk), path),
        )
    return len(chunks)


def _chunk_text(text: str) -> list[str]:
    """Split legal text into stable paragraph-aware chunks."""

    paragraphs = [" ".join(part.split()) for part in text.splitlines() if part.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for paragraph in paragraphs:
        if current and current_length + len(paragraph) + 1 > CHUNK_TARGET_CHARS:
            chunks.append("\n\n".join(current))
            current = []
            current_length = 0
        current.append(paragraph)
        current_length += len(paragraph) + 1
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _index_relations(connection: sqlite3.Connection, root: Path) -> int:
    """Index crosswalk relationship rows."""

    crosswalk_root = root / "_CROSSWALKS"
    if not crosswalk_root.exists():
        return 0
    count = 0
    for path in sorted(crosswalk_root.glob("*.jsonl")):
        for row in iter_jsonl(path):
            source_id = row.get("source_id") or row.get("source_entity_id")
            target_id = row.get("target_id") or row.get("target_entity_id")
            if not source_id or not target_id:
                continue
            connection.execute(
                """
                INSERT OR REPLACE INTO relations (
                    source_geode_id, target_geode_id, relationship, confidence, evidence
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(source_id),
                    str(target_id),
                    str(row.get("relationship") or path.stem),
                    _confidence_value(row.get("confidence")),
                    row.get("source_evidence") or row.get("evidence"),
                ),
            )
            count += 1
    return count


def _index_timeline(connection: sqlite3.Connection, root: Path) -> int:
    """Index master timeline rows."""

    path = root / CONTROL_PLANE_DIR / "MASTER_TIMELINE_INDEX.jsonl"
    if not path.exists():
        return 0
    count = 0
    for row in iter_jsonl(path):
        event_id = row.get("id") or row.get("event_id")
        entity_id = row.get("entity_id")
        if not event_id or not entity_id:
            continue
        connection.execute(
            """
            INSERT OR REPLACE INTO timeline_events (
                event_id, event_date, event_type, entity_id, description, file_path
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(event_id),
                str(row.get("date") or row.get("event_date") or ""),
                str(row.get("event_type") or ""),
                str(entity_id),
                str(row.get("description") or ""),
                row.get("file_path"),
            ),
        )
        count += 1
    return count


def _confidence_value(value: object) -> float:
    """Return a scalar confidence value."""

    if isinstance(value, dict):
        return float(value.get("overall") or 0.0)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _normalize_alias(value: str) -> str:
    """Normalize lookup/search text."""

    return " ".join(
        value.casefold()
        .replace(".", " ")
        .replace(",", " ")
        .replace("-", " ")
        .replace("_", " ")
        .split()
    )


def _alias_variants(value: str) -> set[str]:
    """Return forgiving exact-match aliases for one label."""

    normalized = _normalize_alias(value)
    compact = normalized.replace(" ", "")
    return {item for item in {normalized, compact} if item}


def main() -> None:
    """Build the Geode read index from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("geode/web/data/structured_output/commons.sqlite3"),
    )
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    result = build_index(root=args.root, database_path=args.database, rebuild=args.rebuild)
    print(
        json.dumps(
            {
                "entity_count": result.entity_count,
                "alias_count": result.alias_count,
                "chunk_count": result.chunk_count,
                "relation_count": result.relation_count,
                "timeline_count": result.timeline_count,
            }
        )
    )


if __name__ == "__main__":
    main()
