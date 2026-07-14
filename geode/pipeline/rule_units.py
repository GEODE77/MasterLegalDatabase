"""Deterministic CCR rule-unit extraction from normalized source text."""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from typing import Literal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from geode.pipeline.writer import ensure_project_structure
from geode.schemas import RuleUnit
from geode.schemas.ontology import SUBJECT_TAGS
from geode.utils.file_io import (
    append_jsonl_record_atomic,
    atomic_write_json,
    atomic_write_jsonl,
    iter_jsonl,
    relative_path,
)

LOGGER = logging.getLogger(__name__)

REGULATIONS_LAYER = "02_Regulations_CCR"
RULES_DIR_NAME = "_rules"
RULE_UNITS_NAME = "rule_units.jsonl"
RULE_UNITS_QUALITY_NAME = "rule_units_quality.jsonl"
RULE_UNITS_REVIEW_QUEUE_NAME = "rule_units_review_queue.jsonl"
RULE_UNITS_REVIEW_DECISIONS_NAME = "rule_units_review_decisions.jsonl"
RULE_UNITS_REVIEW_DECISIONS_SUMMARY_NAME = "rule_units_review_decisions_summary.json"
RULE_UNITS_REVIEW_SUMMARY_NAME = "rule_units_review_summary.json"
RULE_UNITS_APPLY_PROPOSAL_NAME = "rule_units_apply_proposal.json"
RULE_UNITS_APPLY_SUMMARY_NAME = "rule_units_apply_summary.json"
RULE_UNITS_SUMMARY_NAME = "rule_units_summary.json"
MAX_SENTENCE_LENGTH = 720
DEFAULT_MAX_UNITS_PER_RECORD = 24

CRS_CITATION_RE = re.compile(
    r"(?:CRS-|(?:section|Â§|§)?\s*)?"
    r"(?P<title>\d{1,2}(?:\.\d+)?)-"
    r"(?P<article>\d{1,3}(?:\.\d+)?)"
    r"-(?P<section>\d{1,4}(?:\.\d+)?)"
    r"(?:\s*\([^)]+\))*"
    r"(?:\s*,?\s*(?:C\.?\s*R\.?\s*S\.?|Colorado\s+Revised\s+Statutes))?",
    re.IGNORECASE,
)
RULE_ACTION_RE = re.compile(
    r"(?P<subject>(?:No\s+)?[A-Za-z0-9][^.;:]{2,180}?)\s+"
    r"(?P<modal>shall not|may not|must not|is prohibited from|are prohibited from|"
    r"is required to|are required to|shall|must|may)\b"
    r"(?P<rest>[^.;]{8,520})",
    re.IGNORECASE,
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;])\s+(?=[A-Z0-9(])")
TEMPORAL_RE = re.compile(
    r"\b("
    r"within\s+\d+\s+(?:calendar\s+)?(?:days?|months?|years?)|"
    r"no later than\s+[^.;,]+|"
    r"before\s+[^.;,]+|"
    r"after\s+[^.;,]+|"
    r"annually|quarterly|monthly|weekly|daily"
    r")\b",
    re.IGNORECASE,
)
CLAUSE_RE = re.compile(
    r"\b(if|when|unless|except(?: as provided)?|provided that)\b(?P<clause>[^.;]+)",
    re.IGNORECASE,
)

SUBJECT_TAG_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("air_quality", ("air", "emission", "stationary source")),
    ("emissions", ("emission", "opacity", "pollutant")),
    ("solid_waste", ("solid waste", "landfill")),
    ("hazardous_waste", ("hazardous waste",)),
    ("water_quality", ("water quality", "discharge", "wastewater")),
    ("professional_licensing", ("license", "licensed", "licensure")),
    ("permitting", ("permit", "certificate of designation")),
    ("reporting", ("report", "notify", "submit", "filing")),
    ("recordkeeping", ("record", "retain", "maintain")),
    ("inspection", ("inspect", "inspection")),
    ("penalties", ("penalty", "fine", "sanction")),
    ("fees", ("fee", "fees")),
    ("disclosure", ("disclose", "disclosure")),
    ("enforcement", ("enforce", "violation")),
    ("public_health", ("health", "disease", "medical")),
    ("business_regulation", ("business", "vendor", "applicant")),
    ("government_operations", ("state agency", "department", "controller")),
)


class RuleUnitExtractionSummary(BaseModel):
    """Summary of a CCR rule-unit extraction run."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    output_root: str
    records_considered: int = Field(ge=0)
    records_with_units: int = Field(ge=0)
    rule_units: int = Field(ge=0)
    skipped_records: int = Field(ge=0)
    failed_records: int = Field(ge=0)
    high_quality_units: int = Field(ge=0)
    medium_quality_units: int = Field(ge=0)
    needs_review_units: int = Field(ge=0)
    dry_run: bool = False
    rule_units_path: str
    quality_path: str
    review_queue_items: int = Field(ge=0)
    review_queue_path: str
    review_summary_path: str
    summary_path: str
    failed_ids: list[str] = Field(default_factory=list)


class RuleUnitQualityRecord(BaseModel):
    """Deterministic quality score for one extracted rule unit."""

    model_config = ConfigDict(extra="forbid")

    rule_unit_id: str
    parent_regulation_id: str
    source_section: str
    quality_level: str
    overall: float = Field(ge=0.0, le=1.0)
    source_fidelity: float = Field(ge=0.0, le=1.0)
    atomicity: float = Field(ge=0.0, le=1.0)
    exception_capture: float = Field(ge=0.0, le=1.0)
    entity_clarity: float = Field(ge=0.0, le=1.0)
    temporal_precision: float = Field(ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)


class RuleUnitReviewQueueRecord(BaseModel):
    """One pending review task for a quality-gated rule unit."""

    model_config = ConfigDict(extra="forbid")

    review_id: str
    rule_unit_id: str
    parent_regulation_id: str
    source_section: str
    status: str = "pending"
    priority: str
    allowed_outcomes: list[str]
    suggested_outcomes: list[str]
    review_reason: str
    issues: list[str]
    source_sentence: str
    source_context: str | None = None
    current_rule_unit: dict[str, Any]
    quality: dict[str, Any]


class RuleUnitReviewSummary(BaseModel):
    """Summary for the needs-review rule-unit queue."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    queue_path: str
    pending_items: int = Field(ge=0)
    approve_candidates: int = Field(ge=0)
    split_candidates: int = Field(ge=0)
    revise_candidates: int = Field(ge=0)
    quarantine_candidates: int = Field(ge=0)


