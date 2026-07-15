"""Retrieval backend interfaces and implementations."""

from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Protocol

from geode.orchestration.contracts import (
    AuthorityLevel,
    Citation,
    Evidence,
    GraphLink,
    Provenance,
    QueryState,
    RetrievalStep,
)
from geode.utils.file_io import iter_jsonl


MAX_CANDIDATES = 50
STOPWORDS = {
    "what", "which", "where", "when", "does", "are", "the", "for", "and", "with",
    "that", "this", "from", "into", "apply", "applies", "requirements", "requirement",
}
GENERIC_QUERY_TERMS = {
    "apply", "applies", "county", "district", "facility", "law", "laws", "local",
    "municipal", "requirements", "requirement", "rules", "rule", "state",
}


class RetrievalBackend(Protocol):
    """Backend interface for source retrieval."""

    def search(self, state: QueryState, step: RetrievalStep) -> list[Evidence]:
        """Return candidate evidence for one planned retrieval step."""

    def traverse(self, evidence: Evidence, relationships: list[str]) -> list[Evidence]:
        """Return candidate evidence reached by graph traversal."""


class FixtureRetrievalBackend:
    """In-memory backend for deterministic tests."""

    def __init__(
        self,
        evidence: list[Evidence],
        graph_links: list[GraphLink] | None = None,
    ) -> None:
        """Create a fixture backend."""

        self.evidence = evidence
        self.graph_links = graph_links or []

    def search(self, state: QueryState, step: RetrievalStep) -> list[Evidence]:
        """Return fixture evidence matching the planned category or targets."""

        del state
        return [
            item
            for item in self.evidence
            if item.category_id == step.category_id
            or item.citation.canonical_id in step.targets
            or any(target in item.provenance.source_id for target in step.targets)
        ]

    def traverse(self, evidence: Evidence, relationships: list[str]) -> list[Evidence]:
        """Follow fixture graph links from one evidence record."""

        source_id = evidence.citation.canonical_id or evidence.provenance.source_id
        target_ids = [
            link.target_id
            for link in self.graph_links
            if link.source_id == source_id and link.relationship in relationships
        ]
        reached: list[Evidence] = []
        for item in self.evidence:
            canonical_id = item.citation.canonical_id or item.provenance.source_id
            if canonical_id in target_ids:
                reached.append(
                    item.model_copy(
                        update={
                            "relationship_path": [
                                *evidence.relationship_path,
                                source_id,
                                canonical_id,
                            ]
                        }
                    )
                )
        return reached


