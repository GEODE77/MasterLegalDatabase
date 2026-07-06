"""Deterministic CCR industry tagging and filtering."""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from geode.connectors.ccr_dataset import (
    CCR_DATASET_COLUMNS,
    DATASET_DIR_NAME,
    DATASET_JSONL_NAME,
    REGULATIONS_LAYER,
    CCRDatasetRecord,
    write_ccr_dataset,
)
from geode.connectors.ccr_industry_taxonomy import DEFAULT_CCR_TAXONOMY
from geode.schemas.ontology import INDUSTRY_TAGS, SUBJECT_TAGS, require_known_values
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, atomic_write_text, iter_jsonl
from geode.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)

TAGGED_JSONL_NAME = "ccr_items_tagged.jsonl"
TAGGED_CSV_NAME = "ccr_items_tagged.csv"
TAG_SUMMARY_NAME = "ccr_tag_summary.json"
FILTER_SUMMARY_NAME = "ccr_filter_summary.json"
DEFAULT_FILTER_PREFIX = "ccr_items_filtered"
MATCHABLE_FIELDS = {
    "record_id",
    "title",
    "rule_name",
    "department",
    "department_normalized",
    "agency",
    "agency_normalized",
    "division_board_program",
    "ccr_citation",
    "department_number",
    "chapter",
    "rule_number",
    "source_page_url",
    "document_url",
}
COORSTEK_HIGH_VALUE_DOMAINS = {
    "building_fire_industrial_operations",
    "chemicals_exposure",
    "environmental_air",
    "environmental_waste",
    "environmental_water",
    "general_manufacturing",
    "materials_product_compliance",
    "mining_minerals_natural_resources",
    "occupational_safety",
    "transportation_hazmat",
    "wage_hour",
    "workplace_health",
}
COORSTEK_ADJACENT_INDUSTRIES = {
    "manufacturing",
    "mining",
    "oil_gas",
    "transportation_warehousing",
    "utilities",
}
DOMAIN_FILTER_ALIASES = {
    "coorstek": sorted(COORSTEK_HIGH_VALUE_DOMAINS),
    "ehs": [
        "chemicals_exposure",
        "environmental_air",
        "environmental_waste",
        "environmental_water",
        "occupational_safety",
        "workplace_health",
    ],
    "environmental": [
        "environmental_air",
        "environmental_waste",
        "environmental_water",
    ],
    "labor": ["labor_employment", "wage_hour"],
    "manufacturing": ["general_manufacturing"],
    "public_health_chemicals": ["chemicals_exposure"],
}

TAGGED_COLUMNS = (
    *CCR_DATASET_COLUMNS,
    "industry_tags",
    "topic_tags",
    "domain_tags",
    "tag_confidence_score",
    "tag_confidence_label",
    "coorstek_relevance",
    "tag_rule_sources",
    "tag_notes",
)


class CCRTagRule(BaseModel):
    """One deterministic CCR tagging rule."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(min_length=1)
    source: Literal["agency", "keyword", "citation"]
    match_fields: list[str] = Field(default_factory=list)
    any_terms: list[str] = Field(default_factory=list)
    all_terms: list[str] = Field(default_factory=list)
    citation_prefixes: list[str] = Field(default_factory=list)
    industry_tags: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)

    @field_validator("match_fields")
    @classmethod
    def validate_match_fields(cls, values: list[str]) -> list[str]:
        """Require match fields to be available on CCR dataset records."""

        unknown = sorted(set(values) - MATCHABLE_FIELDS)
        if unknown:
            raise ValueError(f"unknown CCR taxonomy match fields: {unknown}")
        return values

    @field_validator("industry_tags")
    @classmethod
    def validate_industry_tags(cls, values: list[str]) -> list[str]:
        """Require industry tags to use the Geode ontology."""

        return require_known_values(values, INDUSTRY_TAGS, "industry_tags")

    @field_validator("topic_tags")
    @classmethod
    def validate_topic_tags(cls, values: list[str]) -> list[str]:
        """Require topic tags to use the Geode subject ontology."""

        return require_known_values(values, SUBJECT_TAGS, "topic_tags")


class CCRTagTaxonomy(BaseModel):
    """Validated CCR industry filtering taxonomy."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    rules: list[CCRTagRule]