class RuleUnitReviewDecision(BaseModel):
    """Append-only decision for one rule-unit review task."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    decided_at: datetime
    decided_by: str = Field(min_length=1)
    review_id: str
    rule_unit_id: str
    parent_regulation_id: str
    outcome: Literal["approve", "split", "revise", "quarantine"]
    rationale: str = Field(min_length=1)
    source_sentence: str
    previous_rule_unit: dict[str, Any]
    proposed_rule_units: list[dict[str, Any]] = Field(default_factory=list)
    creates_canonical_change: bool = False


class RuleUnitReviewDecisionSummary(BaseModel):
    """Summary for the append-only review decision log."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    decision_log_path: str
    total_decisions: int = Field(ge=0)
    approved: int = Field(ge=0)
    split: int = Field(ge=0)
    revised: int = Field(ge=0)
    quarantined: int = Field(ge=0)


class RuleUnitApplyChange(BaseModel):
    """One proposed canonical change from a review decision."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    rule_unit_id: str
    outcome: str
    action: Literal["keep", "remove", "replace", "invalid"]
    proposed_rule_unit_ids: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


class RuleUnitApplyProposal(BaseModel):
    """Guarded proposal for applying review decisions to rule units."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    source_rule_units_path: str
    decision_log_path: str
    proposal_path: str
    source_rule_units: int = Field(ge=0)
    resulting_rule_units: int = Field(ge=0)
    decisions_considered: int = Field(ge=0)
    changes: list[RuleUnitApplyChange] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    ready_to_apply: bool = False


class RuleUnitApplyResult(BaseModel):
    """Result of explicitly applying review decisions to rule units."""

    model_config = ConfigDict(extra="forbid")

    applied_at: datetime
    rule_units_path: str
    proposal_path: str
    source_rule_units: int = Field(ge=0)
    resulting_rule_units: int = Field(ge=0)
    decisions_applied: int = Field(ge=0)
    changes_applied: int = Field(ge=0)
    snapshot_expected: bool = False
    applied: bool = False
    message: str


def generate_ccr_rule_units(
    output_root: Path,
    *,
    max_records: int | None = None,
    record_ids: Iterable[str] | None = None,
    max_units_per_record: int = DEFAULT_MAX_UNITS_PER_RECORD,
    dry_run: bool = False,
) -> RuleUnitExtractionSummary:
    """Generate schema-valid rule units from completed CCR Markdown records.

    Args:
        output_root: Geode project root.
        max_records: Optional cap on CCR records considered.
        record_ids: Optional explicit CCR IDs to process.
        max_units_per_record: Maximum rule units to keep per regulation.
        dry_run: When true, validate but do not write outputs.

    Returns:
        Summary describing the extraction run.
    """

    if max_records is not None and max_records < 0:
        raise ValueError("max_records cannot be negative")
    if max_units_per_record <= 0:
        raise ValueError("max_units_per_record must be positive")

    root = output_root.resolve()
    ensure_project_structure(root)
    selected_ids = {item for item in (record_ids or []) if item}
    rule_units_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_NAME
    quality_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_QUALITY_NAME
    review_queue_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_REVIEW_QUEUE_NAME
    review_summary_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_REVIEW_SUMMARY_NAME
    summary_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_SUMMARY_NAME

    units: list[RuleUnit] = []
    quality_records: list[RuleUnitQualityRecord] = []
    review_records: list[RuleUnitReviewQueueRecord] = []
    considered = 0
    skipped = 0
    failed = 0
    failed_ids: list[str] = []
    records_with_units = 0

    for record in _iter_regulation_index(root):
        record_id = str(record.get("id") or "")
        if not record_id:
            continue
        if selected_ids and record_id not in selected_ids:
            continue
        if max_records is not None and considered >= max_records:
            break
        considered += 1

        markdown_path = root / REGULATIONS_LAYER / RULES_DIR_NAME / f"{record_id}.md"
        if not markdown_path.exists():
            skipped += 1
            continue

        try:
            markdown = markdown_path.read_text(encoding="utf-8")
            extracted = extract_rule_units_from_markdown(
                record_id,
                markdown,
                index_tags=_index_subject_tags(record),
                max_units=max_units_per_record,
            )
        except Exception as exc:
            failed += 1
            failed_ids.append(record_id)
            LOGGER.warning("Rule-unit extraction failed id=%s error=%s", record_id, exc)
            continue

        if extracted:
            records_with_units += 1
            for unit in extracted:
                quality = score_rule_unit_quality(unit, markdown)
                reviewed_unit = _apply_quality_to_confidence(unit, quality)
                quality_records.append(quality)
                units.append(reviewed_unit)
                if quality.quality_level == "needs_review":
                    review_records.append(
                        _build_review_queue_record(reviewed_unit, quality, markdown)
                    )

    quality_counts = _quality_counts(quality_records)
    review_summary = _review_summary(review_records, review_queue_path, root)

    summary = RuleUnitExtractionSummary(
        generated_at=datetime.now(timezone.utc),
        output_root=root.as_posix(),
        records_considered=considered,
        records_with_units=records_with_units,
        rule_units=len(units),
        skipped_records=skipped,
        failed_records=failed,
        high_quality_units=quality_counts["high"],
        medium_quality_units=quality_counts["medium"],
        needs_review_units=quality_counts["needs_review"],
        dry_run=dry_run,
        rule_units_path=relative_path(rule_units_path, root),
        quality_path=relative_path(quality_path, root),
        review_queue_items=len(review_records),
        review_queue_path=relative_path(review_queue_path, root),
        review_summary_path=relative_path(review_summary_path, root),
        summary_path=relative_path(summary_path, root),
        failed_ids=failed_ids,
    )

    if not dry_run:
        atomic_write_jsonl(rule_units_path, units, root)
        atomic_write_jsonl(quality_path, quality_records, root)
        atomic_write_jsonl(review_queue_path, review_records, root)
        atomic_write_json(review_summary_path, review_summary, root)
        atomic_write_json(summary_path, summary, root)

    return summary


