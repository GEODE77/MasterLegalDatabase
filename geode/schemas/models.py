"""Pydantic models for the Project Geode corpus and control plane."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationInfo,
    field_validator,
    model_validator,
)

from geode.constants import ALL_LAYERS
from geode.schemas.ontology import (
    COMPLIANCE_KEYWORDS,
    EVENT_TYPES,
    INDUSTRY_TAGS,
    RELATIONSHIP_TYPES,
    RULE_TYPES,
    STATUS_VALUES,
    SUBJECT_TAGS,
    require_known_values,
)
from geode.schemas.validators import (
    canonical_crs_id,
    normalize_crs_number,
    require_not_future_date,
    require_official_source_url,
    require_utc_datetime,
)

LayerName = Literal[
    "01_Statutes_CRS",
    "02_Regulations_CCR",
    "03_Legislation",
    "04_Rulemaking",
    "05_Executive_Orders",
    "06_Session_Laws",
    "07_Supplementary",
    "08_County_Authorities",
    "09_District_Authorities",
    "10_Municipal_Authorities",
]

EntityType = Literal[
    "statute_section",
    "regulation_rule",
    "bill",
    "rulemaking_notice",
    "executive_order",
    "session_law",
    "ag_opinion",
    "coprrr_review",
    "federal_standard",
    "rule_unit",
    "crosswalk_entry",
    "timeline_event",
    "agency",
    "local_authority",
    "local_rule",
]


class GeodeModel(BaseModel):
    """Base model with strict field handling for Geode records."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    @field_validator(
        "effective_date",
        "status_date",
        "introduced_date",
        "publication_date",
        "hearing_date",
        "signed_date",
        "issued_date",
        "data_retrieved",
        "date",
        check_fields=False,
    )
    @classmethod
    def validate_not_future_date(cls, value: date | None, info: ValidationInfo) -> date | None:
        """Reject impossible future dates."""

        if cls.__name__ == "RegulationRule" and info.field_name == "effective_date":
            return value
        if cls.__name__ == "SessionLaw" and info.field_name == "effective_date":
            return value
        if cls.__name__ == "RulemakingNotice" and info.field_name in {
            "hearing_date",
            "effective_date",
        }:
            return value
        return require_not_future_date(value)


class ConfidenceScores(GeodeModel):
    """Per-record or per-field confidence scores."""

    overall: float = Field(ge=0.0, le=1.0)
    fields: dict[str, float] = Field(default_factory=dict)
    route: str | None = None

    @field_validator("fields")
    @classmethod
    def validate_field_scores(cls, value: dict[str, float]) -> dict[str, float]:
        """Require field-level confidence scores to be normalized."""

        invalid = {key: score for key, score in value.items() if score < 0.0 or score > 1.0}
        if invalid:
            raise ValueError(f"confidence fields out of range: {sorted(invalid)}")
        return value


def _confidence(value: object) -> ConfidenceScores:
    """Coerce legacy scalar confidence values into design-style objects."""

    if isinstance(value, ConfidenceScores):
        return value
    if isinstance(value, int | float):
        return ConfidenceScores(overall=float(value))
    return ConfidenceScores.model_validate(value)


class SourceDocument(GeodeModel):
    """Immutable raw source metadata for one archived source file."""

    source_id: str = Field(min_length=1)
    layer: LayerName
    source_owner: str = Field(min_length=1)
    source_url: HttpUrl
    source_format: str = Field(min_length=1)
    retrieved_at: datetime
    raw_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    immutable: bool = True
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require source URLs from official or authorized providers."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("retrieved_at")
    @classmethod
    def validate_retrieved_at(cls, value: datetime) -> datetime:
        """Require timezone-aware retrieval timestamps."""

        return require_utc_datetime(value)


