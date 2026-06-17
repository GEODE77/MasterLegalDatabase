"""Core deterministic industry tagging helpers for Project Geode."""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tqdm import tqdm
except ModuleNotFoundError:
    tqdm = None

TAGGER_VERSION = "1.0.0"
METHOD_WEIGHTS = {
    "crs_article": 3,
    "crs_title": 1,
    "keyword": 0.5,
    "committee": 0.3,
}

DEFAULT_TAXONOMY_DIR = "taxonomies"
DEFAULT_INDEX_DIR = "_INDICES"

# Extracts the CRS title and article from references such as
# "25-7-114.7, C.R.S." and "section 39-22-104 (3)(a), C.R.S.".
CRS_REF_PATTERN = re.compile(
    r"(?:\bsection\s+|\u00a7\s*)?"
    r"(?P<title>\d{1,2}(?:\.\d+)?)-"
    r"(?P<article>\d{1,3}(?:\.\d+)?)"
    r"-\d{1,4}(?:\.\d+)?"
    r"(?:\s*\([^)]+\))*"
    r"(?:\s*,?\s*(?:C\.?\s*R\.?\s*S\.?|Colorado\s+Revised\s+Statutes))?",
    re.IGNORECASE,
)

# Normalizes committee names for deterministic case-insensitive containment.
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
CHAMBER_PREFIX_PATTERN = re.compile(r"^(?:house|senate)\s+", re.IGNORECASE)

LOGGER = logging.getLogger(__name__)


def resolve_bill_fields(bill: dict) -> dict[str, Any]:
    """Normalize bill fields used by the industry tagger.

    Args:
        bill: Parsed, enriched, or design-style bill dictionary.

    Returns:
        Dictionary with ``bill_number``, ``title``, ``crs_references``, and
        ``committees`` keys.
    """
    if not isinstance(bill, dict):
        bill = {}

    metadata = bill.get("metadata") if isinstance(bill.get("metadata"), dict) else {}
    extracted = bill.get("extracted") if isinstance(bill.get("extracted"), dict) else {}
    entities = bill.get("entities") if isinstance(bill.get("entities"), dict) else {}

    raw_refs = (
        bill.get("crs_references")
        or bill.get("citations")
        or extracted.get("citations")
        or []
    )
    raw_committees = entities.get("committees") or extracted.get("committees") or []

    return {
        "bill_number": _first_string(
            bill.get("bill_number"),
            bill.get("id"),
            metadata.get("bill_number"),
        ),
        "title": _first_string(bill.get("title"), metadata.get("title")),
        "crs_references": _citation_strings(raw_refs),
        "committees": _committee_items(raw_committees),
    }


def parse_crs_ref(ref: str) -> tuple[str | None, str | None]:
    """Parse a CRS reference into title and article numbers.

    Args:
        ref: CRS reference string, such as ``section 25-7-114.7, C.R.S.``.

    Returns:
        ``(title_number, article_number)`` or ``(None, None)`` if malformed.
    """
    if not isinstance(ref, str):
        return (None, None)

    match = CRS_REF_PATTERN.search(ref)
    if match is None:
        return (None, None)
    return (match.group("title"), match.group("article"))


def load_taxonomies(taxonomy_dir: str = DEFAULT_TAXONOMY_DIR) -> dict[str, Any]:
    """Load the four deterministic industry tagging taxonomy files.

    Args:
        taxonomy_dir: Directory containing taxonomy JSON files.

    Returns:
        Taxonomy bundle with ``crs_map``, ``naics_hierarchy``, ``keywords``,
        and ``committees`` keys.

    Raises:
        FileNotFoundError: If a required taxonomy file is missing.
        ValueError: If a taxonomy file contains invalid JSON.
    """
    directory = Path(taxonomy_dir)
    files = {
        "crs_map": "crs_title_map.json",
        "naics_hierarchy": "naics_hierarchy.json",
        "keywords": "keyword_to_naics.json",
        "committees": "committee_to_naics.json",
    }

    taxonomies: dict[str, Any] = {}
    for key, filename in files.items():
        path = directory / filename
        if not path.exists():
            raise FileNotFoundError(f"Required taxonomy file is missing: {path}")
        try:
            taxonomies[key] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in taxonomy file {path}: {exc}") from exc

    return taxonomies


