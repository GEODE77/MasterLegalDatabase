"""Reusable schema validators and canonical ID helpers."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from geode.constants import AUTHORIZED_SOURCE_HOSTS
from geode.utils.file_io import iter_jsonl


class ValidationReport(BaseModel):
    """Schema validation report for one layer path."""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    path: str
    checked_records: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)


def normalize_crs_number(value: str) -> str:
    """Normalize a CRS numeric segment without changing decimal meaning."""

    value = value.strip()
    if "." not in value:
        return str(int(value))

    left, right = value.split(".", 1)
    return f"{int(left)}.{right.rstrip('0') or '0'}"


def canonical_crs_id(title_number: str, article_number: str, section_number: str) -> str:
    """Build a canonical Colorado Revised Statutes section ID."""

    return (
        "CRS-"
        f"{normalize_crs_number(title_number)}-"
        f"{normalize_crs_number(article_number)}-"
        f"{normalize_crs_number(section_number)}"
    )


def crs_title_stem(title_number: str) -> str:
    """Return the file stem for a CRS title number."""

    normalized = normalize_crs_number(title_number)
    if "." in normalized:
        return f"crs_title_{normalized.replace('.', '_')}"
    return f"crs_title_{int(normalized):02d}"


def require_official_source_url(url: str) -> str:
    """Validate that a source URL belongs to an approved source host."""

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("source URLs must use https")
    host = parsed.netloc.lower()
    if host not in AUTHORIZED_SOURCE_HOSTS and not host.endswith(".colorado.gov"):
        raise ValueError(f"unauthorized source host: {host}")
    return url


def require_utc_datetime(value: datetime) -> datetime:
    """Require timezone-aware datetimes for durable control-plane records."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include timezone information")
    return value


def require_not_future_date(value: date | None) -> date | None:
    """Reject dates after the local system date."""

    comparison_value = value.date() if isinstance(value, datetime) else value
    if comparison_value is not None and comparison_value > date.today():
        raise ValueError("date cannot be in the future")
    return value


def _record_model_for(data: dict[str, Any]) -> type[BaseModel]:
    """Select the Pydantic model for a raw Geode record."""

    from geode.schemas.models import (
        AGOpinion,
        Agency,
        Bill,
        COPRRRReview,
        CrosswalkEntry,
        ExecutiveOrder,
        FederalStandard,
        RegulationRule,
        RuleUnit,
        RulemakingNotice,
        SessionLaw,
        StatuteSection,
        TimelineEvent,
    )
    from geode.schemas.local import LocalAuthority, LocalRule

    record_id = str(data.get("id", ""))
    if record_id.startswith("TE-"):
        return TimelineEvent
    if "relationship" in data and "source_id" in data:
        return CrosswalkEntry

    entity_type = data.get("entity_type")
    models: dict[str, type[BaseModel]] = {
        "statute_section": StatuteSection,
        "regulation_rule": RegulationRule,
        "bill": Bill,
        "rulemaking_notice": RulemakingNotice,
        "executive_order": ExecutiveOrder,
        "session_law": SessionLaw,
        "ag_opinion": AGOpinion,
        "coprrr_review": COPRRRReview,
        "federal_standard": FederalStandard,
        "rule_unit": RuleUnit,
        "agency": Agency,
        "local_authority": LocalAuthority,
        "local_rule": LocalRule,
    }
    if entity_type not in models:
        raise ValueError(f"unknown entity_type: {entity_type}")
    return models[str(entity_type)]


def validate_record(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate one raw record against the matching Pydantic model."""

    try:
        model = _record_model_for(data)
        model.model_validate(data)
    except (ValidationError, ValueError) as exc:
        return False, [str(exc)]
    return True, []


def validate_layer(layer_path: Path) -> ValidationReport:
    """Validate every JSONL record under a layer path."""

    errors: list[str] = []
    checked_records = 0
    for jsonl_path in sorted(layer_path.rglob("*.jsonl")):
        try:
            rows = iter_jsonl(jsonl_path)
            for line_number, row in enumerate(rows, start=1):
                checked_records += 1
                if jsonl_path.name == "_index.jsonl":
                    from geode.schemas.models import LayerIndexRecord

                    try:
                        LayerIndexRecord.model_validate(row)
                        valid, row_errors = True, []
                    except ValidationError as exc:
                        valid, row_errors = False, [str(exc)]
                else:
                    valid, row_errors = validate_record(row)
                for error in row_errors:
                    errors.append(f"{jsonl_path}:{line_number}: {error}")
        except ValueError as exc:
            errors.append(f"{jsonl_path}: {exc}")
    return ValidationReport(
        valid=not errors,
        path=layer_path.as_posix(),
        checked_records=checked_records,
        errors=errors,
    )
