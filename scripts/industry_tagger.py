"""Deterministically tag Colorado bills with NAICS industries and themes.

This module implements Project Geode's Single Source + Multi-Dimensional
Tagging layer. It reads parsed bill records, applies CRS title/article taxonomy
lookups as the primary signal, supplements with title keywords and committee
mentions, and writes queryable industry/theme indices without any LLM calls.
"""

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

DEFAULT_INPUT_DIR = "data/structured_output"
DEFAULT_TAXONOMY_DIR = "taxonomies"
DEFAULT_OUTPUT_DIR = "data/structured_output/indices"

# Extracts CRS title/article numbers from normalized references such as
# "§ 25-7-114.7, C.R.S." or "§ 39-22-104 (3)(a), C.R.S.".
CRS_REF_PATTERN = re.compile(
    r"(?:\u00a7\s*)?(?P<title>\d{1,2}(?:\.\d+)?)-"
    r"(?P<article>\d{1,3}(?:\.\d+)?)"
)

# Normalizes committee names for deterministic fuzzy containment matching.
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
CHAMBER_PREFIX_PATTERN = re.compile(r"^(?:house|senate)\s+", re.IGNORECASE)

LOGGER = logging.getLogger(__name__)


def parse_crs_ref(ref: str) -> tuple[str | None, str | None]:
    """Parse a CRS reference into title and article numbers.

    Args:
        ref: CRS reference string, such as ``§ 25-7-114.7, C.R.S.``.

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
    """Load all static taxonomy reference files.

    Args:
        taxonomy_dir: Directory containing the four taxonomy JSON files.

    Returns:
        Dictionary containing CRS, NAICS, keyword, and committee taxonomies.

    Raises:
        FileNotFoundError: If a required taxonomy file is missing.
        ValueError: If a taxonomy file is invalid JSON.
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
    """Tag a bill by CRS references using title and article taxonomy matches.

    Args:
        bill: Parsed bill record with a ``crs_references`` list.
        crs_map: Loaded CRS title/article taxonomy mapping.

    Returns:
        CRS tagging result with weighted NAICS hits, themes, matched titles,
        matched articles, universal flag, unmatched refs, and confidence.
    """
    naics_hits: dict[str, float] = {}
    themes: set[str] = set()
    matched_titles: list[str] = []
    matched_articles: list[str] = []
    unmatched_refs: list[str] = []
    universal_detected = False
    article_match_count = 0
    title_match_count = 0

    for ref in _string_list(bill.get("crs_references")):
        title_number, article_number = parse_crs_ref(ref)
        if title_number is None or article_number is None:
            unmatched_refs.append(ref)
            continue

        title_entry = crs_map.get(title_number)
        if not isinstance(title_entry, dict):
            unmatched_refs.append(ref)
            LOGGER.info("Unmatched CRS title reference: %s", ref)
            continue

        title_label = _title_label(title_number, title_entry)
        _append_unique(matched_titles, title_label)
        articles = title_entry.get("articles")
        article_entry = articles.get(article_number) if isinstance(articles, dict) else None

        if isinstance(article_entry, dict):
            article_match_count += 1
            universal_detected = _add_naics_hits(
                naics_hits,
                article_entry.get("naics"),
                METHOD_WEIGHTS["crs_article"],
                universal_detected,
            )
            themes.update(_string_list(article_entry.get("themes")))
            article_name = str(article_entry.get("article_name", "")).strip()
            _append_unique(
                matched_articles,
                f"Title {title_number}, Article {article_number} - {article_name}",
            )
            continue

        title_match_count += 1
        universal_detected = _add_naics_hits(
            naics_hits,
            title_entry.get("default_naics"),
            METHOD_WEIGHTS["crs_title"],
            universal_detected,
        )
        themes.update(_string_list(title_entry.get("default_themes")))

    if article_match_count > 0:
        confidence = "high"
    elif title_match_count > 0:
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
        "article_match_count": article_match_count,
        "title_match_count": title_match_count,
    }


def tag_by_keywords(bill: dict, keyword_map: list) -> dict[str, Any]:
    """Tag a bill using keyword patterns in the bill title only.

    Args:
        bill: Parsed bill record with a ``title`` field.
        keyword_map: Loaded keyword-to-NAICS taxonomy list.

    Returns:
        Keyword tagging result with weighted NAICS hits and themes.
    """
    title = str(bill.get("title") or "")
    naics_hits: dict[str, float] = {}
    themes: set[str] = set()

    if not title:
        return {"naics_hits": naics_hits, "themes": themes}

    for entry in keyword_map if isinstance(keyword_map, list) else []:
        if not isinstance(entry, dict):
            continue
        pattern_text = entry.get("pattern")
        if not isinstance(pattern_text, str) or not pattern_text:
            continue
        try:
            pattern = re.compile(pattern_text, re.IGNORECASE)
        except re.error as exc:
            LOGGER.warning("Invalid keyword regex %r: %s", pattern_text, exc)
            continue
        if pattern.search(title):
            _add_naics_hits(
                naics_hits,
                entry.get("naics"),
                METHOD_WEIGHTS["keyword"],
                False,
            )
            themes.update(_string_list(entry.get("themes")))

    return {"naics_hits": naics_hits, "themes": themes}


