"""Schemas for county, municipal, and special-district authority."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, HttpUrl, field_validator, model_validator

from geode.schemas.models import ConfidenceScores, GeodeModel
from geode.schemas.validators import require_official_source_url, require_utc_datetime


LocalAuthorityLevel = Literal["county", "municipal", "district"]
DistrictFamily = Literal[
    "school",
    "water_sanitation",
    "fire",
    "metropolitan",
    "library",
    "hospital",
    "transit",
    "other",
]


class CountyGapRecord(GeodeModel):
    """Evidence record for a county/category source disposition."""

    entity_type: Literal["county_gap"] = "county_gap"
    gap_id: str = Field(pattern=r"^GAP-CO-COUNTY-[A-Z0-9_-]+-[a-z0-9_]+$")
    authority_id: str = Field(pattern=r"^CO-COUNTY-[A-Z0-9_-]+$")
    authority_level: Literal["county"] = "county"
    county_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    disposition: Literal[
        "source_identified_not_attempted",
        "download_failed",
        "official_source_not_identified",
        "official_discovery_page_access_blocked",
    ]
    official_discovery_url: HttpUrl | None = None
    official_discovery_status: Literal["downloaded", "blocked", "not_attempted"]
    official_discovery_raw_path: str | None = None
    official_discovery_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    candidate_source_ids: list[str] = Field(default_factory=list)
    attempted_source_ids: list[str] = Field(default_factory=list)
    failed_source_ids: list[str] = Field(default_factory=list)
    evidence_message: str = ""
    reason: str = Field(min_length=1)
    audited_at: datetime

    @field_validator("official_discovery_url")
    @classmethod
    def validate_discovery_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Require official URLs when a discovery URL is supplied."""

        if value is not None:
            require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("audited_at")
    @classmethod
    def validate_audit_time(cls, value: datetime) -> datetime:
        """Require a timezone-aware audit timestamp."""

        return require_utc_datetime(value)


class LocalAuthority(GeodeModel):
    """Identity record for one Colorado local governing authority."""

    entity_type: Literal["local_authority"] = "local_authority"
    id: str = Field(pattern=r"^CO-(COUNTY|MUNICIPAL|DISTRICT)-[A-Z0-9_-]+$")
    authority_level: LocalAuthorityLevel
    authority_type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    state: Literal["CO"] = "CO"
    county_names: list[str] = Field(default_factory=list)
    district_family: DistrictFamily | None = None
    official_url: HttpUrl
    source_url: HttpUrl
    boundary_description: str | None = None
    active: bool = True
    data_retrieved: date
    confidence: ConfidenceScores

    @field_validator("official_url", "source_url")
    @classmethod
    def validate_source_urls(cls, value: HttpUrl) -> HttpUrl:
        """Require official government or authority source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value


class LocalRule(GeodeModel):
    """One AI-ready county, municipal, or district rule or policy."""

    entity_type: Literal["local_rule"] = "local_rule"
    id: str = Field(pattern=r"^LOCAL-RULE-[A-Z0-9_-]+$")
    authority_id: str = Field(pattern=r"^CO-(COUNTY|MUNICIPAL|DISTRICT)-[A-Z0-9_-]+$")
    authority_level: LocalAuthorityLevel
    authority_type: str = Field(min_length=1)
    authority_name: str = Field(min_length=1)
    district_family: DistrictFamily | None = None
    county_names: list[str] = Field(default_factory=list)
    citation: str = Field(min_length=1)
    title: str = Field(min_length=1)
    section_heading: str | None = None
    full_text: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    rule_unit_ids: list[str] = Field(default_factory=list)
    state_authority_ids: list[str] = Field(default_factory=list)
    source_citation_pages: dict[str, list[int]] = Field(default_factory=dict)
    source_category: str | None = None
    source_format: str | None = None
    provenance_status: Literal["exact", "section", "document"] = "document"
    semantic_status: Literal["semantic_ready", "source_preservation_only", "needs_review"] = (
        "source_preservation_only"
    )
    effective_date: date | None = None
    repeal_date: date | None = None
    status: Literal["active", "repealed", "superseded", "unknown"] = "unknown"
    applies_to: list[str] = Field(default_factory=list)
    geographic_scope: list[str] = Field(default_factory=list)
    source_url: HttpUrl
    source_path: str = Field(min_length=1)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_version: str = Field(min_length=1)
    source_section: str | None = None
    source_page: int | None = Field(default=None, ge=1)
    source_page_end: int | None = Field(default=None, ge=1)
    source_line_start: int | None = Field(default=None, ge=1)
    source_line_end: int | None = Field(default=None, ge=1)
    data_retrieved: datetime
    confidence: ConfidenceScores

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require an official source URL."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("data_retrieved")
    @classmethod
    def validate_retrieval_time(cls, value: datetime) -> datetime:
        """Require a timezone-aware retrieval timestamp."""

        return require_utc_datetime(value)

    @model_validator(mode="after")
    def validate_provenance_range(self) -> "LocalRule":
        """Ensure exact line and page ranges do not run backward."""

        if self.source_page and self.source_page_end and self.source_page_end < self.source_page:
            raise ValueError("source_page_end cannot precede source_page")
        if self.source_line_start and self.source_line_end and self.source_line_end < self.source_line_start:
            raise ValueError("source_line_end cannot precede source_line_start")
        return self
