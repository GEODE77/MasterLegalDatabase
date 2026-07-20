"""Build the derived Geode Commons corpus read index."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from geode.constants import ALL_LAYERS, CONTROL_PLANE_DIR
from geode.utils.file_io import ensure_not_raw_archive, iter_jsonl, relative_path
from geode.utils.hashing import sha256_file, sha256_text
from geode.web.config import default_database_path
from geode.web.db import CorpusRepository, normalize_alias
from geode.web.models import (
    CorpusEntity,
    EntityAlias,
    EntityRelation,
    EntityTextChunk,
    IndexRun,
    SourceVersion,
    TimelineEvent,
)


LAYER_ENTITY_TYPES = {
    "01_Statutes_CRS": "statute_section",
    "02_Regulations_CCR": "regulation_rule",
    "03_Legislation": "bill",
    "04_Rulemaking": "rulemaking_notice",
    "05_Executive_Orders": "executive_order",
    "06_Session_Laws": "session_law",
    "07_Supplementary": "supplementary_document",
}

ENTITY_ID_FIELDS = ("geode_id", "entity_id", "id", "document_id", "canonical_id")
TITLE_FIELDS = (
    "title",
    "section_heading",
    "heading",
    "name",
    "description",
    "short_title",
    "label",
)
CONTENT_PATH_FIELDS = ("content_path", "file_path", "markdown_path", "path", "output_path")

STABLE_ID_NAMESPACE = uuid.UUID("17f1f775-3864-4bf7-86ef-54030e64a02d")


@dataclass(frozen=True)
class IndexBuildResult:
    """Summary of a derived corpus index build."""

    database_path: Path
    entity_count: int
    alias_count: int
    chunk_count: int
    relation_count: int
    timeline_count: int


def build_index(
    root: Path,
    database_path: Path | None = None,
    rebuild: bool = False,
    incremental: bool = False,
) -> IndexBuildResult:
    """Build or rebuild the read-only corpus index from Geode source files.

    Args:
        root: Project Geode repository root.
        database_path: Optional generated SQLite database path.
        rebuild: Remove the prior generated database before indexing.
        incremental: Reserved for future affected-entity updates. Currently this
            uses the same idempotent replacement path as a rebuild.

    Returns:
        Counts for records written into the derived read index.
    """

    del incremental

    project_root = root.resolve()
    db_path = (database_path or default_database_path(project_root)).resolve()
    ensure_not_raw_archive(db_path, project_root)
    if rebuild and db_path.exists():
        db_path.unlink()

    started_at = _utc_now()
    manifest_path = project_root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    manifest_sha = sha256_file(manifest_path) if manifest_path.exists() else None

    entities = _collect_entities(project_root, started_at)
    chunks = _collect_chunks(project_root, entities)
    aliases = _collect_aliases(entities)
    source_versions = _collect_source_versions(entities)
    relations = list(_iter_crosswalk_relations(project_root))
    timeline_events = list(_iter_timeline_events(project_root))

    completed_at = _utc_now()
    index_run = IndexRun(
        id=_stable_id("index-run", project_root.as_posix(), manifest_sha or "missing"),
        started_at=started_at,
        completed_at=completed_at,
        root=project_root.as_posix(),
        manifest_sha256=manifest_sha,
        entity_count=len(entities),
        alias_count=len(aliases),
        chunk_count=len(chunks),
        relation_count=len(relations),
        timeline_count=len(timeline_events),
        status="completed",
    )

    repository = CorpusRepository(db_path)
    repository.replace_index(
        entities=entities.values(),
        aliases=aliases,
        chunks=chunks,
        relations=relations,
        timeline_events=timeline_events,
        source_versions=source_versions,
        index_run=index_run,
    )

    return IndexBuildResult(
        database_path=db_path,
        entity_count=len(entities),
        alias_count=len(aliases),
        chunk_count=len(chunks),
        relation_count=len(relations),
        timeline_count=len(timeline_events),
    )


def main(argv: list[str] | None = None) -> int:
    """Run the corpus indexer CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project Geode root.")
    parser.add_argument("--database", type=Path, default=None, help="SQLite index path.")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild generated index data.")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Index incrementally where supported. Currently equivalent to replacement.",
    )
    args = parser.parse_args(argv)

    result = build_index(
        root=args.root,
        database_path=args.database,
        rebuild=args.rebuild,
        incremental=args.incremental,
    )
    sys.stdout.write(
        json.dumps(
            {
                "database_path": result.database_path.as_posix(),
                "entity_count": result.entity_count,
                "alias_count": result.alias_count,
                "chunk_count": result.chunk_count,
                "relation_count": result.relation_count,
                "timeline_count": result.timeline_count,
            },
            indent=2,
        )
        + "\n"
    )
    return 0