def append_rule_unit_review_decision(
    output_root: Path,
    *,
    review_id: str,
    outcome: Literal["approve", "split", "revise", "quarantine"],
    decided_by: str,
    rationale: str,
    proposed_rule_units: Iterable[dict[str, Any]] | None = None,
) -> RuleUnitReviewDecision:
    """Append one review decision without mutating queue or rule-unit files.

    Args:
        output_root: Geode project root.
        review_id: Review queue ID being decided.
        outcome: One of approve, split, revise, or quarantine.
        decided_by: Human or agent making the decision.
        rationale: Source-backed reason for the decision.
        proposed_rule_units: Optional proposed replacement units for split/revise.

    Returns:
        The validated decision record that was appended.
    """

    root = output_root.resolve()
    decision_log_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_REVIEW_DECISIONS_NAME
    summary_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_REVIEW_DECISIONS_SUMMARY_NAME
    review_item = _review_queue_item(root, review_id)
    if outcome not in review_item.allowed_outcomes:
        raise ValueError(f"outcome {outcome!r} is not allowed for {review_id}")
    if outcome in {"split", "revise", "quarantine"} and not rationale.strip():
        raise ValueError(f"rationale is required for {outcome} decisions")
    proposed = list(proposed_rule_units or [])
    if outcome in {"split", "revise"} and not proposed:
        raise ValueError(f"proposed_rule_units are required for {outcome} decisions")

    decided_at = datetime.now(timezone.utc)
    decision = RuleUnitReviewDecision(
        decision_id=_decision_id(review_id, outcome, decided_at),
        decided_at=decided_at,
        decided_by=decided_by.strip(),
        review_id=review_item.review_id,
        rule_unit_id=review_item.rule_unit_id,
        parent_regulation_id=review_item.parent_regulation_id,
        outcome=outcome,
        rationale=rationale.strip(),
        source_sentence=review_item.source_sentence,
        previous_rule_unit=review_item.current_rule_unit,
        proposed_rule_units=proposed,
    )
    append_jsonl_record_atomic(decision_log_path, decision, root)
    atomic_write_json(summary_path, _decision_summary(root, decision_log_path), root)
    return decision


def build_rule_unit_apply_proposal(
    output_root: Path,
    *,
    write: bool = True,
) -> RuleUnitApplyProposal:
    """Build a guarded proposal from review decisions without applying changes."""

    root = output_root.resolve()
    rule_units_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_NAME
    decision_log_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_REVIEW_DECISIONS_NAME
    proposal_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_APPLY_PROPOSAL_NAME
    source_units, proposed_units, changes, validation_errors = _build_apply_state(
        rule_units_path,
        decision_log_path,
    )

    proposal = RuleUnitApplyProposal(
        generated_at=datetime.now(timezone.utc),
        source_rule_units_path=relative_path(rule_units_path, root),
        decision_log_path=relative_path(decision_log_path, root),
        proposal_path=relative_path(proposal_path, root),
        source_rule_units=len(source_units),
        resulting_rule_units=len(proposed_units),
        decisions_considered=len(changes),
        changes=changes,
        validation_errors=validation_errors,
        ready_to_apply=not validation_errors,
    )
    if write:
        atomic_write_json(proposal_path, proposal, root)
    return proposal