class CCRTagRuleMatch(BaseModel):
    """One rule match recorded on a tagged CCR row."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    source: Literal["agency", "keyword", "citation"]
    confidence: float = Field(ge=0.0, le=1.0)
    matched_text: str
    reason: str
    industry_tags: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)


class CCRTaggedRecord(CCRDatasetRecord):
    """CCR dataset record enriched with deterministic filtering tags."""

    industry_tags: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    tag_confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    tag_confidence_label: Literal["none", "low", "moderate", "high"] = "none"
    coorstek_relevance: Literal["none", "low", "moderate", "high"] = "none"
    tag_rule_sources: list[CCRTagRuleMatch] = Field(default_factory=list)
    tag_notes: str | None = None

    @field_validator("industry_tags")
    @classmethod
    def validate_tagged_industries(cls, values: list[str]) -> list[str]:
        """Require tagged industries to use the Geode ontology."""

        return require_known_values(values, INDUSTRY_TAGS, "industry_tags")

    @field_validator("topic_tags")
    @classmethod
    def validate_tagged_topics(cls, values: list[str]) -> list[str]:
        """Require tagged topics to use the Geode subject ontology."""

        return require_known_values(values, SUBJECT_TAGS, "topic_tags")


class CCRFilterCriteria(BaseModel):
    """Inclusion and exclusion criteria for tagged CCR records."""

    model_config = ConfigDict(extra="forbid")

    include_industries: list[str] = Field(default_factory=list)
    exclude_industries: list[str] = Field(default_factory=list)
    include_topics: list[str] = Field(default_factory=list)
    exclude_topics: list[str] = Field(default_factory=list)
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)
    match_mode: Literal["any", "all"] = "any"
    min_confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("include_industries", "exclude_industries")
    @classmethod
    def validate_filter_industries(cls, values: list[str]) -> list[str]:
        """Require industry filters to use the Geode ontology."""

        return require_known_values(values, INDUSTRY_TAGS, "industry_filters")

    @field_validator("include_topics", "exclude_topics")
    @classmethod
    def validate_filter_topics(cls, values: list[str]) -> list[str]:
        """Require topic filters to use the Geode subject ontology."""

        return require_known_values(values, SUBJECT_TAGS, "topic_filters")

    @property
    def is_active(self) -> bool:
        """Return whether the filter changes the output dataset."""

        return bool(
            self.include_industries
            or self.exclude_industries
            or self.include_topics
            or self.exclude_topics
            or self.include_domains
            or self.exclude_domains
            or self.min_confidence_score is not None
        )


class CCRIndustryFilterSummary(BaseModel):
    """Summary of a CCR tagging/filtering run."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    taxonomy_version: str
    output_root: str
    input_jsonl_path: str
    tagged_jsonl_path: str
    tagged_csv_path: str
    summary_path: str
    filtered_jsonl_path: str | None = None
    filtered_csv_path: str | None = None
    filter_summary_path: str | None = None
    records_total: int = Field(ge=0)
    tagged_total: int = Field(ge=0)
    untagged_total: int = Field(ge=0)
    filtered_total: int | None = Field(default=None, ge=0)
    industry_counts: dict[str, int] = Field(default_factory=dict)
    topic_counts: dict[str, int] = Field(default_factory=dict)
    domain_counts: dict[str, int] = Field(default_factory=dict)
    coorstek_relevance_counts: dict[str, int] = Field(default_factory=dict)
    confidence_counts: dict[str, int] = Field(default_factory=dict)
    rule_match_counts: dict[str, int] = Field(default_factory=dict)
    filter_criteria: dict[str, Any] | None = None