class StatuteSection(GeodeModel):
    """Design-schema metadata for one Colorado Revised Statutes section."""

    entity_type: Literal["statute_section"] = "statute_section"
    id: str = Field(
        validation_alias=AliasChoices("id", "entity_id"),
        pattern=r"^CRS-\d{1,2}(?:\.\d+)?-\d+(?:\.\d+)?-\d+(?:\.\d+)?$",
    )
    title_num: str = Field(validation_alias=AliasChoices("title_num", "title_number"))
    title_name: str = Field(min_length=1)
    article_num: str = Field(validation_alias=AliasChoices("article_num", "article_number"))
    article_name: str = Field(min_length=1)
    part_num: str | None = Field(
        default=None,
        validation_alias=AliasChoices("part_num", "part_number"),
    )
    part_name: str | None = None
    section_num: str = Field(validation_alias=AliasChoices("section_num", "section_number"))
    section_heading: str = Field(
        validation_alias=AliasChoices("section_heading", "heading"),
        min_length=1,
    )
    full_text: str = Field(validation_alias=AliasChoices("full_text", "text"), min_length=1)
    effective_date: date | None = None
    last_amended_session: str | None = None
    last_amended_by: list[str] = Field(default_factory=list)
    history_note: str | None = None
    subject_tags: list[str] = Field(default_factory=list)
    industry_tags: list[str] = Field(default_factory=list)
    cross_references_outbound: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("cross_references_outbound", "citations"),
    )
    enabling_agencies: list[str] = Field(default_factory=list)
    related_regulations: list[str] = Field(default_factory=list)
    source_url: HttpUrl
    data_retrieved: date
    data_version: str = Field(min_length=1)
    confidence: ConfidenceScores
    source_path: str = Field(default="", exclude=True)
    publication_year: int | None = Field(default=None, exclude=True)
    regulated_entities: list[str] | None = Field(default=None, exclude=True)
    regulated_entities_confidence: float = Field(default=0.0, ge=0.0, le=1.0, exclude=True)
    effective_date_confidence: float = Field(default=0.0, ge=0.0, le=1.0, exclude=True)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official source URLs for statute records."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> ConfidenceScores:
        """Accept design-style confidence objects and legacy scalar values."""

        return _confidence(value)

    @field_validator("subject_tags")
    @classmethod
    def validate_subject_tags(cls, value: list[str]) -> list[str]:
        """Require subject tags from the controlled ontology."""

        return require_known_values(value, SUBJECT_TAGS, "subject_tags")

    @field_validator("industry_tags")
    @classmethod
    def validate_industry_tags(cls, value: list[str]) -> list[str]:
        """Require industry tags from the controlled ontology."""

        return require_known_values(value, INDUSTRY_TAGS, "industry_tags")

    @model_validator(mode="after")
    def validate_consistency(self) -> "StatuteSection":
        """Check canonical IDs and normalize section-number storage."""

        title = normalize_crs_number(str(self.title_num))
        article = normalize_crs_number(str(self.article_num))
        raw_section = self.section_num.split("-")[-1]
        section = normalize_crs_number(raw_section)
        expected = canonical_crs_id(title, article, section)
        if self.id != expected:
            raise ValueError(f"id must be {expected}")
        self.title_num = title
        self.article_num = article
        self.section_num = f"{title}-{article}-{section}"
        if self.effective_date is None and self.effective_date_confidence != 0.0:
            raise ValueError("missing effective_date must have confidence 0.0")
        if self.regulated_entities is None and self.regulated_entities_confidence != 0.0:
            raise ValueError("missing regulated_entities must have confidence 0.0")
        return self

    @property
    def entity_id(self) -> str:
        """Return the legacy entity ID name."""

        return self.id

    @property
    def title_number(self) -> str:
        """Return the legacy title number name."""

        return self.title_num

    @property
    def article_number(self) -> str:
        """Return the legacy article number name."""

        return self.article_num

    @property
    def part_number(self) -> str | None:
        """Return the legacy part number name."""

        return self.part_num

    @property
    def section_number(self) -> str:
        """Return the legacy section-number segment."""

        return self.section_num.split("-")[-1]

    @property
    def heading(self) -> str:
        """Return the legacy section heading name."""

        return self.section_heading

    @property
    def text(self) -> str:
        """Return the legacy full-text name."""

        return self.full_text

    @property
    def citations(self) -> list[str]:
        """Return the legacy outbound citations name."""

        return self.cross_references_outbound

    @property
    def confidence_overall(self) -> float:
        """Return the record-level confidence score."""

        return self.confidence.overall