def _collect_entities(root: Path, indexed_at: datetime) -> dict[str, CorpusEntity]:
    """Collect entities from layer indexes, metadata sidecars, and Markdown files."""

    entities: dict[str, CorpusEntity] = {}
    for layer in ALL_LAYERS:
        layer_path = root / layer
        if not layer_path.exists():
            continue

        index_path = layer_path / "_index.jsonl"
        if index_path.exists():
            for row in _iter_jsonl_if_nonempty(index_path):
                entity = _entity_from_row(row, layer, root, index_path, indexed_at)
                if entity is not None:
                    entities[entity.geode_id] = entity

        meta_dir = layer_path / "_meta"
        if meta_dir.exists():
            for meta_path in sorted(meta_dir.glob("*.jsonl")):
                for row in _iter_jsonl_if_nonempty(meta_path):
                    entity = _entity_from_row(row, layer, root, meta_path, indexed_at)
                    if entity is not None:
                        prior = entities.get(entity.geode_id)
                        entities[entity.geode_id] = _merge_entity(prior, entity)

        for markdown_path in sorted(layer_path.glob("*.md")):
            entity = _entity_from_markdown(markdown_path, layer, root, indexed_at)
            if entity.geode_id not in entities:
                entities[entity.geode_id] = entity

    return entities


def _entity_from_row(
    row: dict[str, Any],
    layer: str,
    root: Path,
    row_path: Path,
    indexed_at: datetime,
) -> CorpusEntity | None:
    """Create one entity model from an index or metadata row."""

    geode_id = _first_string(row, ENTITY_ID_FIELDS)
    content_path = _resolve_content_path(row, root)
    if geode_id is None and content_path is not None:
        geode_id = _entity_id_from_path(content_path)
    if geode_id is None:
        return None

    title = _first_string(row, TITLE_FIELDS) or row.get("citation") or geode_id
    source_path = _optional_relative(row_path, root)
    sha_source = content_path if content_path and content_path.exists() else row_path
    sha = sha256_file(sha_source) if sha_source.exists() else sha256_text(json.dumps(row))
    confidence = _confidence_value(row.get("confidence"))
    subject_tags = _string_list(row.get("subject_tags"))
    industry_tags = _string_list(row.get("industry_tags"))

    return CorpusEntity(
        geode_id=geode_id,
        entity_type=str(row.get("entity_type") or LAYER_ENTITY_TYPES.get(layer, "legal_document")),
        layer=layer,
        citation=_string_or_none(row.get("citation") or row.get("citation_text")),
        title=str(title),
        summary=_string_or_none(row.get("summary") or row.get("description")),
        source_url=_string_or_none(row.get("source_url")),
        source_path=source_path,
        content_path=_optional_relative(content_path, root) if content_path else None,
        meta_path=source_path if "_meta" in row_path.parts else _string_or_none(row.get("meta_path")),
        sha256=sha,
        confidence=confidence,
        subject_tags=subject_tags,
        industry_tags=industry_tags,
        agency_code=_string_or_none(row.get("agency_code") or row.get("agency")),
        effective_date=_string_or_none(row.get("effective_date")),
        publication_year=_int_or_none(row.get("publication_year") or row.get("year")),
        status=_string_or_none(row.get("status")),
        indexed_at=indexed_at,
    )


