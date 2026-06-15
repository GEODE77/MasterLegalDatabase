"""Pilot ingestion helpers for Phase 4 readiness."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from geode.constants import CONTROL_PLANE_DIR
from geode.schemas.models import ValidationResult
from geode.schemas.validators import require_official_source_url
from geode.utils.file_io import load_json

PILOT_TARGETS = {
    "public_health_environment": ("Public Health", "Environment"),
    "labor_employment": ("Labor", "Employment"),
    "natural_resources": ("Natural Resources",),
    "regulatory_agencies": ("Regulatory Agencies", "DORA"),
    "revenue": ("Revenue",),
}
PILOT_TEST_SET_FILENAME = "PILOT_TEST_SET.json"


class PageRange(BaseModel):
    """Estimated page range for a pilot rule."""

    model_config = ConfigDict(extra="forbid")

    min: int = Field(ge=1)
    max: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_range(self) -> "PageRange":
        """Require max to be greater than or equal to min when known."""

        if self.max is not None and self.max < self.min:
            raise ValueError("estimated page max must be greater than or equal to min")
        return self


class ExpectedOntologyTags(BaseModel):
    """Expected controlled and non-controlled pilot ontology hints."""

    model_config = ConfigDict(extra="forbid")

    subject_tags: list[str] = Field(default_factory=list)
    industry_tags: list[str] = Field(default_factory=list)
    compliance_keywords: list[str] = Field(default_factory=list)
    tag_notes: list[str] = Field(default_factory=list)


class PilotRule(BaseModel):
    """Canonical metadata for one Phase 4A CCR pilot rule."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sequence: int = Field(ge=1, le=15)
    ccr_number: str = Field(pattern=r"^\d{1,2}\s+CCR\s+\d+-\d+(?:-\d+)?$")
    canonical_id: str = Field(pattern=r"^\d{1,2}_CCR_\d+-\d+(?:-\d+)?$")
    title: str = Field(min_length=1)
    department: str = Field(min_length=1)
    department_code: str = Field(pattern=r"^\d{3,4}$")
    agency: str = Field(min_length=1)
    agency_abbreviation_hint: str | None = None
    format_available: str = Field(min_length=1)
    format_status: Literal["confirmed_docx_pdf", "expected_docx_pdf"]
    size_label: Literal["short", "medium", "large", "very_large"]
    estimated_page_range: PageRange
    sos_rule_info_url: HttpUrl
    key_test_focus: list[str] = Field(min_length=1)
    why_selected: list[str] = Field(min_length=1)
    expected_ontology_tags: ExpectedOntologyTags

    @field_validator("sos_rule_info_url")
    @classmethod
    def validate_sos_rule_info_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official Secretary of State rule-info URLs."""

        url = str(value).rstrip("/")
        require_official_source_url(url)
        if "DisplayRule.do" not in url or "action=ruleinfo" not in url:
            raise ValueError("sos_rule_info_url must be a rule-info DisplayRule URL")
        return value

    @model_validator(mode="after")
    def validate_canonical_id(self) -> "PilotRule":
        """Require canonical CCR IDs to be derived from the CCR number."""

        expected = canonical_ccr_id(self.ccr_number)
        if self.canonical_id != expected:
            raise ValueError(f"canonical_id must be {expected}")
        return self


class PilotSelectionReport(BaseModel):
    """Selected CCR pilot set summary."""

    model_config = ConfigDict(extra="forbid")

    selected: list[dict[str, Any]]
    by_bucket: dict[str, int]
    has_docx: bool
    has_pdf: bool
    recommendations: list[str] = Field(default_factory=list)


class PilotQualityReport(BaseModel):
    """Quality report for a pilot ingestion run."""

    model_config = ConfigDict(extra="forbid")

    processed: int = Field(ge=0)
    auto_accepted: int = Field(ge=0)
    flagged: int = Field(ge=0)
    quarantined: int = Field(ge=0)
    auto_accept_rate: float = Field(ge=0.0, le=1.0)
    average_confidence: float = Field(ge=0.0, le=1.0)
    common_errors: dict[str, int]
    conversion_paths: dict[str, int]
    average_seconds_per_record: float = Field(ge=0.0)
    total_api_cost_usd: float = Field(ge=0.0)
    recommendations: list[str]


def canonical_ccr_id(ccr_number: str) -> str:
    """Build the Geode canonical ID for a CCR rule number."""

    return "_".join(ccr_number.split())


def load_pilot_test_set(root: Path) -> list[PilotRule]:
    """Load canonical Phase 4A pilot rules from the control plane."""

    path = root / CONTROL_PLANE_DIR / PILOT_TEST_SET_FILENAME
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{PILOT_TEST_SET_FILENAME} must contain an object")
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise ValueError(f"{PILOT_TEST_SET_FILENAME} must contain a rules list")
    return [PilotRule.model_validate(rule) for rule in rules]


def validate_pilot_test_set(
    rules: list[PilotRule | dict[str, Any]],
    root: Path | None = None,
) -> ValidationResult:
    """Validate the canonical pilot rule set and ontology tag references."""

    result = ValidationResult.empty(
        layer="pilot_test_set",
        checked_at=datetime.now(timezone.utc),
    )
    validated: list[PilotRule] = []
    for index, rule in enumerate(rules, start=1):
        try:
            validated.append(PilotRule.model_validate(rule))
        except ValueError as exc:
            result.add_issue("error", f"rules[{index}]", str(exc))

    if len(validated) != 15:
        result.add_issue("error", "rules", "pilot test set must contain exactly 15 rules")

    _add_duplicate_issues(result, "sequence", [str(rule.sequence) for rule in validated])
    _add_duplicate_issues(result, "ccr_number", [rule.ccr_number for rule in validated])
    _add_duplicate_issues(result, "canonical_id", [rule.canonical_id for rule in validated])

    expected_sequences = list(range(1, len(validated) + 1))
    actual_sequences = [rule.sequence for rule in validated]
    if actual_sequences != expected_sequences:
        result.add_issue("error", "rules.sequence", "sequences must be consecutive")

    if root is not None:
        ontology = _load_ontology(root)
        _validate_tag_set(
            result,
            validated,
            "subject_tags",
            ontology["subject_tags"],
        )
        _validate_tag_set(
            result,
            validated,
            "industry_tags",
            ontology["industry_tags"],
        )
        _validate_tag_set(
            result,
            validated,
            "compliance_keywords",
            ontology["compliance_keywords"],
        )
    return result


def summarize_pilot_test_set(rules: list[PilotRule]) -> dict[str, dict[str, int]]:
    """Return summary counts useful for pilot readiness reporting."""

    return {
        "by_department": dict(Counter(rule.department for rule in rules)),
        "by_format_status": dict(Counter(rule.format_status for rule in rules)),
        "by_size_label": dict(Counter(rule.size_label for rule in rules)),
    }


def pilot_rules_to_ccr_entries(rules: list[PilotRule]) -> list[dict[str, Any]]:
    """Convert pilot metadata into CCR downloader handoff entries."""

    entries: list[dict[str, Any]] = []
    for rule in rules:
        entries.append(
            {
                "ccr_number": rule.ccr_number,
                "canonical_id": rule.canonical_id,
                "department": rule.department,
                "department_code": rule.department_code,
                "agency": rule.agency,
                "agency_abbreviation_hint": rule.agency_abbreviation_hint,
                "source_page_url": str(rule.sos_rule_info_url),
                "sos_rule_info_url": str(rule.sos_rule_info_url),
                "docx_url": None,
                "pdf_url": None,
                "format_status": rule.format_status,
            }
        )
    return entries


def select_pilot_set(
    rules: list[dict[str, Any]],
    min_total: int = 10,
    max_total: int = 15,
) -> PilotSelectionReport:
    """Select a broad 10-15 rule pilot set from discovered CCR entries."""

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rule in rules:
        bucket = _bucket_for(rule)
        if bucket:
            buckets[bucket].append(rule)
    selected: list[dict[str, Any]] = []
    for bucket in PILOT_TARGETS:
        selected.extend(buckets.get(bucket, [])[:3])
    selected = selected[:max_total]
    if len(selected) < min_total:
        remaining = [rule for rule in rules if rule not in selected]
        selected.extend(remaining[: min_total - len(selected)])
    selected = selected[:max_total]
    by_bucket = Counter(_bucket_for(rule) or "other" for rule in selected)
    has_docx = any(rule.get("docx_url") for rule in selected)
    has_pdf = any(rule.get("pdf_url") and not rule.get("docx_url") for rule in selected)
    recommendations = []
    if len(selected) < min_total:
        recommendations.append("Discover more CCR rules before running the pilot.")
    if not has_docx or not has_pdf:
        recommendations.append("Add both DOCX and PDF-only rules to the pilot set.")
    return PilotSelectionReport(
        selected=selected,
        by_bucket=dict(by_bucket),
        has_docx=has_docx,
        has_pdf=has_pdf,
        recommendations=recommendations,
    )


def generate_quality_report(run_records: list[dict[str, Any]]) -> PilotQualityReport:
    """Generate Phase 4E quality metrics from per-record pilot run telemetry."""

    processed = len(run_records)
    routes = Counter(str(record.get("route", "quarantine")).lower() for record in run_records)
    confidences = [float(record.get("confidence", 0.0)) for record in run_records]
    durations = [float(record.get("seconds", 0.0)) for record in run_records]
    errors = Counter()
    conversion_paths = Counter()
    total_cost = 0.0
    for record in run_records:
        conversion_paths[str(record.get("conversion_path", "unknown"))] += 1
        total_cost += float(record.get("api_cost_usd", 0.0))
        for error in record.get("errors", []) or []:
            errors[str(error)] += 1
    auto_accepted = routes["auto_accept"]
    auto_accept_rate = auto_accepted / processed if processed else 0.0
    recommendations = []
    if auto_accept_rate < 0.70:
        recommendations.append("Auto-accept rate is below 70%; inspect common errors.")
    if errors:
        recommendations.append("Prioritize fixes for the most common extraction errors.")
    if not processed:
        recommendations.append("Run the pilot pipeline on real CCR records.")
    return PilotQualityReport(
        processed=processed,
        auto_accepted=auto_accepted,
        flagged=routes["flag_accept"],
        quarantined=routes["quarantine"],
        auto_accept_rate=auto_accept_rate,
        average_confidence=mean(confidences) if confidences else 0.0,
        common_errors=dict(errors.most_common()),
        conversion_paths=dict(conversion_paths),
        average_seconds_per_record=mean(durations) if durations else 0.0,
        total_api_cost_usd=round(total_cost, 4),
        recommendations=recommendations,
    )


def _bucket_for(rule: dict[str, Any]) -> str | None:
    """Classify a rule into the Phase 4A department buckets."""

    haystack = f"{rule.get('department', '')} {rule.get('agency', '')}".casefold()
    for bucket, needles in PILOT_TARGETS.items():
        if any(needle.casefold() in haystack for needle in needles):
            return bucket
    return None


def _load_ontology(root: Path) -> dict[str, set[str]]:
    """Load controlled vocabulary sets from ONTOLOGY.json."""

    payload = load_json(root / CONTROL_PLANE_DIR / "ONTOLOGY.json")
    if not isinstance(payload, dict):
        raise ValueError("ONTOLOGY.json must contain an object")
    compliance = payload.get("compliance_keywords")
    if not isinstance(compliance, list):
        raise ValueError("ONTOLOGY.json compliance_keywords must be a list")
    return {
        "subject_tags": _flatten_subject_tags(payload.get("subject_tags")),
        "industry_tags": _flatten_industry_tags(payload.get("industry_tags")),
        "compliance_keywords": {str(tag) for tag in compliance},
    }


def _flatten_subject_tags(subject_tags: object) -> set[str]:
    """Flatten hierarchical or list-style subject ontology payloads."""

    if isinstance(subject_tags, list):
        return {str(tag) for tag in subject_tags}
    if not isinstance(subject_tags, dict):
        raise ValueError("ONTOLOGY.json subject_tags must be an object or list")
    flattened: set[str] = set()
    for parent, payload in subject_tags.items():
        flattened.add(str(parent))
        if not isinstance(payload, dict):
            raise ValueError(f"subject tag parent {parent} must be an object")
        children = payload.get("children")
        if not isinstance(children, list):
            raise ValueError(f"subject tag parent {parent} must define children")
        flattened.update(str(child) for child in children)
    return flattened


def _flatten_industry_tags(industry_tags: object) -> set[str]:
    """Flatten list or object-style industry ontology payloads."""

    if not isinstance(industry_tags, list):
        raise ValueError("ONTOLOGY.json industry_tags must be a list")
    flattened: set[str] = set()
    for item in industry_tags:
        if isinstance(item, dict):
            if "tag" not in item:
                raise ValueError("industry tag objects must include tag")
            flattened.add(str(item["tag"]))
        else:
            flattened.add(str(item))
    return flattened


def _add_duplicate_issues(
    result: ValidationResult,
    label: str,
    values: list[str],
) -> None:
    """Add validation errors for duplicate values."""

    counts = Counter(values)
    duplicates = sorted(value for value, count in counts.items() if count > 1)
    if duplicates:
        result.add_issue("error", f"rules.{label}", f"duplicate {label}: {duplicates}")


def _validate_tag_set(
    result: ValidationResult,
    rules: list[PilotRule],
    field_name: Literal["subject_tags", "industry_tags", "compliance_keywords"],
    allowed: set[str],
) -> None:
    """Validate a pilot tag field against a controlled vocabulary."""

    for rule in rules:
        values = getattr(rule.expected_ontology_tags, field_name)
        unknown = sorted(set(values) - allowed)
        if unknown:
            path = f"rules[{rule.sequence}].expected_ontology_tags.{field_name}"
            result.add_issue("error", path, f"unknown controlled tags: {unknown}")