class RegulationRule(GeodeModel):
    """Design-schema metadata for one CCR regulation rule."""

    entity_type: Literal["regulation_rule"] = "regulation_rule"
    id: str = Field(pattern=r"^\d{1,2}_CCR_\d+-\d+(?:-\d+)?$")
    ccr_number: str = Field(min_length=1)
    title: str = Field(min_length=1)
    department: str = Field(min_length=1)
    department_code: str = Field(min_length=1)
    agency: str = Field(min_length=1)
    agency_code: str = Field(min_length=1)
    enabling_statutes: list[str]
    effective_date: date | None = None
    status: str
    full_text: str = Field(min_length=1)
    chunk_level_3_summary: str = Field(min_length=1)
    subject_tags: list[str]
    industry_tags: list[str]
    compliance_keywords: list[str] = Field(default_factory=list)
    source_url: HttpUrl
    source_format: Literal["pdf", "docx", "doc"]
    extraction_method: str = Field(min_length=1)
    confidence: ConfidenceScores

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> ConfidenceScores:
        """Accept design-style confidence objects and legacy scalar values."""

        return _confidence(value)

    @field_validator("subject_tags")
    @classmethod
    def validate_subject_tags(cls, value: list[str]) -> list[str]:
        """Require controlled subject tags."""

        return require_known_values(value, SUBJECT_TAGS, "subject_tags")

    @field_validator("industry_tags")
    @classmethod
    def validate_industry_tags(cls, value: list[str]) -> list[str]:
        """Require controlled industry tags."""

        return require_known_values(value, INDUSTRY_TAGS, "industry_tags")

    @field_validator("compliance_keywords")
    @classmethod
    def validate_compliance_keywords(cls, value: list[str]) -> list[str]:
        """Require controlled compliance keywords."""

        return require_known_values(value, COMPLIANCE_KEYWORDS, "compliance_keywords")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        """Require controlled status values."""

        return require_known_values([value], STATUS_VALUES, "status")[0]


class Sponsor(GeodeModel):
    """Bill sponsor metadata."""

    name: str = Field(min_length=1)
    party: str | None = None
    chamber: Literal["Senate", "House"]
    role: str = Field(min_length=1)


class Bill(GeodeModel):
    """Design-schema metadata for one legislative bill."""

    entity_type: Literal["bill"] = "bill"
    id: str = Field(
        pattern=r"^(SB|HB|SCR|HCR|SJR|HJR|SJM|HJM|SR|HR|SM|HM)\d{2}(?:X\d+)?-\d{3,4}$"
    )
    session: str = Field(pattern=r"^\d{4}$")
    chamber: Literal["Senate", "House"]
    bill_number: str = Field(pattern=r"^\d{3,4}$")
    title: str = Field(min_length=1)
    sponsors: list[Sponsor]
    status: str
    status_date: date
    introduced_date: date
    statutes_amended: list[str] = Field(default_factory=list)
    statutes_created: list[str] = Field(default_factory=list)
    statutes_repealed: list[str] = Field(default_factory=list)
    subject_tags: list[str]
    source_url: HttpUrl
    confidence: ConfidenceScores

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        """Require controlled bill status values when known."""

        return require_known_values([value], STATUS_VALUES, "status")[0]

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official or authorized source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("subject_tags")
    @classmethod
    def validate_subject_tags(cls, value: list[str]) -> list[str]:
        """Require controlled subject tags."""

        return require_known_values(value, SUBJECT_TAGS, "subject_tags")

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> ConfidenceScores:
        """Accept design-style confidence objects and legacy scalar values."""

        return _confidence(value)