def tag_by_crs(bill: dict, crs_map: dict) -> dict[str, Any]:
    """Tag a bill by CRS title and article references.

    Args:
        bill: Bill dictionary in any supported parsed/enriched shape.
        crs_map: Loaded CRS title/article taxonomy map.

    Returns:
        Weighted CRS tagging result with NAICS hits, themes, matched titles,
        matched articles, universal flag, unmatched refs, and confidence.
    """
    resolved = resolve_bill_fields(bill)
    naics_hits: dict[str, float] = {}
    themes: set[str] = set()
    matched_titles: list[str] = []
    matched_articles: list[str] = []
    unmatched_refs: list[str] = []
    universal_detected = False
    article_matches = 0
    title_matches = 0

    taxonomy = crs_map if isinstance(crs_map, dict) else {}
    for ref in resolved["crs_references"]:
        title_number, article_number = parse_crs_ref(ref)
        if title_number is None or article_number is None:
            unmatched_refs.append(ref)
            continue

        title_entry = taxonomy.get(title_number)
        if not isinstance(title_entry, dict):
            unmatched_refs.append(ref)
            LOGGER.info("Unmatched CRS title reference: %s", ref)
            continue

        _append_unique(matched_titles, _title_label(title_number, title_entry))
        articles = title_entry.get("articles")
        article_entry = articles.get(article_number) if isinstance(articles, dict) else None
        if isinstance(article_entry, dict):
            article_matches += 1
            universal_detected = _add_naics_hits(
                naics_hits,
                article_entry.get("naics"),
                METHOD_WEIGHTS["crs_article"],
                universal_detected,
            )
            themes.update(_string_list(article_entry.get("themes")))
            _append_unique(
                matched_articles,
                _article_label(title_number, article_number, article_entry),
            )
            continue

        title_matches += 1
        universal_detected = _add_naics_hits(
            naics_hits,
            title_entry.get("default_naics"),
            METHOD_WEIGHTS["crs_title"],
            universal_detected,
        )
        themes.update(_string_list(title_entry.get("default_themes")))

    if article_matches:
        confidence = "high"
    elif title_matches:
        confidence = "moderate"
    else:
        confidence = "low"

    return {
        "naics_hits": naics_hits,
        "themes": themes,
        "matched_titles": matched_titles,
        "matched_articles": matched_articles,
        "universal_detected": universal_detected,
        "unmatched_refs": unmatched_refs,
        "confidence": confidence,
        "article_match_count": article_matches,
        "title_match_count": title_matches,
    }


def tag_by_keywords(bill: dict, keyword_map: list) -> dict[str, Any]:
    """Tag a bill by running configured keyword regexes against its title only.

    Args:
        bill: Bill dictionary in any supported parsed/enriched shape.
        keyword_map: Loaded keyword taxonomy list.

    Returns:
        Keyword tagging result with weighted NAICS hits and themes.
    """
    resolved = resolve_bill_fields(bill)
    title = resolved["title"]
    naics_hits: dict[str, float] = {}
    themes: set[str] = set()
    if not title:
        return {"naics_hits": naics_hits, "themes": themes}

    entries = keyword_map if isinstance(keyword_map, list) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        pattern_text = entry.get("pattern")
        if not isinstance(pattern_text, str) or not pattern_text:
            continue
        try:
            if re.search(pattern_text, title, re.IGNORECASE):
                _add_naics_hits(
                    naics_hits,
                    entry.get("naics"),
                    METHOD_WEIGHTS["keyword"],
                    False,
                )
                themes.update(_string_list(entry.get("themes")))
        except re.error as exc:
            LOGGER.warning("Invalid keyword regex %r: %s", pattern_text, exc)

    return {"naics_hits": naics_hits, "themes": themes}