def apply_rule_unit_review_decisions(
    output_root: Path,
    *,
    allow_noop: bool = False,
) -> RuleUnitApplyResult:
    """Apply validated review decisions to `rule_units.jsonl` with snapshot protection."""

    root = output_root.resolve()
    rule_units_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_NAME
    summary_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_APPLY_SUMMARY_NAME
    decision_log_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_REVIEW_DECISIONS_NAME
    source_units, proposed_units, changes, validation_errors = _build_apply_state(
        rule_units_path,
        decision_log_path,
    )
    proposal = build_rule_unit_apply_proposal(root, write=True)
    actionable_changes = [
        change for change in changes if change.action in {"remove", "replace"}
    ]

    if validation_errors:
        raise ValueError("cannot apply invalid proposal; inspect rule_units_apply_proposal.json")
    if not changes and not allow_noop:
        raise ValueError("no review decisions to apply")
    if not actionable_changes and not allow_noop:
        raise ValueError("proposal has no canonical changes to apply")
    if not actionable_changes:
        result = RuleUnitApplyResult(
            applied_at=datetime.now(timezone.utc),
            rule_units_path=relative_path(rule_units_path, root),
            proposal_path=proposal.proposal_path,
            source_rule_units=len(source_units),
            resulting_rule_units=len(proposed_units),
            decisions_applied=len(changes),
            changes_applied=0,
            snapshot_expected=False,
            applied=False,
            message="No canonical rule-unit changes were required.",
        )
        atomic_write_json(summary_path, result, root)
        return result

    had_existing_rule_units = rule_units_path.exists()
    ordered_units = [proposed_units[unit_id] for unit_id in sorted(proposed_units)]
    atomic_write_jsonl(rule_units_path, ordered_units, root)
    result = RuleUnitApplyResult(
        applied_at=datetime.now(timezone.utc),
        rule_units_path=relative_path(rule_units_path, root),
        proposal_path=proposal.proposal_path,
        source_rule_units=len(source_units),
        resulting_rule_units=len(proposed_units),
        decisions_applied=len(changes),
        changes_applied=len(actionable_changes),
        snapshot_expected=had_existing_rule_units,
        applied=True,
        message="Applied review decisions to rule_units.jsonl.",
    )
    atomic_write_json(summary_path, result, root)
    return result


def extract_rule_units_from_markdown(
    parent_regulation_id: str,
    markdown: str,
    *,
    index_tags: Iterable[str] | None = None,
    max_units: int = DEFAULT_MAX_UNITS_PER_RECORD,
) -> list[RuleUnit]:
    """Extract schema-valid rule units from one CCR Markdown document."""

    base_tags = list(index_tags or [])
    seen_actions: set[str] = set()
    units: list[RuleUnit] = []

    for block in _iter_source_blocks(_strip_frontmatter(markdown)):
        if _is_excluded_section(block.section):
            continue
        for sentence in _split_sentences(block.text):
            candidate = _build_rule_unit(
                parent_regulation_id,
                block.section,
                sentence,
                len(units) + 1,
                base_tags,
            )
            if candidate is None:
                continue
            dedupe_key = candidate.action_required.casefold()
            if dedupe_key in seen_actions:
                continue
            seen_actions.add(dedupe_key)
            units.append(candidate)
            if len(units) >= max_units:
                return units

    return units


def score_rule_unit_quality(unit: RuleUnit, source_text: str) -> RuleUnitQualityRecord:
    """Score one rule unit against deterministic quality checks."""

    source_score, source_issues = _score_source_fidelity(unit, source_text)
    atomicity_score, atomicity_issues = _score_atomicity(unit.action_required)
    exception_score, exception_issues = _score_exception_capture(unit)
    entity_score, entity_issues = _score_entity_clarity(unit.regulated_entity)
    temporal_score, temporal_issues = _score_temporal_precision(unit)
    scores = [
        source_score,
        atomicity_score,
        exception_score,
        entity_score,
        temporal_score,
    ]
    overall = round(sum(scores) / len(scores), 2)
    issues = [
        *source_issues,
        *atomicity_issues,
        *exception_issues,
        *entity_issues,
        *temporal_issues,
    ]
    critical_review = source_score <= 0.3 or entity_score <= 0.55
    return RuleUnitQualityRecord(
        rule_unit_id=unit.id,
        parent_regulation_id=unit.parent_regulation_id,
        source_section=unit.source_section,
        quality_level=_quality_level(overall, issues, critical_review),
        overall=overall,
        source_fidelity=source_score,
        atomicity=atomicity_score,
        exception_capture=exception_score,
        entity_clarity=entity_score,
        temporal_precision=temporal_score,
        issues=issues,
    )


def _score_source_fidelity(unit: RuleUnit, source_text: str) -> tuple[float, list[str]]:
    """Score whether the extracted action appears verbatim in the source."""

    source = _normalize_for_match(source_text)
    action = _normalize_for_match(unit.action_required)
    if action and action in source:
        return 1.0, []
    compact_action = re.sub(r"[^a-z0-9]+", "", action)
    compact_source = re.sub(r"[^a-z0-9]+", "", source)
    if compact_action and compact_action in compact_source:
        return 0.9, ["source text match required normalization"]
    return 0.2, ["action text was not found in the source document"]


def _score_atomicity(action: str) -> tuple[float, list[str]]:
    """Score whether one rule unit appears to contain one legal action."""

    issues: list[str] = []
    score = 1.0
    modal_count = len(
        re.findall(
            r"\b(shall|must|may|shall not|may not|is required to|are required to)\b",
            action,
            flags=re.IGNORECASE,
        )
    )
    if modal_count > 1:
        score -= 0.35
        issues.append("possible multiple legal actions")
    if ";" in action:
        score -= 0.2
        issues.append("semicolon may join multiple requirements")
    if len(action) > 420:
        score -= 0.2
        issues.append("long action text should be reviewed for atomicity")
    if re.search(r"\b(and|or)\s+(shall|must|may)\b", action, flags=re.IGNORECASE):
        score -= 0.2
        issues.append("coordinated modal language may hide another rule")
    return round(max(score, 0.2), 2), issues


def _score_exception_capture(unit: RuleUnit) -> tuple[float, list[str]]:
    """Score whether visible exception language was captured."""

    action = unit.action_required
    has_exception_language = bool(
        re.search(r"\b(unless|except|exemption)\b", action, flags=re.IGNORECASE)
    )
    if not has_exception_language:
        return 1.0, []
    if unit.exceptions:
        return 0.92, []
    return 0.35, ["exception language appears in source but no exception was captured"]


