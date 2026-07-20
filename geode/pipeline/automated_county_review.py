"""Automated, source-grounded review and promotion for county candidates."""

from __future__ import annotations

import argparse
import html
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from geode.schemas import RuleUnit
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl


CONTROL = Path("_CONTROL_PLANE")
QUEUE = CONTROL / "COUNTY_SEMANTIC_REVIEW_QUEUE.jsonl"
MAPPING = CONTROL / "COUNTY_SEMANTIC_CANDIDATE_MAP.jsonl"
DECISIONS = CONTROL / "COUNTY_SEMANTIC_AUTOMATED_REVIEW.jsonl"
SUMMARY = CONTROL / "COUNTY_SEMANTIC_AUTOMATED_REVIEW_SUMMARY.json"
UNITS = Path("08_County_Authorities/_meta/local_rule_units.jsonl")
MODAL_RE = re.compile(
    r"\b(shall not|may not|must not|is prohibited from|are prohibited from|"
    r"is required to|are required to|shall|must|may)\b", re.IGNORECASE
)
ACTOR_RE = re.compile(
    r"\b(owners?|operators?|applicants?|licensees?|permittees?|contractors?|"
    r"employers?|persons?|business(?:es)?|companies|facilities|counties|cities|"
    r"municipal(?:ity|ities)|departments?|agencies|officials?|requestors?|"
    r"representatives?|providers?|developers?|landowners?|occupants?|drivers?|"
    r"services?|organizations?|entities|authorities)\b",
    re.IGNORECASE,
)
NOISE_RE = re.compile(
    r"\b(for your convenience|not exhaustive|may not include every|helpful|"
    r"should note|may find|please|click|visit|contact us|learn more)\b",
    re.IGNORECASE,
)
STRONG_SOURCE_CATEGORIES = {
    "county_codes",
    "county_ordinances",
    "continuing_resolutions",
    "public_health",
    "environmental_open_burning",
    "building_construction",
    "animal_control_nuisance",
    "roads_transportation_access",
    "subdivision_development",
    "administrative_rule_manuals",
    "emergency_fire_restrictions",
}