class _IndustryPaths(BaseModel):
    """Canonical paths for CCR industry-filter artifacts."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    output_root: Path
    dataset_dir: Path
    input_jsonl_path: Path
    tagged_jsonl_path: Path
    tagged_csv_path: Path
    summary_path: Path


def load_default_taxonomy() -> CCRTagTaxonomy:
    """Return the built-in CCR industry-filter taxonomy."""

    return CCRTagTaxonomy.model_validate(DEFAULT_CCR_TAXONOMY)


def tag_ccr_record(
    record: CCRDatasetRecord | dict[str, Any],
    taxonomy: CCRTagTaxonomy | None = None,
) -> CCRTaggedRecord:
    """Apply deterministic CCR industry-filter tags to one normalized record."""

    source_record = (
        record if isinstance(record, CCRDatasetRecord) else CCRDatasetRecord.model_validate(record)
    )
    taxonomy = taxonomy or load_default_taxonomy()
    matches = [
        match
        for rule in taxonomy.rules
        if (match := _match_rule(source_record, rule)) is not None
    ]
    industry_tags = _sorted_unique(tag for match in matches for tag in match.industry_tags)
    topic_tags = _sorted_unique(tag for match in matches for tag in match.topic_tags)
    domain_tags = _sorted_unique(tag for match in matches for tag in match.domain_tags)
    confidence_score = _confidence_score(matches)
    return CCRTaggedRecord(
        **source_record.model_dump(mode="json", exclude_none=False),
        industry_tags=industry_tags,
        topic_tags=topic_tags,
        domain_tags=domain_tags,
        tag_confidence_score=confidence_score,
        tag_confidence_label=_confidence_label(confidence_score),
        coorstek_relevance=_coorstek_relevance(industry_tags, domain_tags, confidence_score),
        tag_rule_sources=matches,
        tag_notes=_tag_notes(matches),
    )


def write_ccr_industry_tags(
    output_root: Path,
    *,
    criteria: CCRFilterCriteria | None = None,
    input_jsonl_path: Path | None = None,
    filtered_prefix: str = DEFAULT_FILTER_PREFIX,
    taxonomy: CCRTagTaxonomy | None = None,
) -> CCRIndustryFilterSummary:
    """Tag the normalized CCR dataset and optionally write a filtered dataset."""

    taxonomy = taxonomy or load_default_taxonomy()
    paths = _industry_paths(output_root, input_jsonl_path)
    if not paths.input_jsonl_path.exists() and input_jsonl_path is None:
        write_ccr_dataset(output_root)
    records = [
        tag_ccr_record(CCRDatasetRecord.model_validate(row), taxonomy)
        for row in iter_jsonl(paths.input_jsonl_path)
    ]
    paths.dataset_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_jsonl(paths.tagged_jsonl_path, records, paths.output_root)
    _write_csv(paths.tagged_csv_path, records, paths.output_root)

    criteria = criteria or CCRFilterCriteria()
    filtered_records: list[CCRTaggedRecord] | None = None
    filtered_jsonl_path: Path | None = None
    filtered_csv_path: Path | None = None
    filter_summary_path: Path | None = None
    if criteria.is_active:
        safe_prefix = _safe_prefix(filtered_prefix)
        filtered_jsonl_path = paths.dataset_dir / f"{safe_prefix}.jsonl"
        filtered_csv_path = paths.dataset_dir / f"{safe_prefix}.csv"
        filter_summary_path = paths.dataset_dir / f"{safe_prefix}_summary.json"
        filtered_records = [record for record in records if record_matches_filter(record, criteria)]
        atomic_write_jsonl(filtered_jsonl_path, filtered_records, paths.output_root)
        _write_csv(filtered_csv_path, filtered_records, paths.output_root)

    summary = _build_summary(
        paths,
        taxonomy,
        records,
        criteria,
        filtered_records,
        filtered_jsonl_path,
        filtered_csv_path,
        filter_summary_path,
    )
    atomic_write_json(paths.summary_path, summary, paths.output_root)
    if filter_summary_path is not None:
        atomic_write_json(filter_summary_path, summary, paths.output_root)
    LOGGER.info(
        "Wrote CCR industry tags records=%s tagged=%s filtered=%s",
        summary.records_total,
        summary.tagged_total,
        summary.filtered_total,
    )
    return summary


def record_matches_filter(record: CCRTaggedRecord, criteria: CCRFilterCriteria) -> bool:
    """Return whether a tagged CCR row satisfies inclusion/exclusion filters."""

    if criteria.min_confidence_score is not None:
        if record.tag_confidence_score < criteria.min_confidence_score:
            return False
    if _intersects(record.industry_tags, criteria.exclude_industries):
        return False
    if _intersects(record.topic_tags, criteria.exclude_topics):
        return False
    include_domains = _expand_domain_filters(criteria.include_domains)
    exclude_domains = _expand_domain_filters(criteria.exclude_domains)
    if _intersects(record.domain_tags, exclude_domains):
        return False
    include_groups = [
        (record.industry_tags, criteria.include_industries),
        (record.topic_tags, criteria.include_topics),
        (record.domain_tags, include_domains),
    ]
    active_groups = [(actual, required) for actual, required in include_groups if required]
    if not active_groups:
        return True
    if criteria.match_mode == "all":
        return all(_intersects(actual, required) for actual, required in active_groups)
    return any(_intersects(actual, required) for actual, required in active_groups)


def build_parser() -> argparse.ArgumentParser:
    """Build the CCR industry-filter CLI parser."""

    parser = argparse.ArgumentParser(description="Tag and filter normalized CCR records.")
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    parser.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--include-industry", action="append", default=[])
    parser.add_argument("--exclude-industry", action="append", default=[])
    parser.add_argument("--include-topic", action="append", default=[])
    parser.add_argument("--exclude-topic", action="append", default=[])
    parser.add_argument("--include-domain", action="append", default=[])
    parser.add_argument("--exclude-domain", action="append", default=[])
    parser.add_argument("--match-mode", choices=["any", "all"], default="any")
    parser.add_argument("--min-confidence-score", type=float)
    parser.add_argument("--filtered-prefix", default=DEFAULT_FILTER_PREFIX)
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CCR industry-filter CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(getattr(logging, args.log_level))
    try:
        summary = write_ccr_industry_tags(
            args.output_root,
            criteria=_criteria_from_args(args),
            input_jsonl_path=args.input_jsonl,
            filtered_prefix=args.filtered_prefix,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        _print_summary(summary)
    return 0


def _criteria_from_args(args: argparse.Namespace) -> CCRFilterCriteria:
    """Build filter criteria from CLI arguments."""

    return CCRFilterCriteria(
        include_industries=_split_filter_values(args.include_industry),
        exclude_industries=_split_filter_values(args.exclude_industry),
        include_topics=_split_filter_values(args.include_topic),
        exclude_topics=_split_filter_values(args.exclude_topic),
        include_domains=_split_filter_values(args.include_domain),
        exclude_domains=_split_filter_values(args.exclude_domain),
        match_mode=args.match_mode,
        min_confidence_score=args.min_confidence_score,
    )


def _industry_paths(output_root: Path, input_jsonl_path: Path | None) -> _IndustryPaths:
    """Return canonical CCR industry-filter artifact paths."""

    root = output_root.resolve()
    dataset_dir = root / REGULATIONS_LAYER / DATASET_DIR_NAME
    return _IndustryPaths(
        output_root=root,
        dataset_dir=dataset_dir,
        input_jsonl_path=input_jsonl_path or dataset_dir / DATASET_JSONL_NAME,
        tagged_jsonl_path=dataset_dir / TAGGED_JSONL_NAME,
        tagged_csv_path=dataset_dir / TAGGED_CSV_NAME,
        summary_path=dataset_dir / TAG_SUMMARY_NAME,
    )


def _match_rule(record: CCRDatasetRecord, rule: CCRTagRule) -> CCRTagRuleMatch | None:
    """Return a rule match when the CCR record satisfies a taxonomy rule."""

    field_texts = _field_texts(record, rule.match_fields)
    search_text = " ".join(field_texts)
    matched_terms: list[str] = []
    if rule.any_terms:
        any_matches = [term for term in rule.any_terms if _contains(search_text, term)]
        matched_terms.extend(any_matches)
    if rule.all_terms and all(_contains(search_text, term) for term in rule.all_terms):
        matched_terms.extend(rule.all_terms)
    if rule.citation_prefixes:
        citation = _normalize_text(record.ccr_citation or record.record_id)
        prefix_matches = [
            prefix
            for prefix in rule.citation_prefixes
            if citation.startswith(_normalize_text(prefix))
        ]
        matched_terms.extend(prefix_matches)
    if not matched_terms:
        return None
    return CCRTagRuleMatch(
        rule_id=rule.rule_id,
        source=rule.source,
        confidence=rule.confidence,
        matched_text=", ".join(_sorted_unique(matched_terms)),
        reason=rule.reason,
        industry_tags=rule.industry_tags,
        topic_tags=rule.topic_tags,
        domain_tags=rule.domain_tags,
    )


def _field_texts(record: CCRDatasetRecord, fields: list[str]) -> list[str]:
    """Return normalized field texts from a CCR record."""

    texts: list[str] = []
    for field in fields:
        value = getattr(record, field)
        if value is not None:
            texts.append(str(value))
    return texts


def _contains(search_text: str, term: str) -> bool:
    """Return whether normalized search text contains a normalized term."""

    normalized_term = _normalize_text(term)
    return bool(normalized_term and normalized_term in _normalize_text(search_text))


def _normalize_text(value: str) -> str:
    """Normalize text for deterministic case-insensitive matching."""

    return re.sub(r"\s+", " ", value.casefold()).strip()


def _confidence_score(matches: list[CCRTagRuleMatch]) -> float:
    """Return a bounded confidence score from the rules that matched."""

    if not matches:
        return 0.0
    strongest = max(match.confidence for match in matches)
    bonus = min(0.08, 0.02 * max(0, len(matches) - 1))
    return min(0.99, round(strongest + bonus, 3))


def _confidence_label(score: float) -> Literal["none", "low", "moderate", "high"]:
    """Return a human-readable confidence bucket."""

    if score >= 0.85:
        return "high"
    if score >= 0.65:
        return "moderate"
    if score > 0:
        return "low"
    return "none"


def _coorstek_relevance(
    industry_tags: list[str],
    domain_tags: list[str],
    confidence_score: float,
) -> Literal["none", "low", "moderate", "high"]:
    """Return a practical CoorsTek-relevance bucket for triage."""

    industries = set(industry_tags)
    domains = set(domain_tags)
    if "manufacturing" in industries and domains & COORSTEK_HIGH_VALUE_DOMAINS:
        return "high" if confidence_score >= 0.65 else "moderate"
    if industries & COORSTEK_ADJACENT_INDUSTRIES or domains & COORSTEK_HIGH_VALUE_DOMAINS:
        return "moderate"
    if industry_tags or domain_tags:
        return "low"
    return "none"


def _tag_notes(matches: list[CCRTagRuleMatch]) -> str | None:
    """Return compact notes for untagged or low-evidence records."""

    if not matches:
        return "no deterministic CCR metadata rule matched"
    return None


def _build_summary(
    paths: _IndustryPaths,
    taxonomy: CCRTagTaxonomy,
    records: list[CCRTaggedRecord],
    criteria: CCRFilterCriteria,
    filtered_records: list[CCRTaggedRecord] | None,
    filtered_jsonl_path: Path | None,
    filtered_csv_path: Path | None,
    filter_summary_path: Path | None,
) -> CCRIndustryFilterSummary:
    """Build a deterministic summary for tagging and filtering outputs."""

    tagged_total = sum(1 for record in records if record.tag_confidence_score > 0)
    return CCRIndustryFilterSummary(
        generated_at=datetime.now(timezone.utc),
        taxonomy_version=taxonomy.version,
        output_root=paths.output_root.as_posix(),
        input_jsonl_path=paths.input_jsonl_path.as_posix(),
        tagged_jsonl_path=paths.tagged_jsonl_path.as_posix(),
        tagged_csv_path=paths.tagged_csv_path.as_posix(),
        summary_path=paths.summary_path.as_posix(),
        filtered_jsonl_path=filtered_jsonl_path.as_posix() if filtered_jsonl_path else None,
        filtered_csv_path=filtered_csv_path.as_posix() if filtered_csv_path else None,
        filter_summary_path=filter_summary_path.as_posix() if filter_summary_path else None,
        records_total=len(records),
        tagged_total=tagged_total,
        untagged_total=len(records) - tagged_total,
        filtered_total=len(filtered_records) if filtered_records is not None else None,
        industry_counts=_count_tags(record.industry_tags for record in records),
        topic_counts=_count_tags(record.topic_tags for record in records),
        domain_counts=_count_tags(record.domain_tags for record in records),
        coorstek_relevance_counts=_count_values(
            record.coorstek_relevance for record in records
        ),
        confidence_counts=_count_values(record.tag_confidence_label for record in records),
        rule_match_counts=_count_rule_matches(records),
        filter_criteria=criteria.model_dump(mode="json") if criteria.is_active else None,
    )


def _count_tags(groups: Iterable[list[str]]) -> dict[str, int]:
    """Count tag occurrences across tagged records."""

    counts: dict[str, int] = {}
    for tags in groups:
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1
    return dict(sorted(counts.items()))


def _count_values(values: Iterable[str]) -> dict[str, int]:
    """Count scalar values across tagged records."""

    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _count_rule_matches(records: list[CCRTaggedRecord]) -> dict[str, int]:
    """Count how often each deterministic tagging rule matched."""

    counts: dict[str, int] = {}
    for record in records:
        for match in record.tag_rule_sources:
            counts[match.rule_id] = counts.get(match.rule_id, 0) + 1
    return dict(sorted(counts.items()))


def _write_csv(path: Path, records: list[CCRTaggedRecord], output_root: Path) -> None:
    """Write tagged CCR records to CSV with JSON-encoded list fields."""

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(TAGGED_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for record in records:
        row = record.model_dump(mode="json", exclude_none=False)
        writer.writerow({column: _csv_value(row.get(column)) for column in TAGGED_COLUMNS})
    atomic_write_text(path, buffer.getvalue(), output_root)


def _csv_value(value: object) -> object:
    """Return a stable CSV cell value for nested JSON-compatible values."""

    if isinstance(value, list | dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def _split_filter_values(values: list[str]) -> list[str]:
    """Split repeated and comma-separated CLI filter values."""

    split_values: list[str] = []
    for value in values:
        split_values.extend(part.strip() for part in value.split(",") if part.strip())
    return _sorted_unique(split_values)


def _expand_domain_filters(values: list[str]) -> list[str]:
    """Expand broad CCR domain aliases into precise taxonomy domain tags."""

    expanded: list[str] = []
    for value in values:
        expanded.extend(DOMAIN_FILTER_ALIASES.get(value, [value]))
    return _sorted_unique(expanded)


def _safe_prefix(value: str) -> str:
    """Return a filesystem-safe filtered output prefix."""

    return re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_") or DEFAULT_FILTER_PREFIX


def _sorted_unique(values: Iterable[str]) -> list[str]:
    """Return unique values in deterministic order."""

    return sorted(dict.fromkeys(values))


def _intersects(actual: list[str], required: list[str]) -> bool:
    """Return whether two string collections intersect."""

    return bool(set(actual) & set(required))


def _print_summary(summary: CCRIndustryFilterSummary) -> None:
    """Print a concise human-readable tagging summary."""

    print("CCR industry filtering summary")
    print(f"Records: {summary.records_total}")
    print(f"Tagged: {summary.tagged_total}")
    print(f"Tagged JSONL: {summary.tagged_jsonl_path}")
    print(f"Tag summary: {summary.summary_path}")
    if summary.filtered_jsonl_path:
        print(f"Filtered: {summary.filtered_total}")
        print(f"Filtered JSONL: {summary.filtered_jsonl_path}")


if __name__ == "__main__":
    raise SystemExit(main())