def _score_entity_clarity(entity: str) -> tuple[float, list[str]]:
    """Score whether the regulated entity is usable without broad interpretation."""

    issues: list[str] = []
    score = 1.0
    words = entity.split()
    vague_terms = {
        "person",
        "entity",
        "party",
        "parties",
        "someone",
        "anyone",
    }
    if len(words) == 1 or entity.casefold() in vague_terms:
        score -= 0.45
        issues.append("regulated entity is too broad")
    if len(entity) > 180:
        score -= 0.25
        issues.append("regulated entity phrase is unusually long")
    if re.search(r"\b(the following|this section|these rules)\b", entity, re.IGNORECASE):
        score -= 0.35
        issues.append("regulated entity may be front-matter text")
    return round(max(score, 0.2), 2), issues


def _score_temporal_precision(unit: RuleUnit) -> tuple[float, list[str]]:
    """Score whether temporal language is preserved when present."""

    action_has_temporal = bool(TEMPORAL_RE.search(unit.action_required))
    if not action_has_temporal:
        return 1.0, []
    if unit.temporal:
        return 1.0, []
    return 0.4, ["temporal language appears in source but was not captured"]


def _quality_level(overall: float, issues: list[str], critical_review: bool) -> str:
    """Return a small quality label for the rule-unit report."""

    if critical_review:
        return "needs_review"
    if overall >= 0.86 and not issues:
        return "high"
    if overall >= 0.68:
        return "medium"
    return "needs_review"


def _quality_counts(records: list[RuleUnitQualityRecord]) -> dict[str, int]:
    """Return quality-level counts for a run summary."""

    counts = {"high": 0, "medium": 0, "needs_review": 0}
    for record in records:
        counts[record.quality_level] = counts.get(record.quality_level, 0) + 1
    return counts


def _apply_quality_to_confidence(unit: RuleUnit, quality: RuleUnitQualityRecord) -> RuleUnit:
    """Return a rule unit whose confidence reflects quality-gate results."""

    payload = unit.model_dump(mode="json")
    confidence = payload["confidence"]
    original = float(confidence["overall"])
    confidence["overall"] = round(min(original, quality.overall), 2)
    confidence["fields"]["quality_gate"] = quality.overall
    confidence["fields"]["source_fidelity"] = quality.source_fidelity
    confidence["fields"]["atomicity"] = quality.atomicity
    confidence["fields"]["exception_capture"] = quality.exception_capture
    confidence["fields"]["entity_clarity"] = quality.entity_clarity
    confidence["fields"]["temporal_precision"] = quality.temporal_precision
    confidence["route"] = "deterministic_ccr_rule_unit_v1_quality_gate"
    return RuleUnit.model_validate(payload)


def _build_review_queue_record(
    unit: RuleUnit,
    quality: RuleUnitQualityRecord,
    source_text: str,
) -> RuleUnitReviewQueueRecord:
    """Build one pending review task without changing the source rule unit."""

    suggested = _suggested_review_outcomes(quality.issues)
    return RuleUnitReviewQueueRecord(
        review_id=f"RUR-{unit.id}",
        rule_unit_id=unit.id,
        parent_regulation_id=unit.parent_regulation_id,
        source_section=unit.source_section,
        priority=_review_priority(quality),
        allowed_outcomes=["approve", "split", "revise", "quarantine"],
        suggested_outcomes=suggested,
        review_reason=_review_reason(quality),
        issues=quality.issues,
        source_sentence=unit.action_required,
        source_context=_source_context(source_text, unit.action_required),
        current_rule_unit=unit.model_dump(mode="json"),
        quality=quality.model_dump(mode="json"),
    )


def _suggested_review_outcomes(issues: list[str]) -> list[str]:
    """Return review outcomes suggested by quality-gate issues."""

    outcomes: list[str] = []
    joined = " ".join(issues).casefold()
    if "source" in joined:
        outcomes.append("quarantine")
    if "multiple legal actions" in joined or "atomicity" in joined:
        outcomes.append("split")
    if "exception" in joined or "temporal" in joined or "regulated entity" in joined:
        outcomes.append("revise")
    if not outcomes:
        outcomes.append("approve")
    return sorted(dict.fromkeys(outcomes), key=["approve", "split", "revise", "quarantine"].index)


def _review_priority(quality: RuleUnitQualityRecord) -> str:
    """Return a small priority label for review sorting."""

    if quality.source_fidelity <= 0.3 or quality.entity_clarity <= 0.55:
        return "high"
    if quality.atomicity <= 0.65 or quality.exception_capture <= 0.4:
        return "medium"
    return "low"


def _review_reason(quality: RuleUnitQualityRecord) -> str:
    """Return a concise human-readable reason for review."""

    if quality.issues:
        return "; ".join(quality.issues)
    return "Quality score requires review before high-confidence use."


def _source_context(source_text: str, sentence: str) -> str | None:
    """Return nearby source text for one review item."""

    normalized_source = " ".join(_strip_frontmatter(source_text).split())
    normalized_sentence = " ".join(sentence.split())
    index = normalized_source.find(normalized_sentence)
    if index < 0:
        return None
    start = max(0, index - 220)
    end = min(len(normalized_source), index + len(normalized_sentence) + 220)
    return normalized_source[start:end].strip()


def _review_summary(
    records: list[RuleUnitReviewQueueRecord],
    queue_path: Path,
    root: Path,
) -> RuleUnitReviewSummary:
    """Return a summary of the generated review queue."""

    return RuleUnitReviewSummary(
        generated_at=datetime.now(timezone.utc),
        queue_path=relative_path(queue_path, root),
        pending_items=len(records),
        approve_candidates=sum("approve" in record.suggested_outcomes for record in records),
        split_candidates=sum("split" in record.suggested_outcomes for record in records),
        revise_candidates=sum("revise" in record.suggested_outcomes for record in records),
        quarantine_candidates=sum(
            "quarantine" in record.suggested_outcomes for record in records
        ),
    )