class LocalKnowledgeRetrievalBackend:
    """Read-only retrieval backend over local Geode catalog files."""

    def __init__(self, root: Path | None = None) -> None:
        """Create a local retrieval backend."""

        self.root = (root or Path.cwd()).resolve()

    def search(self, state: QueryState, step: RetrievalStep) -> list[Evidence]:
        """Search local retrieval catalog rows for planned targets and query terms."""

        catalog_path = self.root / "_CONTROL_PLANE" / "RETRIEVAL_CATALOG.jsonl"
        if not catalog_path.exists():
            return []
        scored_candidates: list[tuple[float, Evidence]] = []
        for row in iter_jsonl(catalog_path):
            entity_type = str(row.get("entity_type") or "")
            if entity_type in {"rule_unit", "local_rule"} and row.get("semantic_status") in {
                "source_preservation_only",
                "needs_review",
            }:
                continue
            if step.targets and entity_type not in step.targets:
                continue
            if not _matches_authority(row, step.authority_level.value):
                continue
            if not _matches_location(row, state):
                continue
            metadata_score = _query_score(row, state)
            if metadata_score <= 0:
                continue
            source_id = str(row.get("id") or row.get("citation") or "")
            if not source_id:
                continue
            source_record = _load_source_record(self.root, row)
            source_text = _select_source_text(source_record, row, state)
            if not source_text:
                source_text = str(row.get("retrieval_text") or row.get("title") or source_id)
            score = _query_score(row, state, source_text)
            if score <= 0:
                continue
            scored_candidates.append(
                (
                    score,
                    Evidence(
                    evidence_id=f"candidate-{source_id}",
                    text=source_text,
                    citation=Citation(
                        citation_text=str(row.get("citation") or source_id),
                        canonical_id=source_id,
                        authority_level=step.authority_level,
                    ),
                    provenance=Provenance(
                        source_id=source_id,
                        source_path=_evidence_source_path(row, catalog_path),
                        source_url=row.get("source_url"),
                        retrieved_at=_parse_datetime(row.get("last_updated")),
                        source_hash=row.get("sha256"),
                        source_version=str(row.get("last_updated") or "current"),
                        passage=_passage_from_row(row, source_text, source_record),
                    ),
                    confidence=float(row.get("confidence") or 0.5),
                    category_id=step.category_id,
                    source_category=str(row.get("source_category") or "") or None,
                    semantic_status=str(row.get("semantic_status") or "") or None,
                    answer_safe=(
                        entity_type != "rule_unit"
                        or str(row.get("semantic_status") or "") == "semantic_ready"
                    ),
                    applicability=_applicability(row, state),
                    selection_reasons=_selection_reasons(row, state, score),
                    is_candidate=True,
                    ),
                )
            )
        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        return [candidate for _, candidate in scored_candidates[:MAX_CANDIDATES]]

    def traverse(self, evidence: Evidence, relationships: list[str]) -> list[Evidence]:
        """Follow validated crosswalk rows and load their source passages."""

        source_id = evidence.citation.canonical_id or evidence.provenance.source_id
        crosswalk_dir = self.root / "_CROSSWALKS"
        if not crosswalk_dir.exists():
            return []
        reached: list[Evidence] = []
        for path in crosswalk_dir.glob("*.jsonl"):
            for row in iter_jsonl(path):
                if str(row.get("source_id")) != source_id:
                    continue
                if relationships and str(row.get("relationship")) not in relationships:
                    continue
                target_id = str(row.get("target_id") or "")
                if not target_id:
                    continue
                target = _catalog_row_for_id(self.root, target_id)
                if target is None:
                    continue
                target_status = str(target.get("semantic_status") or "")
                if target_status in {"source_preservation_only", "needs_review"}:
                    continue
                source_record = _load_source_record(self.root, target)
                source_text = _select_source_text(source_record, target, None)
                reached.append(
                    Evidence(
                        evidence_id=f"candidate-{target_id}",
                        text=source_text or str(row.get("source_evidence") or target_id),
                        citation=Citation(
                            citation_text=str(target.get("citation") or target_id),
                            canonical_id=target_id,
                            authority_level=AuthorityLevel(str(target.get("authority_level") or "state")),
                        ),
                        provenance=Provenance(
                            source_id=target_id,
                            source_path=_evidence_source_path(target, path),
                            source_url=target.get("source_url"),
                            source_hash=target.get("sha256"),
                            source_version=str(target.get("last_updated") or "unknown"),
                            passage=_passage_from_row(target, source_text, source_record),
                        ),
                        confidence=float(row.get("confidence") or target.get("confidence") or 0.5),
                        category_id=evidence.category_id,
                        source_category=str(target.get("source_category") or "") or None,
                        semantic_status=str(target.get("semantic_status") or "") or None,
                        answer_safe=(
                            target_status not in {"source_preservation_only", "needs_review"}
                        ),
                        is_candidate=True,
                        relationship_path=[*evidence.relationship_path, source_id, target_id],
                    )
                )
        return reached


def _matches_authority(row: dict[str, object], authority_level: str) -> bool:
    """Keep evidence at the authority level requested by the plan."""

    row_level = str(row.get("authority_level") or "")
    if row_level:
        return row_level == authority_level
    return authority_level not in {"county", "district", "municipal"}


def _matches_location(row: dict[str, object], state: QueryState) -> bool:
    """Keep local evidence within the resolved county or district."""

    jurisdiction = state.jurisdiction
    if jurisdiction is None:
        return True
    authority_id = _normalize_place(row.get("authority_id"))
    if jurisdiction.district and authority_id:
        district = _normalize_place(jurisdiction.district)
        authority_name = _normalize_place(row.get("authority_name"))
        if (
            district not in authority_id.casefold()
            and authority_id.casefold() not in district
            and district not in authority_name
            and authority_name not in district
        ):
            return False
    counties = {_normalize_place(value) for value in (row.get("county_names") or []) if value}
    requested_county = _normalize_place(jurisdiction.county)
    local_level = str(row.get("authority_level") or "") in {
        "county",
        "district",
        "municipal",
    }
    if requested_county and local_level:
        if not counties or requested_county not in counties:
            return False
    return True


def _query_score(row: dict[str, object], state: QueryState, source_text: str = "") -> float:
    """Score a catalog row using exact IDs, categories, and normalized query terms."""

    query = (state.intent.normalized_query or state.intent.raw_query).casefold()
    if not query:
        return 1.0
    identifier = " ".join(
        str(row.get(key) or "") for key in ("id", "citation", "source_category")
    ).casefold()
    if any(token and token in query for token in identifier.split() if len(token) > 5):
        return 100.0
    haystack = " ".join(
        str(row.get(key) or "")
        for key in (
            "retrieval_text",
            "title",
            "citation",
            "authority_type",
            "district_family",
            "source_category",
            "county_names",
        )
    ).casefold()
    terms = {
        term
        for term in re.findall(r"[a-z0-9][a-z0-9_-]+", query)
        if len(term) > 3 and term not in STOPWORDS and term not in GENERIC_QUERY_TERMS
    }
    if not terms:
        return 0.0
    if source_text:
        haystack = f"{haystack} {source_text}".casefold()
    matched = sum(term in haystack for term in terms)
    return float(matched) / len(terms) if matched else 0.0


def _normalize_place(value: object) -> str:
    """Normalize place and authority labels for safe comparisons."""

    text = str(value or "").casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\bcounty\b", "", text).strip().replace(" ", "_")