def tag_by_committee(bill: dict, committee_map: dict) -> dict[str, Any]:
    """Tag a bill by mapping committee mentions to NAICS industries.

    Args:
        bill: Bill dictionary in any supported parsed/enriched shape.
        committee_map: Loaded committee taxonomy mapping.

    Returns:
        Committee tagging result with weighted NAICS hits and themes.
    """
    resolved = resolve_bill_fields(bill)
    naics_hits: dict[str, float] = {}
    themes: set[str] = set()
    taxonomy = committee_map if isinstance(committee_map, dict) else {}

    for committee in resolved["committees"]:
        committee_name = _committee_name(committee)
        chamber = _committee_chamber(committee)
        match = _find_committee_mapping(committee_name, chamber, taxonomy)
        if match is None:
            continue
        _add_naics_hits(
            naics_hits,
            match.get("naics"),
            METHOD_WEIGHTS["committee"],
            False,
        )
        themes.update(_string_list(match.get("themes")))

    return {"naics_hits": naics_hits, "themes": themes}


def combine_scores(
    crs_result: dict,
    keyword_result: dict,
    committee_result: dict,
) -> dict[str, Any]:
    """Combine weighted NAICS hits and themes from all tagger methods.

    Args:
        crs_result: Result from ``tag_by_crs``.
        keyword_result: Result from ``tag_by_keywords``.
        committee_result: Result from ``tag_by_committee``.

    Returns:
        Dictionary containing summed NAICS hits and a sorted theme list.
    """
    combined_naics_hits: dict[str, float] = {}
    all_themes: set[str] = set()

    for result in (crs_result, keyword_result, committee_result):
        if not isinstance(result, dict):
            continue
        hits = result.get("naics_hits")
        if isinstance(hits, dict):
            for code, weight in hits.items():
                try:
                    numeric_weight = float(weight)
                except (TypeError, ValueError):
                    continue
                combined_naics_hits[str(code)] = (
                    combined_naics_hits.get(str(code), 0.0) + numeric_weight
                )
        all_themes.update(_string_list(result.get("themes")))

    return {
        "combined_naics_hits": combined_naics_hits,
        "all_themes": sorted(all_themes),
    }


def classify_scope(
    combined_naics_hits: dict,
    naics_hierarchy: dict,
    universal_detected: bool,
) -> str:
    """Classify the industry applicability scope for a bill.

    Args:
        combined_naics_hits: Weighted NAICS code hit map.
        naics_hierarchy: Loaded NAICS hierarchy taxonomy.
        universal_detected: Whether CRS taxonomy explicitly returned ``ALL``.

    Returns:
        One of ``universal``, ``broad``, ``narrow``, or ``targeted``.
    """
    if universal_detected:
        return "universal"

    codes = [str(code) for code in combined_naics_hits if str(code).strip()]
    if not codes:
        return "targeted"

    sectors = {_sector_for_code(code, naics_hierarchy) for code in codes}
    sectors.discard(None)
    sector_count = len(sectors)

    if sector_count >= 5:
        return "universal"
    if 3 <= sector_count <= 4:
        return "broad"
    if len(codes) == 1 and not _is_sector_code(codes[0], naics_hierarchy):
        return "targeted"
    if 1 <= sector_count <= 2:
        return "narrow"
    return "targeted"