class _TextParser(HTMLParser):
    """Collect visible HTML text."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def review_county_candidates(root: Path, *, apply: bool = False) -> dict[str, Any]:
    """Review the final county queue and optionally promote passing candidates."""

    resolved = root.resolve()
    queue = list(iter_jsonl(resolved / QUEUE))
    mappings = {
        row["review_id"]: row for row in iter_jsonl(resolved / MAPPING)
    }
    index_rows = _load_index(resolved)
    results: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    approved_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    source_cache: dict[str, str] = {}
    for row in queue:
        if not row.get("review_disposition"):
            continue
        result, approved = _review_one(
            resolved, row, mappings.get(row.get("review_id")), index_rows, source_cache
        )
        results.append(result)
        counts[result["automated_disposition"]] += 1
        if approved:
            approved_rows.append((row, result))

    if apply and approved_rows:
        _apply_approved(resolved, approved_rows, mappings, index_rows)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidates_reviewed": len(results),
        "auto_approved": counts["auto_approved"],
        "auto_quarantined": counts["auto_quarantined"],
        "blocked": sum(
            "candidate has no safe permanent identity mapping" in result["hard_failures"]
            for result in results
        ),
        "applied": len(approved_rows) if apply else 0,
        "dry_run": not apply,
        "status": "applied" if apply else "review_complete",
        "review_method": [
            "source hash and parent identity check",
            "exact source text check",
            "legal modal and responsible-party check",
            "single-action and noise check",
            "source-category and current-index check",
            "schema validation before promotion",
        ],
        "boundary": (
            "Only candidates that pass every hard gate are promoted. Failed, ambiguous, "
            "or informational candidates remain outside answer-safe retrieval."
        ),
    }
    atomic_write_jsonl(resolved / DECISIONS, results, resolved)
    atomic_write_json(resolved / SUMMARY, summary, resolved)
    return summary


def _review_one(
    root: Path,
    row: dict[str, Any],
    mapping: dict[str, Any] | None,
    index_rows: dict[str, dict[str, Any]],
    source_cache: dict[str, str],
) -> tuple[dict[str, Any], bool]:
    """Review one candidate with hard gates and an auditable score."""

    candidate = row["candidate_rule_unit"]
    action = _clean(str(candidate.get("action_required") or ""))
    parent_id = str(row.get("parent_rule_id") or candidate.get("parent_regulation_id") or "")
    parent = index_rows.get(parent_id)
    source_path = str(row.get("source_path") or "")
    if source_path not in source_cache:
        source_cache[source_path] = _read_source(root, source_path)
    source_text = source_cache[source_path]
    normalized_action = _normalize(action)
    source_match = bool(source_text) and normalized_action in _normalize(source_text)
    modal_count = len(MODAL_RE.findall(action))
    entity = _clean(str(candidate.get("regulated_entity") or ""))
    entity_specific = _specific_actor(entity)
    legal_source = str(row.get("source_category") or "") in STRONG_SOURCE_CATEGORIES
    formal_filename = bool(re.search(r"(ordinance|code|rule|regulation|policy|resolution)",
                                     str(row.get("source_path") or ""), re.IGNORECASE))
    no_noise = not bool(NOISE_RE.search(action))
    source_identity = bool(parent and parent.get("sha256") == row.get("source_hash"))
    mapping_ok = bool(mapping and mapping.get("permanent_rule_unit_id") and
                      mapping.get("mapping_status") != "blocked")
    current_index = bool(parent and parent.get("last_updated"))
    hard_failures: list[str] = []
    if not source_identity:
        hard_failures.append("source hash does not match active parent")
    if not mapping_ok:
        hard_failures.append("candidate has no safe permanent identity mapping")
    if not source_match:
        hard_failures.append("action text was not found in preserved source")
    if not MODAL_RE.search(action):
        hard_failures.append("no legal action word was found")
    if not entity_specific:
        hard_failures.append("responsible party is not specific enough")
    if modal_count != 1:
        hard_failures.append("candidate contains multiple or no legal actions")
    if not no_noise:
        hard_failures.append("passage contains informational or navigation language")
    if not (legal_source or formal_filename):
        hard_failures.append("source category is not clearly legal or regulatory")

    score = sum([
        0.20 if source_identity else 0.0,
        0.15 if mapping_ok else 0.0,
        0.25 if source_match else 0.0,
        0.15 if entity_specific else 0.0,
        0.10 if modal_count == 1 else 0.0,
        0.10 if legal_source or formal_filename else 0.0,
        0.05 if current_index else 0.0,
    ])
    approved = not hard_failures and score >= 0.95
    disposition = "auto_approved" if approved else "auto_quarantined"
    result = {
        "review_id": row["review_id"],
        "candidate_rule_unit_id": candidate["id"],
        "permanent_rule_unit_id": mapping.get("permanent_rule_unit_id") if mapping else None,
        "automated_disposition": disposition,
        "score": round(score, 3),
        "hard_failures": hard_failures,
        "checks": {
            "source_identity": source_identity,
            "mapping": mapping_ok,
            "source_text_match": source_match,
            "specific_responsible_party": entity_specific,
            "single_legal_action": modal_count == 1,
            "legal_source": legal_source or formal_filename,
            "current_index_identity": current_index,
        },
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewer": "geode_automated_human_style_v1",
    }
    return result, approved


def _apply_approved(
    root: Path,
    approved_rows: list[tuple[dict[str, Any], dict[str, Any]]],
    mappings: dict[str, dict[str, Any]],
    index_rows: dict[str, dict[str, Any]],
) -> None:
    """Add approved candidates to metadata and the active index atomically."""

    metadata_path = root / UNITS
    index_path = root / "08_County_Authorities" / "_index.jsonl"
    metadata = list(iter_jsonl(metadata_path))
    metadata_by_id = {str(row.get("id")): row for row in metadata}
    index = list(iter_jsonl(index_path))
    index_by_id = {str(row.get("id")): row for row in index}
    for row, result in approved_rows:
        candidate = dict(row["candidate_rule_unit"])
        target_id = str(result["permanent_rule_unit_id"])
        candidate["id"] = target_id
        candidate["semantic_status"] = "semantic_ready"
        RuleUnit.model_validate(candidate)
        metadata_by_id[target_id] = candidate
        parent = index_rows[str(row["parent_rule_id"])]
        index_by_id[target_id] = {
            **parent,
            "id": target_id,
            "entity_type": "rule_unit",
            "parent_regulation_id": row["parent_rule_id"],
            "title": candidate["source_section"],
            "source_section": candidate["source_section"],
            "source_path": row["source_path"],
            "source_url": row["source_url"],
            "sha256": row["source_hash"],
            "semantic_status": "semantic_ready",
            "tags": [*list(parent.get("tags") or []), "semantic_ready"],
            "confidence": candidate["confidence"]["overall"],
        }
    atomic_write_jsonl(metadata_path, metadata_by_id.values(), root)
    atomic_write_jsonl(index_path, index_by_id.values(), root)
    _write_retrieval_catalog_if_available(root)


def _load_index(root: Path) -> dict[str, dict[str, Any]]:
    """Load the county active index by ID."""

    path = root / "08_County_Authorities" / "_index.jsonl"
    return {str(row.get("id")): row for row in iter_jsonl(path) if row.get("id")}


def _read_source(root: Path, source_path: str) -> str:
    """Read visible text from HTML, PDF, DOCX, or plain text source files."""

    path = root / source_path
    if not path.exists():
        return ""
    suffix = path.suffix.casefold()
    try:
        if suffix in {".html", ".htm"}:
            parser = _TextParser()
            parser.feed(path.read_text(encoding="utf-8", errors="replace"))
            return html.unescape(" ".join(parser.parts))
        if suffix == ".pdf":
            import fitz

            with fitz.open(path) as document:
                return "\n".join(page.get_text() for page in document)
        if suffix == ".docx":
            with zipfile.ZipFile(path) as archive:
                xml = archive.read("word/document.xml")
            root_node = ElementTree.fromstring(xml)
            return " ".join(root_node.itertext())
        return path.read_text(encoding="utf-8", errors="replace")
    except (AssertionError, OSError, RuntimeError, ValueError, UnicodeError, zipfile.BadZipFile):
        return ""


def _normalize(value: str) -> str:
    """Normalize source and candidate text for exact token comparison."""

    return re.sub(r"[^a-z0-9%$]+", " ", value.casefold()).strip()


def _clean(value: str) -> str:
    """Collapse extraction whitespace."""

    return re.sub(r"\s+", " ", value).strip()


def _specific_actor(entity: str) -> bool:
    """Return whether the entity names a plausible responsible party."""

    normalized = entity.casefold().strip(" ,:;-" )
    if len(normalized) < 4 or normalized in {"you", "and", "as", "each", "it", "this"}:
        return False
    if normalized.startswith(("the following", "other requirements", "additional codes")):
        return False
    return bool(ACTOR_RE.search(normalized)) and normalized.split()[0] not in {"and", "or", "as"}


def _write_retrieval_catalog_if_available(root: Path) -> None:
    """Refresh the catalog when the project catalog writer is available."""

    try:
        from geode.pipeline.retrieval_catalog import write_retrieval_catalog

        write_retrieval_catalog(root)
    except (ImportError, OSError, ValueError):
        return


def main() -> int:
    """Run automated review, with optional controlled application."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(review_county_candidates(args.root, apply=args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