def _parse_datetime(value: object) -> datetime | None:
    """Convert catalog timestamps into the strict orchestration datetime type."""

    if isinstance(value, datetime):
        return value
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _load_source_record(root: Path, row: dict[str, object]) -> dict[str, object]:
    """Load the source-backed record referenced by a catalog row."""

    candidates = [row.get("meta_path"), row.get("path")]
    record_id = str(row.get("id") or "")
    for candidate in candidates:
        if not candidate:
            continue
        path = root / str(candidate)
        if path.suffix.casefold() == ".jsonl" and path.exists():
            for record in iter_jsonl(path):
                if str(record.get("id") or record.get("entity_id") or "") == record_id:
                    return record
        elif path.suffix.casefold() == ".json" and path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        elif path.suffix.casefold() in {".md", ".txt"} and path.exists():
            return {"full_text": path.read_text(encoding="utf-8", errors="replace")}
    return {}


def _evidence_source_path(row: dict[str, object], fallback: Path) -> str:
    """Return a derived source path safe for model-facing provenance."""

    for key in ("path", "meta_path"):
        value = str(row.get(key) or "").strip()
        if value and "_RAW_ARCHIVE" not in value:
            return value
    return fallback.as_posix()


def _catalog_row_for_id(root: Path, record_id: str) -> dict[str, object] | None:
    """Find one catalog row by canonical ID."""

    catalog = root / "_CONTROL_PLANE" / "RETRIEVAL_CATALOG.jsonl"
    if not catalog.exists():
        return None
    for row in iter_jsonl(catalog):
        if str(row.get("id")) == record_id:
            return row
    return None


def _select_source_text(
    record: dict[str, object],
    row: dict[str, object],
    state: QueryState | None,
) -> str:
    """Select a bounded source-backed passage instead of metadata-only text."""

    text = str(
        record.get("full_text")
        or record.get("text")
        or record.get("action_required")
        or record.get("source_evidence")
        or ""
    ).strip()
    if not text:
        return ""
    if state is None:
        return text[:1600]
    query = state.intent.normalized_query or state.intent.raw_query
    terms = [term for term in re.findall(r"[a-z0-9]+", query.casefold()) if len(term) > 3]
    paragraphs = [part.strip() for part in re.split(r"\n{2,}|(?<=[.!?])\s+", text) if part.strip()]
    scored = sorted(
        paragraphs,
        key=lambda part: sum(term in part.casefold() for term in terms),
        reverse=True,
    )
    selected = scored[0] if scored and terms else text
    return selected[:800]


def _applicability(row: dict[str, object], state: QueryState) -> str:
    """Describe why a catalog row is geographically eligible."""

    jurisdiction = state.jurisdiction
    if jurisdiction is None:
        return "No local geography was supplied; authority-level filtering was applied."
    if jurisdiction.district:
        return f"Matched district authority: {jurisdiction.district}."
    if jurisdiction.county:
        return f"Matched county scope: {jurisdiction.county}."
    return "Matched the requested authority level."


def _selection_reasons(row: dict[str, object], state: QueryState, score: float) -> list[str]:
    """Return an explainable record-selection trace."""

    reasons = [f"query_score={score:.3f}", f"authority_level={row.get('authority_level') or 'state'}"]
    if state.jurisdiction and state.jurisdiction.county:
        reasons.append(f"county={state.jurisdiction.county}")
    if row.get("source_category"):
        reasons.append(f"source_category={row['source_category']}")
    return reasons


def _passage_from_row(
    row: dict[str, object],
    passage_text: str = "",
    source_record: dict[str, object] | None = None,
):
    """Build exact passage metadata when the index provides it."""

    from geode.orchestration.contracts import PassageLocation

    record = source_record or {}
    if not any(
        row.get(key) or record.get(key)
        for key in (
            "source_section",
            "section_heading",
            "source_page",
            "section_num",
            "section_heading",
        )
    ):
        return None
    return PassageLocation(
        section=str(
            row.get("source_section") or record.get("source_section") or record.get("section_num") or ""
        ) or None,
        heading=str(row.get("section_heading") or record.get("section_heading") or "") or None,
        page=int(row["source_page"])
        if row.get("source_page")
        else int(record["source_page"])
        if record.get("source_page")
        else None,
        page_end=int(row["source_page_end"])
        if row.get("source_page_end")
        else int(record["source_page_end"])
        if record.get("source_page_end")
        else None,
        line_start=int(row["source_line_start"])
        if row.get("source_line_start")
        else int(record["source_line_start"])
        if record.get("source_line_start")
        else None,
        line_end=int(row["source_line_end"])
        if row.get("source_line_end")
        else int(record["source_line_end"])
        if record.get("source_line_end")
        else None,
        text_hash=hashlib.sha256(" ".join(passage_text.split()).encode("utf-8")).hexdigest()
        if passage_text
        else str(row.get("text_hash") or "") or None,
    )