class RulemakingNotice(GeodeModel):
    """Rulemaking notice from the Colorado Register."""

    entity_type: Literal["rulemaking_notice"] = "rulemaking_notice"
    id: str = Field(pattern=r"^RM-\d{4}-[A-Za-z0-9_-]+$")
    title: str | None = None
    notice_type: str = Field(min_length=1)
    ccr_rule_affected: str = Field(min_length=1)
    ccr_citation: str | None = None
    agency_code: str = Field(min_length=1)
    agency: str | None = None
    summary: str = Field(min_length=1)
    source_section_heading: str | None = None
    source_row_number: int | None = Field(default=None, ge=1)
    source_evidence: str | None = None
    notice_type_source: str | None = None
    hearing_date: date | None = None
    effective_date: date | None = None
    publication_date: date
    edocket_tracking_number: str | None = None
    edocket_url: HttpUrl | None = None
    subject_tags: list[str]
    source_url: HttpUrl
    source_path: str | None = None
    raw_text_path: str | None = None
    extraction_method: str | None = None
    field_confidence: dict[str, float] = Field(default_factory=dict)
    confidence: ConfidenceScores

    @field_validator("subject_tags")
    @classmethod
    def validate_subject_tags(cls, value: list[str]) -> list[str]:
        """Require controlled subject tags."""

        return require_known_values(value, SUBJECT_TAGS, "subject_tags")

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("edocket_url")
    @classmethod
    def validate_edocket_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Require official source URLs for eDocket references."""

        if value is not None:
            require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("field_confidence")
    @classmethod
    def validate_field_confidence(cls, value: dict[str, float]) -> dict[str, float]:
        """Require field confidence scores to be normalized."""

        invalid = {key: score for key, score in value.items() if score < 0.0 or score > 1.0}
        if invalid:
            raise ValueError(f"field_confidence scores out of range: {sorted(invalid)}")
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> ConfidenceScores:
        """Accept design-style confidence objects and legacy scalar values."""

        return _confidence(value)


class ExecutiveOrder(GeodeModel):
    """Governor executive order metadata."""

    entity_type: Literal["executive_order"] = "executive_order"
    id: str = Field(pattern=r"^EO-\d{4}-\d{3}$")
    order_number: str = Field(min_length=1)
    title: str = Field(min_length=1)
    governor: str = Field(min_length=1)
    signed_date: date
    status: str
    full_text: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    statutes_cited: list[str] = Field(default_factory=list)
    subject_tags: list[str]
    source_url: HttpUrl
    source_path: str | None = None
    confidence: ConfidenceScores

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        """Require controlled status values."""

        return require_known_values([value], STATUS_VALUES, "status")[0]

    @field_validator("subject_tags")
    @classmethod
    def validate_subject_tags(cls, value: list[str]) -> list[str]:
        """Require controlled subject tags."""

        return require_known_values(value, SUBJECT_TAGS, "subject_tags")

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> ConfidenceScores:
        """Accept design-style confidence objects and legacy scalar values."""

        return _confidence(value)


class SessionLaw(GeodeModel):
    """Enacted law from a Colorado legislative session."""

    entity_type: Literal["session_law"] = "session_law"
    id: str = Field(pattern=r"^SL-\d{4}-\d+$")
    session_year: str = Field(pattern=r"^\d{4}$")
    chapter: str = Field(min_length=1)
    bill_id: str | None = None
    title: str = Field(min_length=1)
    effective_date: date | None = None
    statutes_affected: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    subject_tags: list[str]
    source_url: HttpUrl
    confidence: ConfidenceScores

    @field_validator("subject_tags")
    @classmethod
    def validate_subject_tags(cls, value: list[str]) -> list[str]:
        """Require controlled subject tags."""

        return require_known_values(value, SUBJECT_TAGS, "subject_tags")

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> ConfidenceScores:
        """Accept design-style confidence objects and legacy scalar values."""

        return _confidence(value)


class AGOpinion(GeodeModel):
    """Formal Colorado Attorney General opinion."""

    entity_type: Literal["ag_opinion"] = "ag_opinion"
    id: str = Field(pattern=r"^AGO-\d{4}-\d+$")
    opinion_number: str = Field(min_length=1)
    title: str = Field(min_length=1)
    attorney_general: str = Field(min_length=1)
    issued_date: date
    statutes_interpreted: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    subject_tags: list[str]
    source_url: HttpUrl
    confidence: ConfidenceScores

    @field_validator("subject_tags")
    @classmethod
    def validate_subject_tags(cls, value: list[str]) -> list[str]:
        """Require controlled subject tags."""

        return require_known_values(value, SUBJECT_TAGS, "subject_tags")

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> ConfidenceScores:
        """Accept design-style confidence objects and legacy scalar values."""

        return _confidence(value)


class COPRRRReview(GeodeModel):
    """COPRRR sunrise or sunset review."""

    entity_type: Literal["coprrr_review"] = "coprrr_review"
    id: str = Field(pattern=r"^COPRRR-\d{4}-[A-Za-z0-9_-]+$")
    review_type: Literal["sunrise", "sunset"]
    program_reviewed: str = Field(min_length=1)
    agency_code: str = Field(min_length=1)
    publication_date: date
    recommendation: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    subject_tags: list[str]
    source_url: HttpUrl
    confidence: ConfidenceScores

    @field_validator("subject_tags")
    @classmethod
    def validate_subject_tags(cls, value: list[str]) -> list[str]:
        """Require controlled subject tags."""

        return require_known_values(value, SUBJECT_TAGS, "subject_tags")

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> ConfidenceScores:
        """Accept design-style confidence objects and legacy scalar values."""

        return _confidence(value)


class FederalStandard(GeodeModel):
    """Federal authority record used as supplementary compliance context."""

    entity_type: Literal["federal_standard"] = "federal_standard"
    id: str = Field(pattern=r"^FED-(CFR|USC)-[A-Za-z0-9_.-]+$")
    title: str = Field(min_length=1)
    citation: str = Field(min_length=1)
    jurisdiction: Literal["federal"] = "federal"
    source_owner: str = Field(min_length=1)
    publication_date: date
    summary: str = Field(min_length=1)
    full_text: str = Field(min_length=1)
    subject_tags: list[str]
    source_url: HttpUrl
    confidence: ConfidenceScores

    @field_validator("subject_tags")
    @classmethod
    def validate_subject_tags(cls, value: list[str]) -> list[str]:
        """Require controlled subject tags."""

        return require_known_values(value, SUBJECT_TAGS, "subject_tags")

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> ConfidenceScores:
        """Accept design-style confidence objects and legacy scalar values."""

        return _confidence(value)


class RuleUnit(GeodeModel):
    """Atomic obligation, prohibition, permission, or related rule unit."""

    entity_type: Literal["rule_unit"] = "rule_unit"
    id: str = Field(min_length=1)
    parent_regulation_id: str = Field(min_length=1)
    source_section: str = Field(min_length=1)
    rule_type: str
    regulated_entity: str = Field(min_length=1)
    action_required: str = Field(min_length=1)
    conditions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    enabling_statute: list[str] = Field(default_factory=list)
    temporal: str | None = None
    penalties: list[str] = Field(default_factory=list)
    plain_english_summary: str = Field(min_length=1)
    subject_tags: list[str]
    confidence: ConfidenceScores
    semantic_status: Literal["semantic_ready", "source_preservation_only", "needs_review"] = (
        "semantic_ready"
    )

    @field_validator("rule_type")
    @classmethod
    def validate_rule_type(cls, value: str) -> str:
        """Require controlled rule types."""

        return require_known_values([value], RULE_TYPES, "rule_type")[0]

    @field_validator("subject_tags")
    @classmethod
    def validate_subject_tags(cls, value: list[str]) -> list[str]:
        """Require controlled subject tags."""

        return require_known_values(value, SUBJECT_TAGS, "subject_tags")

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> ConfidenceScores:
        """Accept design-style confidence objects and legacy scalar values."""

        return _confidence(value)


class CrosswalkEntry(GeodeModel):
    """Relationship record linking two Geode entities."""

    entity_type: Literal["crosswalk_entry", "amendment_history_entry"] = "crosswalk_entry"
    source_id: str = Field(min_length=1)
    source_type: EntityType | str
    target_id: str | None = None
    target_ids: list[str] = Field(default_factory=list)
    target_type: EntityType | str
    relationship: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_evidence: str | None = None
    data_retrieved: date
    agency_name: str | None = None
    department_name: str | None = None
    supporting_regulation_id: str | None = None
    statute_id: str | None = None
    event_id: str | None = None
    event_type: str | None = None
    event_date: date | None = None
    bill_id: str | None = None
    bill_title: str | None = None
    bill_status: str | None = None
    source_url: HttpUrl | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_amendment_history(cls, value: object) -> object:
        """Normalize amendment-history rows into crosswalk-compatible fields."""

        if not isinstance(value, dict):
            return value
        if value.get("entity_type") != "amendment_history_entry":
            return value
        normalized = dict(value)
        bill_id = normalized.get("bill_id")
        statute_id = normalized.get("statute_id")
        event_type = normalized.get("event_type")
        normalized.setdefault("source_id", bill_id or normalized.get("event_id"))
        normalized.setdefault("source_type", "bill" if bill_id else "timeline_event")
        normalized.setdefault("target_id", statute_id)
        normalized.setdefault("target_type", "statute_section")
        normalized.setdefault("relationship", event_type)
        return normalized

    @field_validator("relationship")
    @classmethod
    def validate_relationship(cls, value: str) -> str:
        """Require controlled relationship types."""

        return require_known_values([value], RELATIONSHIP_TYPES, "relationship")[0]

    @model_validator(mode="after")
    def validate_targets(self) -> "CrosswalkEntry":
        """Require one target shape."""

        if not self.target_id and not self.target_ids:
            raise ValueError("target_id or target_ids is required")
        if self.target_id and self.target_ids:
            raise ValueError("use either target_id or target_ids, not both")
        return self


class TimelineEvent(GeodeModel):
    """Unified chronological event across all legal authority layers."""

    id: str = Field(pattern=r"^TE-\d{4}-\d{2}-\d{2}-\d{3}$")
    date: date
    event_type: str
    entity_id: str = Field(min_length=1)
    entity_type: EntityType | str
    description: str = Field(min_length=1)
    affects: list[str] = Field(default_factory=list)
    layer: LayerName
    file_path: str = Field(min_length=1)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        """Require controlled event types."""

        return require_known_values([value], EVENT_TYPES, "event_type")[0]


class Agency(GeodeModel):
    """Colorado state agency metadata."""

    entity_type: Literal["agency"] = "agency"
    id: str = Field(pattern=r"^[A-Z0-9]+_[A-Z0-9]+$")
    agency_name: str = Field(min_length=1)
    agency_abbreviation: str = Field(min_length=1)
    department: str = Field(min_length=1)
    department_code: str = Field(min_length=1)
    enabling_statutes: list[str] | None = None
    ccr_prefix: str | None = None
    regulation_count: int | None = Field(default=None, ge=0)
    website_url: HttpUrl | None = None
    notes: str | None = None

    @field_validator("website_url")
    @classmethod
    def validate_website_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Require official agency URLs when present."""

        if value is not None:
            require_official_source_url(str(value).rstrip("/"))
        return value


