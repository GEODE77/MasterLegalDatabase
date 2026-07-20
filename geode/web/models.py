"""Validated read-side models for the Geode Commons corpus index."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WebReadModel(BaseModel):
    """Base model for derived, rebuildable web index records."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CorpusEntity(WebReadModel):
    """Searchable legal object derived from the canonical Geode file corpus."""

    geode_id: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    citation: str | None = None
    title: str = Field(min_length=1)
    summary: str | None = None
    source_url: str | None = None
    source_path: str | None = None
    content_path: str | None = None
    meta_path: str | None = None
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    subject_tags: list[str] = Field(default_factory=list)
    industry_tags: list[str] = Field(default_factory=list)
    agency_code: str | None = None
    effective_date: str | None = None
    publication_year: int | None = None
    status: str | None = None
    indexed_at: datetime


class EntityAlias(WebReadModel):
    """Alternative citation, title, or identifier that resolves to a Geode entity."""

    id: str = Field(min_length=1)
    entity_geode_id: str = Field(min_length=1)
    alias: str = Field(min_length=1)
    alias_type: str = Field(min_length=1)
    normalized_alias: str = Field(min_length=1)


class EntityTextChunk(WebReadModel):
    """Searchable passage chunk derived from canonical legal text."""

    id: str = Field(min_length=1)
    entity_geode_id: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    heading_path: list[str] = Field(default_factory=list)
    text: str = Field(min_length=1)
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    citation_scope: str | None = None


class EntityRelation(WebReadModel):
    """Relationship between canonical Geode entities derived from crosswalk files."""

    id: str = Field(min_length=1)
    source_geode_id: str = Field(min_length=1)
    source_type: str | None = None
    target_geode_id: str = Field(min_length=1)
    target_type: str | None = None
    relationship: str = Field(min_length=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_evidence: str | None = None
    crosswalk_file: str | None = None


class TimelineEvent(WebReadModel):
    """Chronological event connected to a legal object."""

    id: str = Field(min_length=1)
    legal_document_id: str | None = None
    event_type: str = Field(min_length=1)
    label: str = Field(min_length=1)
    date: str = Field(min_length=1)
    source_reference: str | None = None
    related_entity_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceVersion(WebReadModel):
    """Source fingerprint for an indexed legal object version."""

    id: str = Field(min_length=1)
    entity_geode_id: str = Field(min_length=1)
    version_label: str = Field(min_length=1)
    source_url: str | None = None
    source_path: str | None = None
    content_path: str | None = None
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    indexed_at: datetime


class IndexRun(WebReadModel):
    """Audit record for one derived index build."""

    id: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    root: str = Field(min_length=1)
    manifest_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    entity_count: int = Field(ge=0)
    alias_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    relation_count: int = Field(ge=0)
    timeline_count: int = Field(ge=0)
    status: str = Field(min_length=1)


class SearchResult(WebReadModel):
    """API response row for a corpus search hit."""

    entity: CorpusEntity
    match_reason: str
