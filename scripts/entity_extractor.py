"""Enrich parsed Colorado bill JSON with deterministic entity extraction."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from tqdm import tqdm

PATTERNS: dict[str, re.Pattern[str]] = {
    "month_date": re.compile(
        r"\b(?P<month>January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+"
        r"(?P<day>\d{1,2}),\s+(?P<year>\d{4})\b",
        re.IGNORECASE,
    ),
    "numeric_date": re.compile(
        r"\b(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{4})\b"
    ),
    "fiscal_year": re.compile(
        r"\b(?:the\s+)?(?P<start>\d{4})-(?P<end>\d{2})\s+fiscal\s+year\b",
        re.IGNORECASE,
    ),
    "dollar_amount": re.compile(r"\$\s*\d[\d,]*(?:\.\d{2})?"),
    "fte": re.compile(r"\b\d+(?:\.\d+)?\s*FTE\b", re.IGNORECASE),
    "fund_name": re.compile(
        r"\b(?:general fund|cash funds?|federal funds?|state education fund|"
        r"marijuana tax cash fund|highway users tax fund|[\w\s-]{2,80}\s+fund)\b",
        re.IGNORECASE,
    ),
    "penalty_class": re.compile(
        r"\bclass\s+(?P<class>[1-6]|one|two|three|four|five|six)\s+"
        r"(?P<kind>misdemeanor|felony)\b",
        re.IGNORECASE,
    ),
    "fine": re.compile(
        r"\b(?:fine|fined|civil penalty|penalty)\b[^.]{0,120}?"
        r"\$\s*\d[\d,]*(?:\.\d{2})?",
        re.IGNORECASE,
    ),
    "imprisonment": re.compile(
        r"\b(?:imprisonment|imprisoned|jail|county jail|incarcerat\w*)\b[^.]{0,160}",
        re.IGNORECASE,
    ),
    "definition_intro": re.compile(
        r"\bAs\s+used\s+in\s+this\s+(?P<section>section|part|article|subsection)"
        r"[^:]{0,120}:",
        re.IGNORECASE,
    ),
    "definition_quoted": re.compile(
        r"(?P<section>(?:\(\w+\)\s*){0,3})[\"'](?P<term>[^\"']{2,120})[\"']\s+"
        r"means\s+(?P<definition>.*?)(?=(?:\n\s*(?:\(\w+\)\s*){0,3}"
        r"[\"'][^\"']{2,120}[\"']\s+means\b)|\n\s*SECTION\s+\d+\.|$)",
        re.IGNORECASE | re.DOTALL,
    ),
    "definition_unquoted": re.compile(
        r"(?P<section>(?:\(\w+\)\s*){1,3})"
        r"(?P<term>[A-Z][A-Za-z0-9 ,'-]{2,80})\s+means\s+"
        r"(?P<definition>.*?)(?=(?:\n\s*(?:\(\w+\)\s*){1,3}"
        r"[A-Z][A-Za-z0-9 ,'-]{2,80}\s+means\b)|\n\s*SECTION\s+\d+\.|$)",
        re.IGNORECASE | re.DOTALL,
    ),
}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
LOGGER = logging.getLogger(__name__)


def extract_committees(
    text: str,
    lookup_path: str = "schemas/committee_lookup.json",
) -> list[dict]:
    """Extract committee mentions using a static lookup table.

    Args:
        text: Bill text or parsed bill JSON text fields.
        lookup_path: Path to committee lookup JSON.

    Returns:
        Committee mention dictionaries with committee, chamber, and context.
    """

    try:
        lookup = _load_committee_lookup(lookup_path)
        normalized_text = _normalize_match_text(text)
        matches: list[dict] = []
        seen: set[tuple[str, str, str]] = set()
        for committee in lookup:
            names = [committee["name"], *committee.get("aliases", [])]
            for candidate in names:
                normalized_candidate = _normalize_match_text(candidate)
                if not normalized_candidate:
                    continue
                position = normalized_text.find(normalized_candidate)
                if position == -1:
                    position = _partial_committee_position(normalized_text, normalized_candidate)
                if position == -1:
                    continue
                context = _sentence_context_from_normalized(text, normalized_text, position)
                key = (committee["name"], committee["chamber"], context)
                if key not in seen:
                    seen.add(key)
                    matches.append(
                        {
                            "committee": committee["name"],
                            "chamber": committee["chamber"],
                            "context": context,
                        }
                    )
                break
        return matches
    except Exception as exc:
        LOGGER.warning("committee extraction failed: %s", exc)
        return []


def extract_dates(text: str) -> list[dict]:
    """Extract dates and fiscal years from bill text.

    Args:
        text: Bill text.

    Returns:
        Date mention dictionaries with raw text, normalized value, and context.
    """

    results: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for pattern_name in ("month_date", "numeric_date", "fiscal_year"):
        for match in PATTERNS[pattern_name].finditer(text):
            raw_text = _clean_text(match.group(0))
            normalized = _normalize_date_match(pattern_name, match)
            if normalized is None:
                continue
            key = (raw_text, normalized)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "raw_text": raw_text,
                    "normalized": normalized,
                    "context": _sentence_context(text, match.start(), match.end()),
                }
            )
    return sorted(results, key=lambda item: item["context"])


def extract_fiscal_impact(text: str) -> dict | None:
    """Extract fiscal-impact amounts, FTE mentions, and fund names.

    Args:
        text: Bill text.

    Returns:
        Fiscal impact dictionary, or ``None`` when no fiscal signal is found.
    """

    try:
        dollar_amounts = [
            {
                "amount": _clean_amount(match.group(0)),
                "context": _sentence_context(text, match.start(), match.end()),
            }
            for match in PATTERNS["dollar_amount"].finditer(text)
        ]
        fte_mentions = _dedupe_preserve_order(
            _clean_text(match.group(0)) for match in PATTERNS["fte"].finditer(text)
        )
        fund_names = _dedupe_preserve_order(
            _clean_text(match.group(0)).title() for match in PATTERNS["fund_name"].finditer(text)
        )
        has_fiscal_signal = bool(dollar_amounts or fte_mentions or fund_names)
        has_fiscal_language = bool(
            re.search(r"\bfiscal\s+(?:note|impact|year)\b", text, re.IGNORECASE)
        )
        if not has_fiscal_signal and not has_fiscal_language:
            return None
        return {
            "dollar_amounts": dollar_amounts,
            "fte_mentions": fte_mentions,
            "fund_names": fund_names,
        }
    except Exception as exc:
        LOGGER.warning("fiscal impact extraction failed: %s", exc)
        return None


def extract_penalties(text: str) -> list[dict]:
    """Extract criminal, fine, and imprisonment penalty clauses.

    Args:
        text: Bill text.

    Returns:
        Penalty dictionaries with type, detail, and context.
    """

    penalties: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for match in PATTERNS["penalty_class"].finditer(text):
        kind = match.group("kind").lower()
        _append_penalty(penalties, seen, kind, match.group(0), text, match)
    for match in PATTERNS["fine"].finditer(text):
        _append_penalty(penalties, seen, "fine", match.group(0), text, match)
    for match in PATTERNS["imprisonment"].finditer(text):
        _append_penalty(penalties, seen, "other", match.group(0), text, match)
    return penalties


def extract_definitions(text: str) -> list[dict]:
    """Extract defined terms and definitions from bill text.

    Args:
        text: Bill text.

    Returns:
        Definition dictionaries with term, definition, and section marker.
    """

    definitions: list[dict] = []
    seen_terms: set[str] = set()
    for pattern_name in ("definition_quoted", "definition_unquoted"):
        for match in PATTERNS[pattern_name].finditer(text):
            term = _clean_definition_term(match.group("term"))
            if not term:
                continue
            key = term.casefold()
            if key in seen_terms:
                continue
            definition = _clean_definition_text(match.group("definition"))
            if not definition:
                continue
            seen_terms.add(key)
            definitions.append(
                {
                    "term": term,
                    "definition": definition,
                    "section": _clean_text(match.group("section")) or "",
                }
            )
    return definitions


def enrich_bill(
    parsed_json_path: str,
    output_dir: str = "data/structured_output",
    lookup_path: str = "schemas/committee_lookup.json",
) -> str:
    """Add extracted entities to one parsed bill JSON file.

    Args:
        parsed_json_path: Path to a ``*_parsed.json`` file.
        output_dir: Directory containing or receiving the parsed JSON file.
        lookup_path: Committee lookup JSON path.

    Returns:
        Path to the enriched parsed JSON file.
    """

    source_path = Path(parsed_json_path)
    bill = _read_json(source_path)
    text = _bill_text(bill)
    bill["entities"] = {
        "committees": extract_committees(text, lookup_path),
        "dates": extract_dates(text),
        "fiscal_impact": extract_fiscal_impact(text),
        "penalties": extract_penalties(text),
        "definitions": extract_definitions(text),
    }
    output_path = Path(output_dir) / source_path.name
    _write_json(output_path, bill)
    return str(output_path)


def enrich_all(
    input_dir: str = "data/structured_output",
    lookup_path: str = "schemas/committee_lookup.json",
) -> dict:
    """Enrich every parsed bill JSON file in a directory.

    Args:
        input_dir: Directory containing ``*_parsed.json`` files.
        lookup_path: Committee lookup JSON path.

    Returns:
        Summary dictionary with processed and failed counts.
    """

    parsed_paths = sorted(Path(input_dir).glob("*_parsed.json"))
    summary: dict[str, Any] = {"processed": 0, "failed": 0, "failures": []}
    for parsed_path in tqdm(parsed_paths, desc="Enriching bills", unit="bill"):
        try:
            enrich_bill(str(parsed_path), input_dir, lookup_path)
            summary["processed"] += 1
        except Exception as exc:
            summary["failed"] += 1
            failure = {"file": parsed_path.name, "error": str(exc)}
            summary["failures"].append(failure)
            LOGGER.error("%s: enrichment failed: %s", parsed_path.name, exc)
    return summary


def _load_committee_lookup(lookup_path: str) -> list[dict]:
    """Load and validate committee lookup entries.

    Args:
        lookup_path: Lookup JSON path.

    Returns:
        Committee entry list.
    """

    payload = _read_json(Path(lookup_path))
    committees = payload.get("committees", [])
    return committees if isinstance(committees, list) else []


def _bill_text(bill: dict) -> str:
    """Recover searchable text from a parsed bill record.

    Args:
        bill: Parsed bill dictionary.

    Returns:
        Combined searchable text.
    """

    parts = [
        str(bill.get("title", "")),
        str(bill.get("effective_date", "")),
        json.dumps(bill.get("appropriations"), ensure_ascii=False),
    ]
    for section in bill.get("sections", []) or []:
        if isinstance(section, dict):
            parts.append(str(section.get("heading", "")))
            parts.append(str(section.get("text", "")))
    return "\n\n".join(part for part in parts if part and part != "null")


def _normalize_date_match(pattern_name: str, match: re.Match[str]) -> str | None:
    """Normalize a date regex match.

    Args:
        pattern_name: Name of the date pattern.
        match: Regex match object.

    Returns:
        Normalized date string or fiscal-year label.
    """

    try:
        if pattern_name == "month_date":
            month = MONTHS[match.group("month").casefold()]
            day = int(match.group("day"))
            year = int(match.group("year"))
            return datetime(year, month, day).date().isoformat()
        if pattern_name == "numeric_date":
            month = int(match.group("month"))
            day = int(match.group("day"))
            year = int(match.group("year"))
            return datetime(year, month, day).date().isoformat()
        return f"FY {match.group('start')}-{match.group('end')}"
    except (KeyError, ValueError):
        return None


def _append_penalty(
    penalties: list[dict],
    seen: set[tuple[str, str]],
    penalty_type: str,
    detail: str,
    text: str,
    match: re.Match[str],
) -> None:
    """Append one penalty if it has not already been recorded.

    Args:
        penalties: Mutable penalty list.
        seen: Deduplication set.
        penalty_type: Penalty type label.
        detail: Matched penalty detail.
        text: Source text.
        match: Regex match object.
    """

    clean_detail = _clean_text(detail)
    key = (penalty_type, clean_detail.casefold())
    if key in seen:
        return
    seen.add(key)
    penalties.append(
        {
            "type": penalty_type,
            "detail": clean_detail,
            "context": _sentence_context(text, match.start(), match.end()),
        }
    )


def _partial_committee_position(text: str, committee_name: str) -> int:
    """Find a committee by meaningful token containment.

    Args:
        text: Normalized text.
        committee_name: Normalized committee candidate.

    Returns:
        Position in text, or ``-1``.
    """

    tokens = [token for token in committee_name.split() if len(token) > 2]
    if len(tokens) < 2:
        return -1
    phrase = " ".join(tokens[: min(len(tokens), 3)])
    position = text.find(phrase)
    if position == -1:
        return -1
    window = text[position : position + max(len(committee_name), 120)]
    matched_tokens = sum(1 for token in tokens if token in window)
    return position if matched_tokens / len(tokens) >= 0.6 else -1


def _sentence_context(text: str, start: int, end: int) -> str:
    """Return the surrounding sentence for a match span.

    Args:
        text: Source text.
        start: Match start index.
        end: Match end index.

    Returns:
        Clean surrounding sentence or bounded context.
    """

    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start))
    right_period = text.find(".", end)
    right_newline = text.find("\n", end)
    right_candidates = [value for value in (right_period, right_newline) if value != -1]
    context_start = left + 1 if left != -1 else max(0, start - 160)
    context_end = min(right_candidates) + 1 if right_candidates else min(len(text), end + 160)
    return _clean_text(text[context_start:context_end])


def _sentence_context_from_normalized(
    original_text: str,
    normalized_text: str,
    normalized_position: int,
) -> str:
    """Approximate context for a match found in normalized text.

    Args:
        original_text: Original bill text.
        normalized_text: Normalized bill text.
        normalized_position: Match position in normalized text.

    Returns:
        Surrounding sentence/context from original text when possible.
    """

    if not normalized_text:
        return ""
    ratio = normalized_position / len(normalized_text)
    original_position = int(len(original_text) * ratio)
    return _sentence_context(original_text, original_position, original_position)


def _normalize_match_text(value: str) -> str:
    """Normalize text for case-insensitive containment matching.

    Args:
        value: Raw text.

    Returns:
        Normalized alphanumeric text.
    """

    normalized = re.sub(r"&", " and ", value.casefold())
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _clean_definition_term(value: str) -> str:
    """Clean a candidate defined term.

    Args:
        value: Raw term.

    Returns:
        Cleaned term.
    """

    return _clean_text(value).strip(" \"'“”.,;:")


def _clean_definition_text(value: str) -> str:
    """Clean a candidate definition body.

    Args:
        value: Raw definition.

    Returns:
        Cleaned definition text.
    """

    cleaned = _clean_text(value)
    return cleaned.strip(" ;")


def _clean_amount(value: str) -> str:
    """Normalize a dollar amount string.

    Args:
        value: Raw dollar amount.

    Returns:
        Dollar amount with internal spaces removed.
    """

    return re.sub(r"\s+", "", value)


def _clean_text(value: str) -> str:
    """Normalize whitespace in text.

    Args:
        value: Raw text.

    Returns:
        Cleaned text.
    """

    return re.sub(r"\s+", " ", value).strip()


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    """Deduplicate strings while preserving first-seen order.

    Args:
        values: Candidate strings.

    Returns:
        Deduplicated list.
    """

    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _read_json(path: Path) -> dict:
    """Read a JSON object from disk.

    Args:
        path: JSON path.

    Returns:
        Parsed JSON object.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _write_json(path: Path, payload: dict) -> None:
    """Write a JSON object using deterministic formatting.

    Args:
        path: Target path.
        payload: JSON-serializable object.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser.

    Returns:
        Configured argument parser.
    """

    parser = argparse.ArgumentParser(description="Enrich parsed Colorado bill JSON.")
    parser.add_argument(
        "--input-dir",
        default="data/structured_output",
        help='Directory containing parsed JSON, default "data/structured_output".',
    )
    parser.add_argument("--single", help="Optional path to one parsed JSON file.")
    parser.add_argument(
        "--lookup-path",
        default="schemas/committee_lookup.json",
        help="Committee lookup JSON path.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the entity enrichment CLI.

    Args:
        argv: Optional argument sequence.

    Returns:
        Process exit code.
    """

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)
    args = _build_parser().parse_args(argv)
    if args.single:
        output_path = enrich_bill(
            args.single,
            Path(args.single).parent.as_posix(),
            args.lookup_path,
        )
        print(f"Enriched 1 bill. output={output_path}")
        return 0
    summary = enrich_all(args.input_dir, args.lookup_path)
    print("Processed {processed}. Failed {failed}.".format(**summary))
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
