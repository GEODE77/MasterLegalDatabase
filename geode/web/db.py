"""SQLite repository for the Geode read index."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CorpusEntity:
    """One indexed Geode entity."""

    geode_id: str
    layer: str
    entity_type: str
    title: str
    citation: str | None
    path: str
    source_url: str
    publication_year: int | None
    sha256: str
    confidence: float


@dataclass(frozen=True)
class SearchResult:
    """One entity search hit."""

    entity: CorpusEntity
    match_reason: str


@dataclass(frozen=True)
class CorpusChunk:
    """Searchable text chunk for one entity."""

    geode_id: str
    chunk_index: int
    text: str
    path: str


@dataclass(frozen=True)
class CorpusRelation:
    """Relationship between two Geode entities."""

    source_geode_id: str
    target_geode_id: str
    relationship: str
    confidence: float
    evidence: str | None


@dataclass(frozen=True)
class TimelineEvent:
    """Timeline event connected to a Geode entity."""

    event_id: str
    event_date: str
    event_type: str
    entity_id: str
    description: str
    file_path: str | None


@dataclass(frozen=True)
class SourceVersion:
    """Source-version row for an indexed entity."""

    geode_id: str
    version_label: str
    path: str
    sha256: str


@dataclass(frozen=True)
class IndexRun:
    """Summary of the latest index build."""

    entity_count: int
    alias_count: int
    chunk_count: int
    relation_count: int
    timeline_count: int


class CorpusRepository:
    """Read-only repository for a built Geode SQLite index."""

    def __init__(self, database_path: Path) -> None:
        """Open a repository against a SQLite database path."""

        self.database_path = database_path

    def resolve_entity(self, value: str) -> CorpusEntity | None:
        """Resolve an ID, citation, or alias to a corpus entity."""

        normalized = _normalize_alias(value)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT e.*
                FROM aliases a
                JOIN entities e ON e.geode_id = a.geode_id
                WHERE a.alias = ?
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT * FROM entities WHERE geode_id = ? LIMIT 1",
                    (value,),
                ).fetchone()
            return _entity_from_row(row) if row is not None else None

    def search_entities(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search indexed entities by alias, title, citation, and text."""

        terms = [term for term in _normalize_alias(query).split() if term]
        if not terms:
            return []
        results: list[SearchResult] = []
        seen: set[str] = set()
        entity = self.resolve_entity(query)
        if entity is not None:
            results.append(SearchResult(entity=entity, match_reason="alias matched"))
            seen.add(entity.geode_id)

        with self._connect() as connection:
            for row in connection.execute("SELECT * FROM entities ORDER BY geode_id"):
                candidate = _entity_from_row(row)
                haystack = _normalize_alias(
                    " ".join(
                        value or ""
                        for value in [candidate.title, candidate.citation, candidate.geode_id]
                    )
                )
                if candidate.geode_id not in seen and all(term in haystack for term in terms):
                    results.append(SearchResult(candidate, "metadata matched"))
                    seen.add(candidate.geode_id)
                    if len(results) >= limit:
                        return results

            for row in connection.execute(
                """
                SELECT e.*
                FROM chunks c
                JOIN entities e ON e.geode_id = c.geode_id
                WHERE c.normalized_text LIKE ?
                ORDER BY e.geode_id, c.chunk_index
                """,
                (f"%{'%'.join(terms)}%",),
            ):
                candidate = _entity_from_row(row)
                if candidate.geode_id in seen:
                    continue
                results.append(SearchResult(candidate, "text matched"))
                seen.add(candidate.geode_id)
                if len(results) >= limit:
                    return results
        return results

    def list_chunks(self, geode_id: str) -> list[CorpusChunk]:
        """Return searchable chunks for one entity."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT geode_id, chunk_index, text, path
                FROM chunks
                WHERE geode_id = ?
                ORDER BY chunk_index
                """,
                (geode_id,),
            ).fetchall()
        return [
            CorpusChunk(
                geode_id=row["geode_id"],
                chunk_index=row["chunk_index"],
                text=row["text"],
                path=row["path"],
            )
            for row in rows
        ]

    def list_relations(self, geode_id: str) -> list[CorpusRelation]:
        """Return relationships connected to one entity."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source_geode_id, target_geode_id, relationship, confidence, evidence
                FROM relations
                WHERE source_geode_id = ? OR target_geode_id = ?
                ORDER BY source_geode_id, target_geode_id, relationship
                """,
                (geode_id, geode_id),
            ).fetchall()
        return [
            CorpusRelation(
                source_geode_id=row["source_geode_id"],
                target_geode_id=row["target_geode_id"],
                relationship=row["relationship"],
                confidence=row["confidence"],
                evidence=row["evidence"],
            )
            for row in rows
        ]

    def list_timeline_events(self, geode_id: str) -> list[TimelineEvent]:
        """Return timeline events connected to one entity."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, event_date, event_type, entity_id, description, file_path
                FROM timeline_events
                WHERE entity_id = ?
                ORDER BY event_date, event_id
                """,
                (geode_id,),
            ).fetchall()
        return [
            TimelineEvent(
                event_id=row["event_id"],
                event_date=row["event_date"],
                event_type=row["event_type"],
                entity_id=row["entity_id"],
                description=row["description"],
                file_path=row["file_path"],
            )
            for row in rows
        ]

    def list_source_versions(self, geode_id: str) -> list[SourceVersion]:
        """Return source versions known for one entity."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT geode_id, version_label, path, sha256
                FROM source_versions
                WHERE geode_id = ?
                ORDER BY version_label
                """,
                (geode_id,),
            ).fetchall()
        return [
            SourceVersion(
                geode_id=row["geode_id"],
                version_label=row["version_label"],
                path=row["path"],
                sha256=row["sha256"],
            )
            for row in rows
        ]

    def latest_index_run(self) -> IndexRun | None:
        """Return the latest index-run summary."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT entity_count, alias_count, chunk_count, relation_count, timeline_count
                FROM index_runs
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return IndexRun(
            entity_count=row["entity_count"],
            alias_count=row["alias_count"],
            chunk_count=row["chunk_count"],
            relation_count=row["relation_count"],
            timeline_count=row["timeline_count"],
        )

    def _connect(self) -> sqlite3.Connection:
        """Open a row-enabled SQLite connection."""

        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def _entity_from_row(row: sqlite3.Row) -> CorpusEntity:
    """Build an entity dataclass from a SQLite row."""

    return CorpusEntity(
        geode_id=row["geode_id"],
        layer=row["layer"],
        entity_type=row["entity_type"],
        title=row["title"],
        citation=row["citation"],
        path=row["path"],
        source_url=row["source_url"],
        publication_year=row["publication_year"],
        sha256=row["sha256"],
        confidence=row["confidence"],
    )


def _normalize_alias(value: str) -> str:
    """Normalize a lookup string for forgiving exact matching."""

    return " ".join(
        value.casefold()
        .replace(".", " ")
        .replace(",", " ")
        .replace("-", " ")
        .replace("_", " ")
        .split()
    )