def _entity_from_markdown(
    markdown_path: Path,
    layer: str,
    root: Path,
    indexed_at: datetime,
) -> CorpusEntity:
    """Create an entity model from a Markdown legal text file."""

    text = markdown_path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(text)
    geode_id = (
        _first_string(frontmatter, ENTITY_ID_FIELDS)
        or _string_or_none(frontmatter.get("citation"))
        or _entity_id_from_path(markdown_path)
    )
    heading = _first_markdown_heading(text)
    title = _first_string(frontmatter, TITLE_FIELDS) or heading or geode_id

    return CorpusEntity(
        geode_id=geode_id,
        entity_type=str(frontmatter.get("entity_type") or LAYER_ENTITY_TYPES.get(layer, "legal_document")),
        layer=layer,
        citation=_string_or_none(frontmatter.get("citation")),
        title=title,
        summary=_string_or_none(frontmatter.get("summary")),
        source_url=_string_or_none(frontmatter.get("source_url")),
        source_path=relative_path(markdown_path, root),
        content_path=relative_path(markdown_path, root),
        meta_path=None,
        sha256=sha256_file(markdown_path),
        confidence=_confidence_value(frontmatter.get("confidence")),
        subject_tags=_string_list(frontmatter.get("subject_tags")),
        industry_tags=_string_list(frontmatter.get("industry_tags")),
        agency_code=_string_or_none(frontmatter.get("agency_code")),
        effective_date=_string_or_none(frontmatter.get("effective_date")),
        publication_year=_int_or_none(frontmatter.get("publication_year")),
        status=_string_or_none(frontmatter.get("status")),
        indexed_at=indexed_at,
    )


def _merge_entity(prior: CorpusEntity | None, incoming: CorpusEntity) -> CorpusEntity:
    """Merge sparse sidecar metadata into an entity record without losing paths."""

    if prior is None:
        return incoming
    return prior.model_copy(
        update={
            "citation": prior.citation or incoming.citation,
            "summary": prior.summary or incoming.summary,
            "source_url": prior.source_url or incoming.source_url,
            "meta_path": prior.meta_path or incoming.meta_path,
            "confidence": max(prior.confidence, incoming.confidence),
            "subject_tags": sorted({*prior.subject_tags, *incoming.subject_tags}),
            "industry_tags": sorted({*prior.industry_tags, *incoming.industry_tags}),
            "agency_code": prior.agency_code or incoming.agency_code,
            "effective_date": prior.effective_date or incoming.effective_date,
            "publication_year": prior.publication_year or incoming.publication_year,
            "status": prior.status or incoming.status,
        }
    )


def _collect_aliases(entities: dict[str, CorpusEntity]) -> list[EntityAlias]:
    """Create deterministic lookup aliases for indexed entities."""

    aliases: dict[str, EntityAlias] = {}
    for entity in entities.values():
        for alias_type, alias_value in (
            ("id", entity.geode_id),
            ("title", entity.title),
            ("citation", entity.citation),
        ):
            if not alias_value:
                continue
            normalized = normalize_alias(alias_value)
            if not normalized:
                continue
            alias_id = _stable_id("alias", entity.geode_id, alias_type, normalized)
            aliases[alias_id] = EntityAlias(
                id=alias_id,
                entity_geode_id=entity.geode_id,
                alias=alias_value,
                alias_type=alias_type,
                normalized_alias=normalized,
            )
    return sorted(aliases.values(), key=lambda item: item.id)


def _collect_chunks(root: Path, entities: dict[str, CorpusEntity]) -> list[EntityTextChunk]:
    """Build text chunks for Markdown-backed entities."""

    chunks: list[EntityTextChunk] = []
    for entity in sorted(entities.values(), key=lambda item: item.geode_id):
        if entity.content_path is None:
            continue
        content_path = root / entity.content_path
        if not content_path.exists() or content_path.suffix.lower() not in {".md", ".txt"}:
            continue
        text = content_path.read_text(encoding="utf-8")
        for chunk_index, heading_path, chunk_text, start, end in _split_markdown_chunks(text):
            chunk_sha = sha256_text(chunk_text)
            chunks.append(
                EntityTextChunk(
                    id=_stable_id("chunk", entity.geode_id, str(chunk_index), chunk_sha),
                    entity_geode_id=entity.geode_id,
                    chunk_index=chunk_index,
                    heading_path=heading_path,
                    text=chunk_text,
                    start_char=start,
                    end_char=end,
                    sha256=chunk_sha,
                    citation_scope=entity.citation or entity.geode_id,
                )
            )
    return chunks