def tag_by_committee(bill: dict, committee_map: dict) -> dict[str, Any]:
    """Tag a bill using extracted committee mentions.

    Args:
        bill: Parsed and enriched bill record.
        committee_map: Loaded committee-to-NAICS mapping.

    Returns:
        Committee tagging result with weighted NAICS hits and themes.
    """
    naics_hits: dict[str, float] = {}
    themes: set[str] = set()
    entities = bill.get("entities")
    committees = entities.get("committees") if isinstance(entities, dict) else []

    for committee in committees if isinstance(committees, list) else []:
        if not isinstance(committee, dict):
            continue
        committee_name = str(committee.get("committee") or "")
        chamber = str(committee.get("chamber") or "").lower()
        match = _find_committee_mapping(committee_name, chamber, committee_map)
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
    crs_result: dict, keyword_result: dict, committee_result: dict
) -> dict[str, Any]:
    """Combine weighted NAICS hits and themes from all tagging methods.

    Args:
        crs_result: Result from ``tag_by_crs``.
        keyword_result: Result from ``tag_by_keywords``.
        committee_result: Result from ``tag_by_committee``.

    Returns:
        Combined NAICS hit map and sorted theme list.
    """
    combined_naics_hits: dict[str, float] = {}
    all_themes: set[str] = set()

    for result in (crs_result, keyword_result, committee_result):
        hits = result.get("naics_hits") if isinstance(result, dict) else {}
        if isinstance(hits, dict):
            for code, weight in hits.items():
                combined_naics_hits[str(code)] = (
                    combined_naics_hits.get(str(code), 0.0) + float(weight)
                )
        themes = result.get("themes") if isinstance(result, dict) else set()
        all_themes.update(str(theme) for theme in themes if str(theme).strip())

    return {
        "combined_naics_hits": combined_naics_hits,
        "all_themes": sorted(all_themes),
    }


def classify_scope(
    combined_naics_hits: dict, naics_hierarchy: dict, universal_detected: bool
) -> str:
    """Classify the applicability scope from combined NAICS hits.

    Args:
        combined_naics_hits: Weighted NAICS hit map.
        naics_hierarchy: Loaded NAICS hierarchy.
        universal_detected: Whether CRS taxonomy returned universal applicability.

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

    if len(sectors) >= 5:
        return "universal"
    if 3 <= len(sectors) <= 4:
        return "broad"
    if len(sectors) == 1 and all(not _is_sector_code(code, naics_hierarchy) for code in codes):
        return "targeted"
    if 1 <= len(sectors) <= 2:
        return "narrow"
    return "targeted"


def rank_industries(
    combined_naics_hits: dict, naics_hierarchy: dict
) -> list[dict[str, Any]]:
    """Rank NAICS industries by accumulated tagging weight.

    Args:
        combined_naics_hits: Weighted NAICS hit map.
        naics_hierarchy: Loaded NAICS hierarchy.

    Returns:
        Up to 20 ranked industry records with code, name, relevance, and score.
    """
    sorted_hits = sorted(
        ((str(code), float(weight)) for code, weight in combined_naics_hits.items()),
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
    """Tag a single bill with industries, themes, CRS titles, and metadata.

    Args:
        bill: Parsed and enriched bill record.
        taxonomies: Loaded taxonomy bundle from ``load_taxonomies``.

    Returns:
        Complete deterministic tag record for one bill.
    """
    crs_result = tag_by_crs(bill, taxonomies.get("crs_map", {}))
    keyword_result = tag_by_keywords(bill, taxonomies.get("keywords", []))
    committee_result = tag_by_committee(bill, taxonomies.get("committees", {}))
    combined = combine_scores(crs_result, keyword_result, committee_result)
    combined_hits = combined["combined_naics_hits"]
    scope = classify_scope(
        combined_hits,
        taxonomies.get("naics_hierarchy", {}),
        bool(crs_result["universal_detected"]),
    )
    ranked_industries = rank_industries(
        combined_hits,
        taxonomies.get("naics_hierarchy", {}),
    )

    return {
        "bill_number": str(bill.get("bill_number") or "UNKNOWN"),
        "applicability_scope": scope,
        "industries": [
            {
                "naics": industry["naics"],
                "name": industry["name"],
                "relevance": industry["relevance"],
            }
            for industry in ranked_industries
        ],
        "regulatory_themes": combined["all_themes"],
        "crs_titles": list(crs_result["matched_titles"]),
        "universal_applicability": scope == "universal",
        "tagging_metadata": {
            "method_weights": METHOD_WEIGHTS,
            "confidence": crs_result["confidence"],
            "crs_matches": {
                "article_level": crs_result["article_match_count"],
                "title_level": crs_result["title_match_count"],
                "unmatched": len(crs_result["unmatched_refs"]),
            },
            "tagged_at": datetime.now(timezone.utc).isoformat(),
            "tagger_version": TAGGER_VERSION,
        },
    }


def build_theme_index(all_tags: dict) -> dict[str, list[str]]:
    """Build a reverse index from regulatory theme to bill numbers.

    Args:
        all_tags: Full industry index mapping bill numbers to tag records.

    Returns:
        Theme-to-bill-number reverse index.
    """
    theme_index: dict[str, list[str]] = {}

    for bill_number, tag_record in all_tags.items():
        if not isinstance(tag_record, dict):
            continue
        for theme in _string_list(tag_record.get("regulatory_themes")):
            theme_index.setdefault(theme, []).append(str(bill_number))

    return {theme: sorted(bills) for theme, bills in sorted(theme_index.items())}


def tag_all(
    input_dir: str = DEFAULT_INPUT_DIR,
    taxonomy_dir: str = DEFAULT_TAXONOMY_DIR,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Tag every parsed bill and write industry/theme index files.

    Args:
        input_dir: Directory containing ``*_parsed.json`` files.
        taxonomy_dir: Directory containing taxonomy JSON files.
        output_dir: Directory where index JSON files are written.

    Returns:
        Batch summary with scope, confidence, theme, and industry counts.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    taxonomies = load_taxonomies(taxonomy_dir)
    parsed_paths = sorted(input_path.glob("*_parsed.json"))

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


def _load_bill(path: Path) -> dict[str, Any]:
    """Load one parsed bill JSON object."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Top-level parsed bill JSON value is not an object.")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    """Write a JSON payload with deterministic formatting."""
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


