"""SQLite repository for the rebuildable Geode Commons read index."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from geode.web.models import (
    CorpusEntity,
    EntityAlias,
    EntityRelation,
    EntityTextChunk,
    IndexRun,
    SearchResult,
    SourceVersion,
    TimelineEvent,
)


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS corpus_entities (
        geode_id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        layer TEXT NOT NULL,
        citation TEXT,
        title TEXT NOT NULL,
        summary TEXT,
        source_url TEXT,
        source_path TEXT,
        content_path TEXT,
        meta_path TEXT,
        sha256 TEXT NOT NULL,
        confidence REAL NOT NULL,
        subject_tags TEXT NOT NULL,
        industry_tags TEXT NOT NULL,
        agency_code TEXT,
        effective_date TEXT,
        publication_year INTEGER,
        status TEXT,
        indexed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entity_aliases (
        id TEXT PRIMARY KEY,
        entity_geode_id TEXT NOT NULL,
        alias TEXT NOT NULL,
        alias_type TEXT NOT NULL,
        normalized_alias TEXT NOT NULL,
        UNIQUE(entity_geode_id, alias_type, normalized_alias)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entity_text_chunks (
        id TEXT PRIMARY KEY,
        entity_geode_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        heading_path TEXT NOT NULL,
        text TEXT NOT NULL,
        start_char INTEGER,
        end_char INTEGER,
        sha256 TEXT NOT NULL,
        citation_scope TEXT,
        UNIQUE(entity_geode_id, chunk_index, sha256)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entity_relations (
        id TEXT PRIMARY KEY,
        source_geode_id TEXT NOT NULL,
        source_type TEXT,
        target_geode_id TEXT NOT NULL,
        target_type TEXT,
        relationship TEXT NOT NULL,
        confidence REAL NOT NULL,
        source_evidence TEXT,
        crosswalk_file TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS timeline_events (
        id TEXT PRIMARY KEY,
        legal_document_id TEXT,
        event_type TEXT NOT NULL,
        label TEXT NOT NULL,
        date TEXT NOT NULL,
        source_reference TEXT,
        related_entity_id TEXT,
        metadata TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_versions (
        id TEXT PRIMARY KEY,
        entity_geode_id TEXT NOT NULL,
        version_label TEXT NOT NULL,
        source_url TEXT,
        source_path TEXT,
        content_path TEXT,
        sha256 TEXT NOT NULL,
        indexed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS index_runs (
        id TEXT PRIMARY KEY,
        started_at TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        root TEXT NOT NULL,
        manifest_sha256 TEXT,
        entity_count INTEGER NOT NULL,
        alias_count INTEGER NOT NULL,
        chunk_count INTEGER NOT NULL,
        relation_count INTEGER NOT NULL,
        timeline_count INTEGER NOT NULL,
        status TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_alias_normalized ON entity_aliases(normalized_alias)",
    "CREATE INDEX IF NOT EXISTS idx_entity_title ON corpus_entities(title)",
    "CREATE INDEX IF NOT EXISTS idx_chunk_entity ON entity_text_chunks(entity_geode_id)",
    "CREATE INDEX IF NOT EXISTS idx_relation_source ON entity_relations(source_geode_id)",
    "CREATE INDEX IF NOT EXISTS idx_relation_target ON entity_relations(target_geode_id)",
    "CREATE INDEX IF NOT EXISTS idx_timeline_entity ON timeline_events(legal_document_id)",
    "CREATE INDEX IF NOT EXISTS idx_source_version_entity ON source_versions(entity_geode_id)",
)


def normalize_alias(value: str) -> str:
    """Normalize an alias for stable case-insensitive lookup."""

    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def connect_database(database_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection and initialize the read-index schema."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    initialize_database(connection)
    return connection


@contextmanager
def database_connection(database_path: Path) -> Any:
    """Yield a SQLite connection and close it after use."""

    connection = connect_database(database_path)
    try:
        yield connection
    finally:
        connection.close()


def initialize_database(connection: sqlite3.Connection) -> None:
    """Create read-index tables and indexes if they do not exist."""

    with connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)


def _json_list(value: list[str]) -> str:
    """Serialize a string list for SQLite storage."""

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_object(value: dict[str, Any]) -> str:
    """Serialize a dictionary for SQLite storage."""

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_list(value: str | None) -> list[str]:
    """Load a JSON list from SQLite storage."""

    if not value:
        return []
    payload = json.loads(value)
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload]


def _load_object(value: str | None) -> dict[str, Any]:
    """Load a JSON object from SQLite storage."""

    if not value:
        return {}
    payload = json.loads(value)
    if not isinstance(payload, dict):
        return {}
    return payload


def _entity_from_row(row: sqlite3.Row) -> CorpusEntity:
    """Convert a SQLite row into a corpus entity model."""

    return CorpusEntity(
        geode_id=row["geode_id"],
        entity_type=row["entity_type"],
        layer=row["layer"],
        citation=row["citation"],
        title=row["title"],
        summary=row["summary"],
        source_url=row["source_url"],
        source_path=row["source_path"],
        content_path=row["content_path"],
        meta_path=row["meta_path"],
        sha256=row["sha256"],
        confidence=float(row["confidence"]),
        subject_tags=_load_list(row["subject_tags"]),
        industry_tags=_load_list(row["industry_tags"]),
        agency_code=row["agency_code"],
        effective_date=row["effective_date"],
        publication_year=row["publication_year"],
        status=row["status"],
        indexed_at=row["indexed_at"],
    )


def _chunk_from_row(row: sqlite3.Row) -> EntityTextChunk:
    """Convert a SQLite row into a text chunk model."""

    return EntityTextChunk(
        id=row["id"],
        entity_geode_id=row["entity_geode_id"],
        chunk_index=row["chunk_index"],
        heading_path=_load_list(row["heading_path"]),
        text=row["text"],
        start_char=row["start_char"],
        end_char=row["end_char"],
        sha256=row["sha256"],
        citation_scope=row["citation_scope"],
    )


def _relation_from_row(row: sqlite3.Row) -> EntityRelation:
    """Convert a SQLite row into an entity relation model."""

    return EntityRelation(
        id=row["id"],
        source_geode_id=row["source_geode_id"],
        source_type=row["source_type"],
        target_geode_id=row["target_geode_id"],
        target_type=row["target_type"],
        relationship=row["relationship"],
        confidence=float(row["confidence"]),
        source_evidence=row["source_evidence"],
        crosswalk_file=row["crosswalk_file"],
    )


def _timeline_from_row(row: sqlite3.Row) -> TimelineEvent:
    """Convert a SQLite row into a timeline event model."""

    return TimelineEvent(
        id=row["id"],
        legal_document_id=row["legal_document_id"],
        event_type=row["event_type"],
        label=row["label"],
        date=row["date"],
        source_reference=row["source_reference"],
        related_entity_id=row["related_entity_id"],
        metadata=_load_object(row["metadata"]),
    )


def _source_version_from_row(row: sqlite3.Row) -> SourceVersion:
    """Convert a SQLite row into a source version model."""

    return SourceVersion(
        id=row["id"],
        entity_geode_id=row["entity_geode_id"],
        version_label=row["version_label"],
        source_url=row["source_url"],
        source_path=row["source_path"],
        content_path=row["content_path"],
        sha256=row["sha256"],
        indexed_at=row["indexed_at"],
    )


class CorpusRepository:
    """Repository for querying and replacing the generated read index."""

    def __init__(self, database_path: Path) -> None:
        """Create a repository rooted at one SQLite database file."""

        self.database_path = database_path

    def replace_index(
        self,
        entities: Iterable[CorpusEntity],
        aliases: Iterable[EntityAlias],
        chunks: Iterable[EntityTextChunk],
        relations: Iterable[EntityRelation],
        timeline_events: Iterable[TimelineEvent],
        source_versions: Iterable[SourceVersion],
        index_run: IndexRun,
    ) -> None:
        """Replace all generated read-index records in one transaction."""

        entity_rows = list(entities)
        alias_rows = list(aliases)
        chunk_rows = list(chunks)
        relation_rows = list(relations)
        timeline_rows = list(timeline_events)
        source_version_rows = list(source_versions)

        with database_connection(self.database_path) as connection:
            with connection:
                connection.execute("DELETE FROM entity_aliases")
                connection.execute("DELETE FROM entity_text_chunks")
                connection.execute("DELETE FROM entity_relations")
                connection.execute("DELETE FROM timeline_events")
                connection.execute("DELETE FROM source_versions")
                connection.execute("DELETE FROM corpus_entities")
                connection.execute("DELETE FROM index_runs")

                connection.executemany(
                    """
                    INSERT INTO corpus_entities (
                        geode_id, entity_type, layer, citation, title, summary, source_url,
                        source_path, content_path, meta_path, sha256, confidence, subject_tags,
                        industry_tags, agency_code, effective_date, publication_year, status,
                        indexed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row.geode_id,
                            row.entity_type,
                            row.layer,
                            row.citation,
                            row.title,
                            row.summary,
                            row.source_url,
                            row.source_path,
                            row.content_path,
                            row.meta_path,
                            row.sha256,
                            row.confidence,
                            _json_list(row.subject_tags),
                            _json_list(row.industry_tags),
                            row.agency_code,
                            row.effective_date,
                            row.publication_year,
                            row.status,
                            row.indexed_at.isoformat(),
                        )
                        for row in entity_rows
                    ],
                )
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO entity_aliases (
                        id, entity_geode_id, alias, alias_type, normalized_alias
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row.id,
                            row.entity_geode_id,
                            row.alias,
                            row.alias_type,
                            row.normalized_alias,
                        )
                        for row in alias_rows
                    ],
                )
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO entity_text_chunks (
                        id, entity_geode_id, chunk_index, heading_path, text, start_char,
                        end_char, sha256, citation_scope
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row.id,
                            row.entity_geode_id,
                            row.chunk_index,
                            _json_list(row.heading_path),
                            row.text,
                            row.start_char,
                            row.end_char,
                            row.sha256,
                            row.citation_scope,
                        )
                        for row in chunk_rows
                    ],
                )
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO entity_relations (
                        id, source_geode_id, source_type, target_geode_id, target_type,
                        relationship, confidence, source_evidence, crosswalk_file
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row.id,
                            row.source_geode_id,
                            row.source_type,
                            row.target_geode_id,
                            row.target_type,
                            row.relationship,
                            row.confidence,
                            row.source_evidence,
                            row.crosswalk_file,
                        )
                        for row in relation_rows
                    ],
                )
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO timeline_events (
                        id, legal_document_id, event_type, label, date, source_reference,
                        related_entity_id, metadata
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row.id,
                            row.legal_document_id,
                            row.event_type,
                            row.label,
                            row.date,
                            row.source_reference,
                            row.related_entity_id,
                            _json_object(row.metadata),
                        )
                        for row in timeline_rows
                    ],
                )
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO source_versions (
                        id, entity_geode_id, version_label, source_url, source_path,
                        content_path, sha256, indexed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row.id,
                            row.entity_geode_id,
                            row.version_label,
                            row.source_url,
                            row.source_path,
                            row.content_path,
                            row.sha256,
                            row.indexed_at.isoformat(),
                        )
                        for row in source_version_rows
                    ],
                )
                connection.execute(
                    """
                    INSERT INTO index_runs (
                        id, started_at, completed_at, root, manifest_sha256, entity_count,
                        alias_count, chunk_count, relation_count, timeline_count, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        index_run.id,
                        index_run.started_at.isoformat(),
                        index_run.completed_at.isoformat(),
                        index_run.root,
                        index_run.manifest_sha256,
                        index_run.entity_count,
                        index_run.alias_count,
                        index_run.chunk_count,
                        index_run.relation_count,
                        index_run.timeline_count,
                        index_run.status,
                    ),
                )

    def get_entity(self, geode_id: str) -> CorpusEntity | None:
        """Return one entity by stable Geode ID."""

        with database_connection(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM corpus_entities WHERE geode_id = ?",
                (geode_id,),
            ).fetchone()
        return _entity_from_row(row) if row else None

    def resolve_entity(self, value: str) -> CorpusEntity | None:
        """Resolve a Geode ID or alias to an entity."""

        direct = self.get_entity(value)
        if direct is not None:
            return direct

        normalized = normalize_alias(value)
        with database_connection(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT e.*
                FROM entity_aliases a
                JOIN corpus_entities e ON e.geode_id = a.entity_geode_id
                WHERE a.normalized_alias = ?
                ORDER BY CASE a.alias_type WHEN 'citation' THEN 0 WHEN 'id' THEN 1 ELSE 2 END
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
        return _entity_from_row(row) if row else None

    def search_entities(self, query: str, limit: int = 20) -> list[SearchResult]:
        """Search indexed legal objects by ID, citation, title, and text chunks."""

        normalized = normalize_alias(query)
        if not normalized:
            return []

        like_value = f"%{normalized}%"
        text_like = f"%{query}%"
        with database_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                WITH chunk_matches AS (
                    SELECT entity_geode_id, MIN(chunk_index) AS first_chunk
                    FROM entity_text_chunks
                    WHERE text LIKE ?
                    GROUP BY entity_geode_id
                )
                SELECT e.*,
                    CASE
                        WHEN a.normalized_alias = ? THEN 'citation matched'
                        WHEN lower(e.title) LIKE lower(?) THEN 'title matched'
                        WHEN c.entity_geode_id IS NOT NULL THEN 'text matched'
                        ELSE 'metadata matched'
                    END AS match_reason
                FROM corpus_entities e
                LEFT JOIN entity_aliases a ON a.entity_geode_id = e.geode_id
                LEFT JOIN chunk_matches c ON c.entity_geode_id = e.geode_id
                WHERE a.normalized_alias = ?
                    OR a.normalized_alias LIKE ?
                    OR lower(e.geode_id) LIKE lower(?)
                    OR lower(e.title) LIKE lower(?)
                    OR c.entity_geode_id IS NOT NULL
                GROUP BY e.geode_id
                ORDER BY
                    CASE
                        WHEN a.normalized_alias = ? THEN 0
                        WHEN lower(e.geode_id) = lower(?) THEN 1
                        WHEN lower(e.title) LIKE lower(?) THEN 2
                        ELSE 3
                    END,
                    e.title
                LIMIT ?
                """,
                (
                    text_like,
                    normalized,
                    text_like,
                    normalized,
                    like_value,
                    text_like,
                    text_like,
                    normalized,
                    query,
                    text_like,
                    limit,
                ),
            ).fetchall()

        return [
            SearchResult(entity=_entity_from_row(row), match_reason=row["match_reason"])
            for row in rows
        ]

    def list_chunks(self, geode_id: str) -> list[EntityTextChunk]:
        """Return text chunks for one legal object in source order."""

        with database_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM entity_text_chunks
                WHERE entity_geode_id = ?
                ORDER BY chunk_index
                """,
                (geode_id,),
            ).fetchall()
        return [_chunk_from_row(row) for row in rows]

    def list_relations(self, geode_id: str) -> list[EntityRelation]:
        """Return inbound and outbound relations for one legal object."""

        with database_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM entity_relations
                WHERE source_geode_id = ? OR target_geode_id = ?
                ORDER BY relationship, target_geode_id
                """,
                (geode_id, geode_id),
            ).fetchall()
        return [_relation_from_row(row) for row in rows]

    def list_timeline_events(self, geode_id: str) -> list[TimelineEvent]:
        """Return timeline events for one legal object."""

        with database_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM timeline_events
                WHERE legal_document_id = ? OR related_entity_id = ?
                ORDER BY date, id
                """,
                (geode_id, geode_id),
            ).fetchall()
        return [_timeline_from_row(row) for row in rows]

    def list_source_versions(self, geode_id: str) -> list[SourceVersion]:
        """Return source fingerprints for one legal object."""

        with database_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM source_versions
                WHERE entity_geode_id = ?
                ORDER BY version_label, id
                """,
                (geode_id,),
            ).fetchall()
        return [_source_version_from_row(row) for row in rows]

    def latest_index_run(self) -> IndexRun | None:
        """Return the latest index run audit row."""

        with database_connection(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM index_runs ORDER BY completed_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return IndexRun(
            id=row["id"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            root=row["root"],
            manifest_sha256=row["manifest_sha256"],
            entity_count=row["entity_count"],
            alias_count=row["alias_count"],
            chunk_count=row["chunk_count"],
            relation_count=row["relation_count"],
            timeline_count=row["timeline_count"],
            status=row["status"],
        )