def _collect_source_versions(entities: dict[str, CorpusEntity]) -> list[SourceVersion]:
    """Create source fingerprint rows for indexed legal objects."""

    versions: list[SourceVersion] = []
    for entity in sorted(entities.values(), key=lambda item: item.geode_id):
        version_label = entity.status or entity.effective_date or "indexed"
        versions.append(
            SourceVersion(
                id=_stable_id("source-version", entity.geode_id, entity.sha256),
                entity_geode_id=entity.geode_id,
                version_label=version_label,
                source_url=entity.source_url,
                source_path=entity.source_path,
                content_path=entity.content_path,
                sha256=entity.sha256,
                indexed_at=entity.indexed_at,
            )
        )
    return versions


def _split_markdown_chunks(text: str) -> Iterator[tuple[int, list[str], str, int, int]]:
    """Split Markdown into stable heading-oriented chunks."""

    body_start = 0
    if text.startswith("---"):
        close = text.find("\n---", 3)
        if close != -1:
            newline_after = text.find("\n", close + len("\n---"))
            body_start = len(text) if newline_after == -1 else newline_after + 1

    heading_stack: list[str] = []
    current_lines: list[str] = []
    current_start = body_start
    chunk_index = 0
    offset = 0
    for line in text.splitlines(keepends=True):
        next_offset = offset + len(line)
        if offset < body_start:
            offset = next_offset
            continue
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading and current_lines:
            chunk_text = "".join(current_lines).strip()
            if _has_non_heading_text(chunk_text):
                yield chunk_index, heading_stack.copy(), chunk_text, current_start, offset
                chunk_index += 1
            current_lines = []
            current_start = offset

        if heading:
            level = len(heading.group(1))
            label = heading.group(2).strip()
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(label)
        if not current_lines:
            current_start = offset
        current_lines.append(line)
        offset = next_offset

    chunk_text = "".join(current_lines).strip()
    if _has_non_heading_text(chunk_text):
        yield chunk_index, heading_stack.copy(), chunk_text, current_start, len(text)


def _has_non_heading_text(value: str) -> bool:
    """Return true when a Markdown chunk has text beyond heading labels."""

    for line in value.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return True
    return False


def _iter_crosswalk_relations(root: Path) -> Iterator[EntityRelation]:
    """Yield relation rows from all JSONL files in `_CROSSWALKS`."""

    crosswalk_dir = root / "_CROSSWALKS"
    if not crosswalk_dir.exists():
        return
    for path in sorted(crosswalk_dir.glob("*.jsonl")):
        for row in _iter_jsonl_if_nonempty(path):
            yield from _relations_from_crosswalk_row(row, path, root)


def _relations_from_crosswalk_row(
    row: dict[str, Any],
    path: Path,
    root: Path,
) -> Iterator[EntityRelation]:
    """Normalize supported crosswalk row shapes into relation records."""

    source_id = _string_or_none(row.get("source_id") or row.get("entity_id"))
    source_type = _string_or_none(row.get("source_type") or row.get("entity_type"))
    confidence = _confidence_value(row.get("confidence"))
    source_evidence = _string_or_none(row.get("source_evidence") or row.get("evidence"))
    crosswalk_file = relative_path(path, root)

    if source_id is None:
        return

    target_id = _string_or_none(row.get("target_id"))
    if target_id:
        relationship = str(row.get("relationship") or path.stem)
        yield _relation(
            source_id,
            source_type,
            target_id,
            _string_or_none(row.get("target_type")),
            relationship,
            confidence,
            source_evidence,
            crosswalk_file,
        )

    for target in _string_list(row.get("target_ids")):
        yield _relation(
            source_id,
            source_type,
            target,
            _string_or_none(row.get("target_type")),
            str(row.get("relationship") or path.stem),
            confidence,
            source_evidence,
            crosswalk_file,
        )

    for field, relationship in (
        ("statutes_amended", "amends"),
        ("statutes_created", "creates"),
        ("statutes_repealed", "repeals"),
        ("enabling_statutes", "enabled_by"),
        ("regulations_issued", "issues"),
    ):
        for target in _string_list(row.get(field)):
            yield _relation(
                source_id,
                source_type,
                target,
                _target_type_for_field(field),
                relationship,
                confidence,
                source_evidence,
                crosswalk_file,
            )