class CRSTitleDocument(GeodeModel):
    """Parsed CRS title document ready for Markdown and metadata output."""

    entity_id: str = Field(pattern=r"^CRS-TITLE-\d{1,2}(?:\.\d+)?$")
    title_number: str = Field(pattern=r"^\d{1,2}(?:\.\d+)?$")
    title_name: str = Field(min_length=1)
    publication_year: int = Field(ge=1861)
    generated_at: datetime
    source_document: SourceDocument
    sections: list[StatuteSection]

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        """Require timezone-aware generation timestamps."""

        return require_utc_datetime(value)

    @model_validator(mode="after")
    def validate_sections(self) -> "CRSTitleDocument":
        """Ensure sections belong to this title and publication year."""

        for section in self.sections:
            if section.title_number != self.title_number:
                raise ValueError("section title_number must match document title_number")
            if section.publication_year != self.publication_year:
                raise ValueError("section publication_year must match title publication_year")
        return self


class LayerIndexRecord(GeodeModel):
    """Metadata-only index row for locating a corpus entity."""

    id: str = Field(validation_alias=AliasChoices("id", "entity_id"), min_length=1)
    layer: LayerName
    entity_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    citation: str | None = None
    path: str = Field(min_length=1)
    meta_path: str | None = None
    source_url: HttpUrl
    source_path: str = Field(min_length=1)
    publication_year: int | None = None
    last_updated: datetime
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    authority_id: str | None = None
    authority_name: str | None = None
    authority_level: str | None = None
    authority_type: str | None = None
    district_family: str | None = None
    county_names: list[str] = Field(default_factory=list)
    geographic_scope: list[str] = Field(default_factory=list)
    source_section: str | None = None
    section_heading: str | None = None
    source_page: int | None = Field(default=None, ge=1)
    source_page_end: int | None = Field(default=None, ge=1)
    source_line_start: int | None = Field(default=None, ge=1)
    source_line_end: int | None = Field(default=None, ge=1)
    source_category: str | None = None
    semantic_status: str | None = None
    text_hash: str | None = None

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official source URLs in index rows."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @field_validator("last_updated")
    @classmethod
    def validate_last_updated(cls, value: datetime) -> datetime:
        """Require timezone-aware index timestamps."""

        return require_utc_datetime(value)

    @property
    def entity_id(self) -> str:
        """Return the legacy entity ID name."""

        return self.id