def _review_queue_item(root: Path, review_id: str) -> RuleUnitReviewQueueRecord:
    """Return one review queue item by ID."""

    queue_path = root / REGULATIONS_LAYER / "_meta" / RULE_UNITS_REVIEW_QUEUE_NAME
    if not queue_path.exists():
        raise ValueError("review queue has not been generated")
    for row in iter_jsonl(queue_path):
        if row.get("review_id") == review_id:
            return RuleUnitReviewQueueRecord.model_validate(row)
    raise ValueError(f"unknown review_id: {review_id}")


def _decision_id(review_id: str, outcome: str, decided_at: datetime) -> str:
    """Return a deterministic-looking decision ID for one append event."""

    stamp = decided_at.strftime("%Y%m%dT%H%M%S%fZ")
    return f"RUD-{stamp}-{review_id}-{outcome}"


def _decision_summary(root: Path, decision_log_path: Path) -> RuleUnitReviewDecisionSummary:
    """Return current counts for the append-only decision log."""

    decisions = list(_iter_review_decisions(decision_log_path))
    return RuleUnitReviewDecisionSummary(
        generated_at=datetime.now(timezone.utc),
        decision_log_path=relative_path(decision_log_path, root),
        total_decisions=len(decisions),
        approved=sum(decision.outcome == "approve" for decision in decisions),
        split=sum(decision.outcome == "split" for decision in decisions),
        revised=sum(decision.outcome == "revise" for decision in decisions),
        quarantined=sum(decision.outcome == "quarantine" for decision in decisions),
    )


def _iter_review_decisions(path: Path) -> Iterator[RuleUnitReviewDecision]:
    """Yield validated review decisions from the append-only log."""

    if not path.exists():
        return
    for row in iter_jsonl(path):
        yield RuleUnitReviewDecision.model_validate(row)


def _read_rule_unit_records(path: Path) -> dict[str, RuleUnit]:
    """Read current rule-unit records keyed by ID."""

    if not path.exists():
        return {}
    records: dict[str, RuleUnit] = {}
    for row in iter_jsonl(path):
        unit = RuleUnit.model_validate(row)
        records[unit.id] = unit
    return records


def _build_apply_state(
    rule_units_path: Path,
    decision_log_path: Path,
) -> tuple[dict[str, RuleUnit], dict[str, RuleUnit], list[RuleUnitApplyChange], list[str]]:
    """Return source records, proposed records, changes, and validation errors."""

    source_units = _read_rule_unit_records(rule_units_path)
    proposed_units = dict(source_units)
    changes: list[RuleUnitApplyChange] = []
    validation_errors: list[str] = []

    for decision in _latest_decisions_by_rule(decision_log_path).values():
        change, replacements = _change_from_decision(decision, proposed_units)
        changes.append(change)
        validation_errors.extend(change.validation_errors)

        if change.validation_errors:
            continue
        if change.action == "remove":
            proposed_units.pop(decision.rule_unit_id, None)
        elif change.action == "replace":
            proposed_units.pop(decision.rule_unit_id, None)
            for replacement in replacements:
                proposed_units[replacement.id] = replacement

    for unit_id, unit in proposed_units.items():
        try:
            RuleUnit.model_validate(unit.model_dump(mode="json"))
        except Exception as exc:
            validation_errors.append(f"{unit_id}: {exc}")

    return source_units, proposed_units, changes, validation_errors


def _latest_decisions_by_rule(path: Path) -> dict[str, RuleUnitReviewDecision]:
    """Return the newest review decision for each rule-unit ID."""

    latest: dict[str, RuleUnitReviewDecision] = {}
    for decision in _iter_review_decisions(path):
        current = latest.get(decision.rule_unit_id)
        if current is None or decision.decided_at >= current.decided_at:
            latest[decision.rule_unit_id] = decision
    return latest


def _change_from_decision(
    decision: RuleUnitReviewDecision,
    current_units: dict[str, RuleUnit],
) -> tuple[RuleUnitApplyChange, list[RuleUnit]]:
    """Build one proposed change from a review decision."""

    errors: list[str] = []
    replacements: list[RuleUnit] = []
    if decision.rule_unit_id not in current_units:
        errors.append("target rule unit is not present in current rule_units.jsonl")

    if decision.outcome == "approve":
        return (
            RuleUnitApplyChange(
                decision_id=decision.decision_id,
                rule_unit_id=decision.rule_unit_id,
                outcome=decision.outcome,
                action="keep" if not errors else "invalid",
                validation_errors=errors,
            ),
            replacements,
        )

    if decision.outcome == "quarantine":
        return (
            RuleUnitApplyChange(
                decision_id=decision.decision_id,
                rule_unit_id=decision.rule_unit_id,
                outcome=decision.outcome,
                action="remove" if not errors else "invalid",
                validation_errors=errors,
            ),
            replacements,
        )

    for index, payload in enumerate(decision.proposed_rule_units, start=1):
        try:
            replacement = RuleUnit.model_validate(payload)
        except Exception as exc:
            errors.append(f"replacement {index} failed validation: {exc}")
            continue
        if replacement.parent_regulation_id != decision.parent_regulation_id:
            errors.append(f"replacement {replacement.id} has a different parent regulation")
            continue
        replacements.append(replacement)

    if not replacements:
        errors.append("no valid proposed replacement rule units")

    return (
        RuleUnitApplyChange(
            decision_id=decision.decision_id,
            rule_unit_id=decision.rule_unit_id,
            outcome=decision.outcome,
            action="replace" if not errors else "invalid",
            proposed_rule_unit_ids=[replacement.id for replacement in replacements],
            validation_errors=errors,
        ),
        replacements,
    )