def rank_industries(
    combined_naics_hits: dict,
    naics_hierarchy: dict,
) -> list[dict[str, Any]]:
    """Rank matched NAICS industries by deterministic score.

    Args:
        combined_naics_hits: Weighted NAICS code hit map.
        naics_hierarchy: Loaded NAICS hierarchy taxonomy.

    Returns:
        Up to 20 ranked industry records with relevance buckets.
    """
    sorted_hits = sorted(
        (
            (str(code), float(weight))
            for code, weight in combined_naics_hits.items()
            if _can_float(weight)
        ),
        key=lambda item: (-item[1], item[0]),
    )[:20]
    if not sorted_hits:
        return []

    count = len(sorted_hits)
    high_cutoff = max(1, math.ceil(count * 0.2))
    medium_cutoff = max(high_cutoff, math.ceil(count * 0.6))
    ranked: list[dict[str, Any]] = []

    for index, (code, score) in enumerate(sorted_hits):
        if index < high_cutoff:
            relevance = "high"
        elif index < medium_cutoff:
            relevance = "medium"
        else:
            relevance = "low"
        entry = naics_hierarchy.get(code) if isinstance(naics_hierarchy, dict) else None
        name = entry.get("name") if isinstance(entry, dict) else None
        ranked.append(
            {
                "naics": code,
                "name": str(name or f"Unknown NAICS {code}"),
                "relevance": relevance,
                "score": score,
            }
        )

    return ranked


def tag_bill(bill: dict, taxonomies: dict) -> dict[str, Any]:
    """Run all deterministic industry tagging methods for one bill.

    Args:
        bill: Parsed/enriched bill record.
        taxonomies: Taxonomy bundle from ``load_taxonomies``.

    Returns:
        Complete deterministic industry tag record for the bill.
    """
    resolved = resolve_bill_fields(bill)
    bundle = taxonomies if isinstance(taxonomies, dict) else {}
    crs_result = tag_by_crs(bill, bundle.get("crs_map", {}))
    keyword_result = tag_by_keywords(bill, bundle.get("keywords", []))
    committee_result = tag_by_committee(bill, bundle.get("committees", {}))
    combined = combine_scores(crs_result, keyword_result, committee_result)
    combined_hits = combined["combined_naics_hits"]
    scope = classify_scope(
        combined_hits,
        bundle.get("naics_hierarchy", {}),
        bool(crs_result.get("universal_detected")),
    )

    return {
        "bill_number": resolved["bill_number"] or "UNKNOWN",
        "applicability_scope": scope,
        "industries": rank_industries(
            combined_hits,
            bundle.get("naics_hierarchy", {}),
        ),
        "regulatory_themes": combined["all_themes"],
        "crs_titles": list(crs_result.get("matched_titles", [])),
        "universal_applicability": scope == "universal",
        "tagging_metadata": {
            "method_weights": METHOD_WEIGHTS,
            "confidence": str(crs_result.get("confidence", "low")),
            "crs_matches": {
                "article_level": int(crs_result.get("article_match_count", 0) or 0),
                "title_level": int(crs_result.get("title_match_count", 0) or 0),
                "unmatched": len(crs_result.get("unmatched_refs", []) or []),
            },
            "tagged_at": datetime.now(timezone.utc).isoformat(),
            "tagger_version": TAGGER_VERSION,
        },
    }


def build_theme_index(all_tags: dict) -> dict[str, list[str]]:
    """Build a reverse index from theme to bill numbers.

    Args:
        all_tags: Mapping of bill number to industry tag record.

    Returns:
        Sorted theme-to-bill-number index.
    """
    theme_index: dict[str, list[str]] = {}
    if not isinstance(all_tags, dict):
        return theme_index

    for bill_number, tag_record in all_tags.items():
        if not isinstance(tag_record, dict):
            continue
        for theme in _string_list(tag_record.get("regulatory_themes")):
            theme_index.setdefault(theme, []).append(str(bill_number))

    return {theme: sorted(bills) for theme, bills in sorted(theme_index.items())}