class ManifestEntry(GeodeModel):
    """Manifest metadata for a corpus layer."""

    layer: LayerName
    description: str
    record_count: int = Field(ge=0)
    path: str = Field(min_length=1)
    index_path: str = Field(min_length=1)
    latest_publication_year: int | None = None
    source_ids: list[str] = Field(default_factory=list)
    last_updated: datetime
    status: str = Field(min_length=1)

    @field_validator("last_updated")
    @classmethod
    def validate_last_updated(cls, value: datetime) -> datetime:
        """Require timezone-aware manifest timestamps."""

        return require_utc_datetime(value)


class MasterManifest(GeodeModel):
    """Top-level control-plane manifest."""

    project: str
    schema_version: str
    generated_at: datetime
    layers: dict[str, ManifestEntry]
    notes: str | None = None

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        """Require timezone-aware manifest timestamps."""

        return require_utc_datetime(value)

    @model_validator(mode="after")
    def validate_layer_keys(self) -> "MasterManifest":
        """Ensure known layer names are used as manifest keys."""

        unknown_layers = set(self.layers) - set(ALL_LAYERS)
        if unknown_layers:
            raise ValueError(f"unknown manifest layers: {sorted(unknown_layers)}")
        for key, value in self.layers.items():
            if key != value.layer:
                raise ValueError("manifest layer keys must match entry layer values")
        return self