def _normalize_for_match(value: str) -> str:
    """Normalize text for source-fidelity comparison."""

    return " ".join(value.casefold().split())


class _SourceBlock(BaseModel):
    """A paragraph-like source block tied to the nearest visible heading."""

    section: str
    text: str


def _iter_regulation_index(root: Path) -> Iterator[dict[str, Any]]:
    """Yield CCR index rows without loading the whole index file."""

    index_path = root / REGULATIONS_LAYER / "_index.jsonl"
    if not index_path.exists():
        return
    yield from iter_jsonl(index_path)


def _strip_frontmatter(markdown: str) -> str:
    """Remove YAML frontmatter from a Markdown document when present."""

    return re.sub(r"\A---[\s\S]*?---\s*", "", markdown, count=1).strip()


def _iter_source_blocks(text: str) -> Iterator[_SourceBlock]:
    """Yield source text blocks with a conservative section label."""

    section = "Source text"
    buffer: list[str] = []

    for raw_line in text.splitlines():
        line = " ".join(raw_line.strip().split())
        if not line or _is_noise_line(line):
            if buffer:
                yield _SourceBlock(section=section, text=" ".join(buffer))
                buffer = []
            continue
        if _is_heading(line):
            if buffer:
                yield _SourceBlock(section=section, text=" ".join(buffer))
                buffer = []
            section = _clean_heading(line)
            continue
        buffer.append(line)
        if sum(len(item) for item in buffer) > 2200:
            yield _SourceBlock(section=section, text=" ".join(buffer))
            buffer = []

    if buffer:
        yield _SourceBlock(section=section, text=" ".join(buffer))


def _split_sentences(text: str) -> Iterator[str]:
    """Split a source block into candidate source sentences."""

    for sentence in SENTENCE_SPLIT_RE.split(text):
        normalized = " ".join(sentence.split()).strip()
        if 45 <= len(normalized) <= MAX_SENTENCE_LENGTH:
            yield normalized


def _build_rule_unit(
    parent_regulation_id: str,
    source_section: str,
    sentence: str,
    sequence: int,
    base_tags: list[str],
) -> RuleUnit | None:
    """Build one validated rule unit when a sentence has a clear rule shape."""

    match = RULE_ACTION_RE.search(sentence)
    if match is None:
        return None

    subject = _clean_subject(match.group("subject"))
    if not _is_specific_subject(subject):
        return None

    rule_type = _rule_type(match.group("modal"), sentence)
    tags = _subject_tags(sentence, base_tags)
    confidence = _confidence(rule_type, subject, tags, sentence)
    payload = {
        "entity_type": "rule_unit",
        "id": f"{parent_regulation_id}_RU_{sequence:04d}",
        "parent_regulation_id": parent_regulation_id,
        "source_section": source_section[:240],
        "rule_type": rule_type,
        "regulated_entity": subject,
        "action_required": sentence,
        "conditions": _clauses(sentence, include_exceptions=False),
        "exceptions": _clauses(sentence, include_exceptions=True),
        "enabling_statute": _extract_crs_ids(sentence),
        "temporal": _temporal(sentence),
        "penalties": _penalties(sentence),
        "plain_english_summary": sentence,
        "subject_tags": tags,
        "confidence": {
            "overall": confidence,
            "fields": {
                "regulated_entity": 0.74,
                "action_required": 0.86,
                "source_section": 0.72,
                "subject_tags": 0.58 if tags else 0.0,
            },
            "route": "deterministic_ccr_rule_unit_v1",
        },
    }
    return RuleUnit.model_validate(payload)


def _clean_subject(value: str) -> str:
    """Return a compact regulated-entity phrase from a source sentence."""

    subject = " ".join(value.split()).strip(" ,:-")
    subject = re.sub(r"^(and|or|but|provided that)\s+", "", subject, flags=re.IGNORECASE)
    return subject[:240]


def _is_specific_subject(subject: str) -> bool:
    """Return true when the subject is specific enough to retain."""

    if len(subject) < 4:
        return False
    vague = {"it", "this", "that", "there", "these", "those"}
    if subject.casefold() in vague:
        return False
    excluded_fragments = (
        "following general definitions",
        "following definitions",
        "purpose of these",
        "statutory authority",
    )
    if any(fragment in subject.casefold() for fragment in excluded_fragments):
        return False
    return any(character.isalpha() for character in subject)


def _rule_type(modal: str, sentence: str) -> str:
    """Map source modal language to the controlled rule-type vocabulary."""

    lower = f"{modal} {sentence}".casefold()
    if sentence.strip().casefold().startswith("no ") or "shall not" in lower:
        return "prohibition"
    if "may not" in lower or "prohibited" in lower:
        return "prohibition"
    if "penalty" in lower or "fine" in lower:
        return "penalty"
    if "report" in lower or "notify" in lower or "submit" in lower:
        return "reporting"
    if "may" in modal.casefold():
        return "permission"
    if "condition" in lower or "if " in lower or "when " in lower:
        return "condition"
    return "obligation"