def _add_naics_hits(
    hits: dict[str, float], codes: Any, weight: float, universal_detected: bool
) -> bool:
    """Add weighted NAICS hits and return the updated universal flag."""
    for code in _string_list(codes):
        if code == "ALL":
            universal_detected = True
            continue
        hits[code] = hits.get(code, 0.0) + weight
    return universal_detected


def _title_label(title_number: str, title_entry: dict[str, Any]) -> str:
    """Build a canonical title label for output records."""
    title_name = str(title_entry.get("title_name") or "").strip()
    return f"Title {title_number} - {title_name}" if title_name else f"Title {title_number}"


def _find_committee_mapping(
    committee_name: str, chamber: str, committee_map: dict
) -> dict[str, Any] | None:
    """Find the best committee mapping by chamber and normalized name."""
    if not committee_name or not isinstance(committee_map, dict):
        return None

    normalized_name = _normalize_committee_name(committee_name)
    for key, entry in committee_map.items():
        if not isinstance(entry, dict):
            continue
        mapped_chamber = str(entry.get("chamber") or "").lower()
        if chamber and mapped_chamber and chamber != mapped_chamber:
            continue

        candidates = {
            _normalize_committee_name(str(key)),
            _normalize_committee_name(CHAMBER_PREFIX_PATTERN.sub("", str(key))),
        }
        if normalized_name in candidates:
            return entry
        if any(
            normalized_name in candidate or candidate in normalized_name
            for candidate in candidates
        ):
            return entry

    return None


def _normalize_committee_name(value: str) -> str:
    """Normalize a committee name for deterministic fuzzy matching."""
    lowered = CHAMBER_PREFIX_PATTERN.sub("", value.lower())
    return NON_ALNUM_PATTERN.sub(" ", lowered).strip()


def _sector_for_code(code: str, naics_hierarchy: dict) -> str | None:
    """Resolve a NAICS code to its sector code."""
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
    """Return whether a NAICS code is a top-level sector in the hierarchy."""
    entry = naics_hierarchy.get(code) if isinstance(naics_hierarchy, dict) else None
    return isinstance(entry, dict) and entry.get("parent") is None


def _append_unique(values: list[str], value: str) -> None:
    """Append a string to a list only if it is non-empty and not already present."""
    if value and value not in values:
        values.append(value)


def _string_list(value: Any) -> list[str]:
    """Return stripped non-empty strings from a possible list."""
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Deterministically tag parsed Colorado bills by industry."
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help=f"Directory of *_parsed.json files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--taxonomy-dir",
        default=DEFAULT_TAXONOMY_DIR,
        help=f"Directory containing taxonomy JSON files. Default: {DEFAULT_TAXONOMY_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for generated index files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--single",
        help="Tag one parsed bill JSON file and print the result to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the industry tagger CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = _build_parser().parse_args(argv)

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