def _relation(
    source_id: str,
    source_type: str | None,
    target_id: str,
    target_type: str | None,
    relationship: str,
    confidence: float,
    source_evidence: str | None,
    crosswalk_file: str,
) -> EntityRelation:
    """Create a deterministic entity relation."""

    relation_id = _stable_id(
        "relation",
        source_id,
        target_id,
        relationship,
        crosswalk_file,
        source_evidence or "",
    )
    return EntityRelation(
        id=relation_id,
        source_geode_id=source_id,
        source_type=source_type,
        target_geode_id=target_id,
        target_type=target_type,
        relationship=relationship,
        confidence=confidence,
        source_evidence=source_evidence,
        crosswalk_file=crosswalk_file,
    )


def _iter_timeline_events(root: Path) -> Iterator[TimelineEvent]:
    """Yield timeline events from the control-plane timeline index."""

    path = root / CONTROL_PLANE_DIR / "MASTER_TIMELINE_INDEX.jsonl"
    if not path.exists():
        return
    for row in _iter_jsonl_if_nonempty(path):
        event_id = _string_or_none(row.get("id"))
        date = _string_or_none(row.get("date"))
        event_type = _string_or_none(row.get("event_type"))
        if not event_id or not date or not event_type:
            continue
        entity_id = _string_or_none(row.get("entity_id") or row.get("legal_document_id"))
        yield TimelineEvent(
            id=event_id,
            legal_document_id=entity_id,
            event_type=event_type,
            label=str(row.get("label") or row.get("description") or event_type),
            date=date,
            source_reference=_string_or_none(row.get("source_reference") or row.get("file_path")),
            related_entity_id=_string_or_none(row.get("related_entity_id")),
            metadata={key: value for key, value in row.items() if key not in {"id"}},
        )


def _iter_jsonl_if_nonempty(path: Path) -> Iterator[dict[str, Any]]:
    """Read JSONL records and treat empty files as empty iterators."""

    if not path.exists() or path.stat().st_size == 0:
        return iter(())
    return iter_jsonl(path)


def _resolve_content_path(row: dict[str, Any], root: Path) -> Path | None:
    """Resolve the first path-like content field from a row."""

    value = _first_string(row, CONTENT_PATH_FIELDS)
    if value is None:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def _optional_relative(path: Path | None, root: Path) -> str | None:
    """Return a project-relative path when a path is available."""

    if path is None:
        return None
    try:
        return relative_path(path, root)
    except ValueError:
        return path.as_posix()


def _entity_id_from_path(path: Path) -> str:
    """Derive a stable fallback entity ID from a content path."""

    return path.stem.replace(" ", "_")


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse simple YAML frontmatter key-value pairs without external dependencies."""

    if not text.startswith("---"):
        return {}
    close = text.find("\n---", 3)
    if close == -1:
        return {}
    payload: dict[str, Any] = {}
    for line in text[3:close].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        stripped = value.strip().strip('"').strip("'")
        if stripped:
            payload[key.strip()] = stripped
    return payload


def _first_markdown_heading(text: str) -> str | None:
    """Return the first Markdown heading label in a text file."""

    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return None


def _first_string(row: dict[str, Any], fields: Iterable[str]) -> str | None:
    """Return the first non-empty string-like value for a set of field names."""

    for field in fields:
        value = _string_or_none(row.get(field))
        if value:
            return value
    return None


def _string_or_none(value: Any) -> str | None:
    """Return a string value or `None` for empty values."""

    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, int | float):
        return str(value)
    return None


def _string_list(value: Any) -> list[str]:
    """Normalize a scalar or list value into a list of strings."""

    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list | tuple | set):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _int_or_none(value: Any) -> int | None:
    """Return an integer or `None` from a loose JSON field value."""

    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _confidence_value(value: Any) -> float:
    """Normalize confidence values from scalar or object-shaped records."""

    if isinstance(value, dict):
        value = value.get("overall")
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return min(1.0, max(0.0, confidence))


def _target_type_for_field(field: str) -> str:
    """Infer a target entity type for common crosswalk list fields."""

    if "statute" in field:
        return "statute_section"
    if "regulation" in field:
        return "regulation_rule"
    return "legal_document"


def _stable_id(*parts: str) -> str:
    """Return a deterministic UUID for a generated read-index record."""

    return str(uuid.uuid5(STABLE_ID_NAMESPACE, "::".join(parts)))


def _utc_now() -> datetime:
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc)


if __name__ == "__main__":
    raise SystemExit(main())