def tag_all(
    input_dir: str,
    taxonomy_dir: str = DEFAULT_TAXONOMY_DIR,
    output_dir: str = DEFAULT_INDEX_DIR,
) -> dict[str, Any]:
    """Tag all parsed bills in a directory and write industry/theme indices.

    Args:
        input_dir: Directory containing ``*_parsed.json`` bill records.
        taxonomy_dir: Directory containing taxonomy JSON files.
        output_dir: Directory where index JSON files are written.

    Returns:
        Batch summary with tagging counts and breakdowns.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    taxonomies = load_taxonomies(taxonomy_dir)
    parsed_paths = sorted(input_path.glob("*_parsed.json")) if input_path.exists() else []

    industry_index: dict[str, dict[str, Any]] = {}
    summary = {
        "tagged": 0,
        "failed": 0,
        "scope_breakdown": {"universal": 0, "broad": 0, "narrow": 0, "targeted": 0},
        "confidence_breakdown": {"high": 0, "moderate": 0, "low": 0},
        "unique_themes": 0,
        "unique_industries": 0,
    }

    for bill_path in _progress(parsed_paths, "Tagging bills"):
        try:
            bill = _load_bill(bill_path)
            tag_record = tag_bill(bill, taxonomies)
            bill_number = tag_record["bill_number"]
            industry_index[bill_number] = tag_record
            summary["tagged"] += 1
            scope = tag_record["applicability_scope"]
            confidence = tag_record["tagging_metadata"]["confidence"]
            summary["scope_breakdown"][scope] += 1
            summary["confidence_breakdown"][confidence] += 1
        except Exception as exc:
            summary["failed"] += 1
            LOGGER.error("Failed to tag %s: %s", bill_path, exc)

    theme_index = build_theme_index(industry_index)
    _write_json(output_path / "industry_index.json", industry_index)
    _write_json(output_path / "theme_index.json", theme_index)

    summary["unique_themes"] = len(theme_index)
    summary["unique_industries"] = len(
        {
            industry["naics"]
            for tag_record in industry_index.values()
            for industry in tag_record.get("industries", [])
            if isinstance(industry, dict) and industry.get("naics")
        }
    )
    return summary


def _first_string(*values: Any) -> str:
    """Return the first non-empty string-like value."""
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, (dict, list, tuple, set)):
            text = str(value).strip()
            if text:
                return text
    return ""


def _citation_strings(value: Any) -> list[str]:
    """Normalize citation containers into a list of strings."""
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []

    citations: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            citations.append(item.strip())
        elif isinstance(item, dict):
            text = _first_string(
                item.get("canonical_form"),
                item.get("citation"),
                item.get("ref"),
                item.get("text"),
                item.get("as_written"),
            )
            if text:
                citations.append(text)
    return citations


def _committee_items(value: Any) -> list[Any]:
    """Normalize committee containers into a list."""
    if isinstance(value, (str, dict)):
        return [value]
    if isinstance(value, list):
        return value
    return []


def _committee_name(committee: Any) -> str:
    """Extract a committee display name from a string or object."""
    if isinstance(committee, str):
        return committee.strip()
    if isinstance(committee, dict):
        return _first_string(
            committee.get("committee"),
            committee.get("name"),
            committee.get("committee_name"),
        )
    return ""


def _committee_chamber(committee: Any) -> str:
    """Extract a normalized committee chamber from a committee object."""
    if isinstance(committee, dict):
        return _first_string(committee.get("chamber")).lower()
    return ""


def _find_committee_mapping(
    committee_name: str,
    chamber: str,
    committee_map: dict[str, Any],
) -> dict[str, Any] | None:
    """Find a committee taxonomy entry by case-insensitive containment."""
    normalized_name = _normalize_committee_name(committee_name)
    if not normalized_name:
        return None

    for key, entry in committee_map.items():
        if not isinstance(entry, dict):
            continue
        mapped_chamber = _first_string(entry.get("chamber")).lower()
        if chamber and mapped_chamber and chamber != mapped_chamber:
            continue

        normalized_key = _normalize_committee_name(str(key))
        bare_key = _normalize_committee_name(CHAMBER_PREFIX_PATTERN.sub("", str(key)))
        candidates = {normalized_key, bare_key}
        if any(
            normalized_name == candidate
            or normalized_name in candidate
            or candidate in normalized_name
            for candidate in candidates
            if candidate
        ):
            return entry
    return None


def _normalize_committee_name(value: str) -> str:
    """Normalize a committee name for deterministic matching."""
    lowered = CHAMBER_PREFIX_PATTERN.sub("", value.lower())
    return NON_ALNUM_PATTERN.sub(" ", lowered).strip()


def _add_naics_hits(
    hits: dict[str, float],
    codes: Any,
    weight: float,
    universal_detected: bool,
) -> bool:
    """Add weighted NAICS hits and return the updated universal flag."""
    for code in _string_list(codes):
        if code == "ALL":
            universal_detected = True
            continue
        hits[code] = hits.get(code, 0.0) + weight
    return universal_detected


def _string_list(value: Any) -> list[str]:
    """Return stripped non-empty strings from a possible list or scalar."""
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, (list, tuple, set)):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _title_label(title_number: str, title_entry: dict[str, Any]) -> str:
    """Build a canonical title label for match output."""
    title_name = _first_string(title_entry.get("title_name"))
    return f"Title {title_number} - {title_name}" if title_name else f"Title {title_number}"


def _article_label(
    title_number: str,
    article_number: str,
    article_entry: dict[str, Any],
) -> str:
    """Build a canonical article label for match output."""
    article_name = _first_string(article_entry.get("article_name"))
    label = f"Title {title_number}, Article {article_number}"
    return f"{label} - {article_name}" if article_name else label


def _append_unique(values: list[str], value: str) -> None:
    """Append a value only when it is non-empty and not already present."""
    if value and value not in values:
        values.append(value)


def _sector_for_code(code: str, naics_hierarchy: dict) -> str | None:
    """Resolve a NAICS code to its 2-digit sector code."""
    if not isinstance(code, str) or not code:
        return None
    entry = naics_hierarchy.get(code) if isinstance(naics_hierarchy, dict) else None
    if isinstance(entry, dict):
        sector = entry.get("sector")
        return str(sector) if sector is not None else None
    if code.startswith(("31", "32", "33")):
        return "31-33"
    if code.startswith(("44", "45")):
        return "44-45"
    if code.startswith(("48", "49")):
        return "48-49"
    return code[:2] if len(code) >= 2 and code[:2].isdigit() else None


def _is_sector_code(code: str, naics_hierarchy: dict) -> bool:
    """Return whether a code is a top-level NAICS sector."""
    entry = naics_hierarchy.get(code) if isinstance(naics_hierarchy, dict) else None
    return isinstance(entry, dict) and entry.get("parent") is None


def _can_float(value: Any) -> bool:
    """Return whether a value can be converted to float."""
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _load_bill(path: Path) -> dict[str, Any]:
    """Load one parsed bill JSON object."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Top-level parsed bill JSON value is not an object.")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    """Write deterministic JSON output."""
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _progress(items: list[Path], description: str) -> Any:
    """Return a progress iterator, using tqdm when available."""
    if tqdm is None:
        return items
    return tqdm(items, desc=description, unit="bill")


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Deterministically tag parsed Colorado bills by industry."
    )
    parser.add_argument(
        "--input-dir",
        default="data/structured_output",
        help='Directory of *_parsed.json files. Default: "data/structured_output".',
    )
    parser.add_argument(
        "--taxonomy-dir",
        default=DEFAULT_TAXONOMY_DIR,
        help=f"Directory containing taxonomy JSON files. Default: {DEFAULT_TAXONOMY_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_INDEX_DIR,
        help=f"Directory for generated index files. Default: {DEFAULT_INDEX_DIR}",
    )
    parser.add_argument("--single", help="Tag one parsed bill JSON file and print it.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the industry tagger command-line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        taxonomies = load_taxonomies(args.taxonomy_dir)
        if args.single:
            tag_record = tag_bill(_load_bill(Path(args.single)), taxonomies)
            print(json.dumps(tag_record, indent=2, ensure_ascii=False))
            return 0

        summary = tag_all(
            input_dir=args.input_dir,
            taxonomy_dir=args.taxonomy_dir,
            output_dir=args.output_dir,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0 if summary["failed"] == 0 else 1
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"Industry tagging failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