class UpdateLogRecord(GeodeModel):
    """Append-only control-plane log entry."""

    event_id: str = Field(pattern=r"^UL-[0-9TZ]+-[A-Za-z0-9_-]+$")
    timestamp: datetime
    event_type: str = Field(min_length=1)
    layer: LayerName | None = None
    entity_id: str | None = None
    action: str = Field(min_length=1)
    source_path: str | None = None
    output_paths: list[str] = Field(default_factory=list)
    record_count: int = Field(ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    message: str

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """Require timezone-aware log timestamps."""

        return require_utc_datetime(value)


class QuarantineRecord(GeodeModel):
    """Record for an extraction or validation failure requiring review."""

    event_id: str = Field(pattern=r"^QR-[0-9TZ]+-[A-Za-z0-9_-]+$")
    timestamp: datetime
    source_path: str = Field(min_length=1)
    layer: LayerName
    reason: str = Field(min_length=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reviewed: bool = False

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """Require timezone-aware quarantine timestamps."""

        return require_utc_datetime(value)


class ValidationIssue(GeodeModel):
    """One validation issue emitted by a validation command."""

    severity: Literal["error", "warning"]
    path: str
    message: str


class ValidationResult(GeodeModel):
    """Structured result from validation and integrity checks."""

    valid: bool
    layer: str
    checked_at: datetime
    issues: list[ValidationIssue] = Field(default_factory=list)

    @field_validator("checked_at")
    @classmethod
    def validate_checked_at(cls, value: datetime) -> datetime:
        """Require timezone-aware validation timestamps."""

        return require_utc_datetime(value)

    @classmethod
    def empty(cls, layer: str, checked_at: datetime) -> "ValidationResult":
        """Create an empty valid result for incremental issue collection."""

        return cls(valid=True, layer=layer, checked_at=checked_at, issues=[])

    def add_issue(self, severity: Literal["error", "warning"], path: str, message: str) -> None:
        """Append a validation issue and update the valid flag."""

        self.issues.append(ValidationIssue(severity=severity, path=path, message=message))
        if severity == "error":
            self.valid = False