def _subject_tags(sentence: str, base_tags: list[str]) -> list[str]:
    """Return controlled subject tags from source text and index tags."""

    lower = sentence.casefold()
    tags = [
        tag
        for tag, patterns in SUBJECT_TAG_PATTERNS
        if tag in SUBJECT_TAGS and any(pattern in lower for pattern in patterns)
    ]
    for tag in base_tags:
        if tag in SUBJECT_TAGS and tag not in tags:
            tags.append(tag)
    if not tags:
        tags.append("compliance")
    return tags[:8]


def _index_subject_tags(record: dict[str, Any]) -> list[str]:
    """Return controlled tags already present on a CCR index row."""

    tags = record.get("tags")
    if not isinstance(tags, list):
        return []
    return [str(tag) for tag in tags if str(tag) in SUBJECT_TAGS]


def _confidence(rule_type: str, subject: str, tags: list[str], sentence: str) -> float:
    """Return a conservative extraction confidence score."""

    score = 0.62
    if rule_type in {"obligation", "prohibition", "reporting"}:
        score += 0.08
    if len(subject.split()) >= 2:
        score += 0.04
    if tags:
        score += 0.03
    if CRS_CITATION_RE.search(sentence):
        score += 0.03
    return round(min(score, 0.82), 2)


def _clauses(sentence: str, *, include_exceptions: bool) -> list[str]:
    """Return exact conditional or exception clauses from the sentence."""

    clauses: list[str] = []
    for match in CLAUSE_RE.finditer(sentence):
        keyword = match.group(1).casefold()
        is_exception = keyword.startswith(("unless", "except"))
        if is_exception != include_exceptions:
            continue
        clause = f"{match.group(1)}{match.group('clause')}".strip(" ,")
        clauses.append(clause[:260])
    return clauses


def _temporal(sentence: str) -> str | None:
    """Return an exact temporal phrase from the source sentence when present."""

    match = TEMPORAL_RE.search(sentence)
    return match.group(1) if match else None


def _penalties(sentence: str) -> list[str]:
    """Return the source sentence as penalty evidence when penalty language appears."""

    lower = sentence.casefold()
    if "penalty" in lower or "fine" in lower or "sanction" in lower:
        return [sentence]
    return []


def _extract_crs_ids(text: str) -> list[str]:
    """Extract canonical CRS IDs from source text."""

    ids: list[str] = []
    for match in CRS_CITATION_RE.finditer(text):
        candidate = f"CRS-{match.group('title')}-{match.group('article')}-{match.group('section')}"
        if candidate not in ids:
            ids.append(candidate)
    return ids


def _is_noise_line(line: str) -> bool:
    """Return true for page numbers and common CCR footer fragments."""

    if line.isdigit():
        return True
    return line in {
        "Code of Colorado Regulations",
        "Secretary of State",
        "State of Colorado",
        "CODE OF COLORADO REGULATIONS",
    }


def _is_excluded_section(section: str) -> bool:
    """Return true for front-matter sections that are poor rule-unit sources."""

    normalized = section.casefold()
    excluded = (
        "definitions",
        "purpose",
        "statutory authority",
        "editor",
        "history",
        "basis and purpose",
    )
    return any(item in normalized for item in excluded)


def _is_heading(line: str) -> bool:
    """Return true when a line looks like a source heading."""

    return (
        line.startswith("#### ")
        or bool(re.match(r"^(PART|RULE|REGULATION|APPENDIX)\s+[A-Z0-9]", line))
        or bool(re.match(r"^[A-Z][A-Z\s,;()/-]{8,}$", line))
        or bool(re.match(r"^([IVXLCDM]+\.|[A-Z]\.|[0-9]+\.)\s+[A-Z0-9]", line))
    )


def _clean_heading(line: str) -> str:
    """Return display text for a source heading."""

    return re.sub(r"^#+\s*", "", line).strip()[:240] or "Source text"


def build_parser() -> argparse.ArgumentParser:
    """Build the rule-unit CLI parser."""

    parser = argparse.ArgumentParser(description="Generate and review CCR rule units.")
    parser.add_argument(
        "--output-root",
        "--root",
        dest="output_root",
        type=Path,
        default=Path.cwd(),
    )
    parser.add_argument("--max-records", type=int)
    parser.add_argument("--record-id", action="append", default=[])
    parser.add_argument("--max-units-per-record", type=int, default=DEFAULT_MAX_UNITS_PER_RECORD)
    parser.add_argument("--build-apply-proposal", action="store_true")
    parser.add_argument("--apply-decisions", action="store_true")
    parser.add_argument("--allow-noop-apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the rule-unit extraction CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.apply_decisions:
            result = apply_rule_unit_review_decisions(
                args.output_root,
                allow_noop=args.allow_noop_apply,
            )
            if args.json:
                print(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))
            else:
                print(result.message)
                print(f"Decisions applied: {result.decisions_applied}")
                print(f"Changes applied: {result.changes_applied}")
            return 0
        if args.build_apply_proposal:
            proposal = build_rule_unit_apply_proposal(args.output_root, write=not args.dry_run)
            if args.json:
                print(json.dumps(proposal.model_dump(mode="json"), indent=2, sort_keys=True))
            else:
                print(f"Decisions considered: {proposal.decisions_considered}")
                print(f"Changes: {len(proposal.changes)}")
                print(f"Ready to apply: {proposal.ready_to_apply}")
            return 0 if proposal.ready_to_apply else 2
        summary = generate_ccr_rule_units(
            args.output_root,
            max_records=args.max_records,
            record_ids=args.record_id,
            max_units_per_record=args.max_units_per_record,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        print(f"Rule units: {summary.rule_units}")
        print(f"Records considered: {summary.records_considered}")
        print(f"Output: {summary.rule_units_path}")
    return 0 if summary.failed_records == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
