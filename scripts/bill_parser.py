"""Parse extracted Colorado bill text with deterministic legislative rules."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from tqdm import tqdm

PARSER_VERSION = "1.0.0"
SECTION_SYMBOL = "\u00a7"

PATTERNS: dict[str, re.Pattern[str]] = {
    # Matches canonical Colorado bill numbers such as HB25-1001 or SB26-0033.
    "bill_number": re.compile(
        r"\b(?P<prefix>HB|SB)\s*(?P<year>\d{2})[-\s]?(?P<number>\d{4})\b",
        re.IGNORECASE,
    ),
    # Matches left-margin legislative line numbers that are removed when sequential.
    "line_number": re.compile(r"^(?P<indent>\s*)(?P<number>\d{1,4})\s+(?P<body>.+)$"),
    # Captures the CONCERNING title clause near the top before sponsors or sections.
    "title_clause": re.compile(
        r"\bCONCERNING\b(?P<body>.*?)(?=\n\s*(?:BY\s+(?:REPRESENTATIVE|SENATOR)|"
        r"BE IT ENACTED|SECTION\s+\d+\.|Bill Summary|$))",
        re.IGNORECASE | re.DOTALL,
    ),
    # Captures House sponsor blocks after BY REPRESENTATIVE(S).
    "house_sponsors": re.compile(
        r"\bBY\s+REPRESENTATIVE(?:\(S\)|S)?\s+(?P<names>.*?)(?=\bBY\s+SENATOR|"
        r"\n\s*(?:A\s+BILL|CONCERNING|Bill Summary|Committee|SECTION\s+\d+\.|"
        r"BE IT ENACTED|$))",
        re.IGNORECASE | re.DOTALL,
    ),
    # Captures Senate sponsor blocks after BY SENATOR(S).
    "senate_sponsors": re.compile(
        r"\bBY\s+SENATOR(?:\(S\)|S)?\s+(?P<names>.*?)(?=\bBY\s+REPRESENTATIVE|"
        r"\n\s*(?:A\s+BILL|CONCERNING|Bill Summary|Committee|SECTION\s+\d+\.|"
        r"BE IT ENACTED|$))",
        re.IGNORECASE | re.DOTALL,
    ),
    # Matches committee assignment lines near bill front matter.
    "committee_assignment": re.compile(
        r"\b(?:House|Senate)?\s*Committee\s+on\s+[A-Za-z ,&-]+",
        re.IGNORECASE,
    ),
    # Matches the mandatory enacting clause used to separate front matter from law text.
    "enacting_clause": re.compile(
        r"BE\s+IT\s+ENACTED\s+BY\s+THE\s+GENERAL\s+ASSEMBLY\s+OF\s+THE\s+STATE\s+"
        r"OF\s+COLORADO:",
        re.IGNORECASE,
    ),
    # Matches numbered bill sections such as SECTION 1. and SECTION 12.
    "section_header": re.compile(r"(?m)^\s*SECTION\s+(?P<number>\d+)\.\s*"),
    # Matches nested subsection markers like (1), (a), (I), and (A).
    "subsection_marker": re.compile(r"\((?:\d+|[a-z]|[IVXLCDM]+|[A-Z])\)"),
    # Matches CRS citations with section symbol or C.R.S./Colorado Revised Statutes suffix.
    "crs_reference": re.compile(
        r"(?:\bsection\s+|"
        + SECTION_SYMBOL
        + r"\s*)?(?P<crs>\d{1,2}(?:\.\d+)?-\d{1,3}(?:\.\d+)?-\d{1,4}(?:\.\d+)?)"
        r"(?:\s*\([^)]+\))*\s*,?\s*(?:C\.?\s*R\.?\s*S\.?|Colorado\s+Revised\s+Statutes)",
        re.IGNORECASE,
    ),
    # Detects ordinary amend instructions such as "is amended to read".
    "amended": re.compile(r"\bis\s+amended(?:\s+to\s+read)?\b", re.IGNORECASE),
    # Detects added statutory text such as "BY THE ADDITION OF" or "is added".
    "addition": re.compile(
        r"\b(?:BY\s+THE\s+ADDITION\s+OF|is\s+added|add\s+a\s+new)\b",
        re.IGNORECASE,
    ),
    # Detects repeal instructions including "is REPEALED".
    "repealed": re.compile(
        r"\bis\s+(?:hereby\s+)?REPEALED\b|\bREPEAL(?:ED|ING)?\b",
        re.IGNORECASE,
    ),
    # Detects new enactments that are not obviously amendments to existing CRS text.
    "new_statute": re.compile(
        r"\b(?:new\s+(?:article|part|section)|is\s+enacted)\b",
        re.IGNORECASE,
    ),
    # Captures headed effective-date sections near the end of Colorado bills.
    "effective_date_heading": re.compile(
        r"(?is)(?:SECTION\s+\d+\.\s*)?Effective\s+date\.(?P<body>.*?)(?=SECTION\s+\d+\.|$)"
    ),
    # Captures sentence-form effective-date clauses when no heading is present.
    "effective_date_sentence": re.compile(
        r"(?is)(this\s+act\s+takes\s+effect.*?)(?=(?:\.\s+SECTION\s+\d+\.|"
        r"\.\s*$|\n\s*SECTION\s+\d+\.))"
    ),
    # Detects sections or clauses involving appropriations.
    "appropriation": re.compile(r"\bappropriat(?:e|ed|ion|ions)\b", re.IGNORECASE),
    # Matches dollar amounts with optional commas and cents.
    "dollar_amount": re.compile(r"\$\s*\d[\d,]*(?:\.\d{2})?"),
    # Matches common Colorado fund names near appropriation amounts.
    "fund_name": re.compile(
        r"\b(?:general fund|cash funds?|federal funds?|state education fund|"
        r"marijuana tax cash fund|highway users tax fund|[\w\s-]{2,80}\s+fund)\b",
        re.IGNORECASE,
    ),
}

LOGGER = logging.getLogger(__name__)


def strip_line_numbers(text: str) -> str:
    """Remove sequential legislative line numbers from the left margin.

    Args:
        text: Raw extracted bill text.

    Returns:
        Text with likely sequential line numbers removed.
    """

    try:
        lines = text.splitlines()
        parsed = [PATTERNS["line_number"].match(line) for line in lines]
        numbers = [int(match.group("number")) if match else None for match in parsed]
        cleaned_lines = []
        for index, line in enumerate(lines):
            match = parsed[index]
            if match is None:
                cleaned_lines.append(line)
                continue
            current = numbers[index]
            previous_number = _nearest_number(numbers, index, -1)
            next_number = _nearest_number(numbers, index, 1)
            if _is_sequential_line_number(current, previous_number, next_number):
                cleaned_lines.append(f"{match.group('indent')}{match.group('body')}")
            else:
                cleaned_lines.append(line)
        return "\n".join(cleaned_lines)
    except Exception as exc:
        LOGGER.warning("line-number stripping failed: %s", exc)
        return text


def parse_bill_number(text: str) -> str | None:
    """Extract the canonical Colorado bill number.

    Args:
        text: Bill text or source filename.

    Returns:
        Canonical bill number such as ``HB25-1001``, or ``None``.
    """

    try:
        match = PATTERNS["bill_number"].search(text)
        if match is None:
            return None
        return (
            f"{match.group('prefix').upper()}"
            f"{match.group('year')}-{match.group('number')}"
        )
    except Exception as exc:
        LOGGER.warning("bill-number parsing failed: %s", exc)
        return None


def parse_title(text: str) -> str | None:
    """Extract and normalize the CONCERNING title clause.

    Args:
        text: Full bill text.

    Returns:
        Title-cased CONCERNING clause, or ``None``.
    """

    try:
        front_matter = _front_matter(strip_line_numbers(text))
        match = PATTERNS["title_clause"].search(front_matter)
        if match is None:
            return None
        raw_title = "CONCERNING " + match.group("body")
        clean_title = _clean_title_text(raw_title)
        return clean_title.title() if clean_title else None
    except Exception as exc:
        LOGGER.warning("title parsing failed: %s", exc)
        return None


def parse_sponsors(text: str) -> dict:
    """Parse House and Senate bill sponsors from bill front matter.

    Args:
        text: Full bill text.

    Returns:
        Dictionary with ``house_sponsors`` and ``senate_sponsors`` lists.
    """

    sponsors = {"house_sponsors": [], "senate_sponsors": []}
    try:
        front_matter = _front_matter(strip_line_numbers(text))
        house_match = PATTERNS["house_sponsors"].search(front_matter)
        senate_match = PATTERNS["senate_sponsors"].search(front_matter)
        if house_match is not None:
            sponsors["house_sponsors"] = _split_sponsor_names(house_match.group("names"))
        if senate_match is not None:
            sponsors["senate_sponsors"] = _split_sponsor_names(senate_match.group("names"))
    except Exception as exc:
        LOGGER.warning("sponsor parsing failed: %s", exc)
    return sponsors


def parse_sections(text: str) -> list[dict]:
    """Split a Colorado bill into numbered sections.

    Args:
        text: Full bill text.

    Returns:
        List of section dictionaries with number, heading, text, CRS refs, and action.
    """

    try:
        clean_text = strip_line_numbers(text)
        matches = list(PATTERNS["section_header"].finditer(clean_text))
        sections: list[dict] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(clean_text)
            section_text = clean_text[start:end].strip()
            sections.append(
                {
                    "section_number": int(match.group("number")),
                    "heading": _extract_section_heading(section_text),
                    "text": section_text,
                    "crs_references": parse_crs_references(section_text),
                    "action": _detect_section_action(section_text),
                }
            )
        return sections
    except Exception as exc:
        LOGGER.warning("section parsing failed: %s", exc)
        return []


def parse_crs_references(text: str) -> list[str]:
    """Extract all Colorado Revised Statutes references.

    Args:
        text: Text to scan for CRS citations.

    Returns:
        Deduplicated citations normalized as ``§ XX-XX-XXX, C.R.S.``.
    """

    try:
        references: list[str] = []
        seen: set[str] = set()
        for match in PATTERNS["crs_reference"].finditer(text):
            citation = f"{SECTION_SYMBOL} {match.group('crs')}, C.R.S."
            if citation not in seen:
                seen.add(citation)
                references.append(citation)
        return references
    except Exception as exc:
        LOGGER.warning("CRS reference parsing failed: %s", exc)
        return []


def parse_effective_date(text: str) -> str | None:
    """Extract the raw effective-date clause.

    Args:
        text: Full bill text.

    Returns:
        Raw effective-date clause text, or ``None``.
    """

    try:
        clean_text = strip_line_numbers(text)
        heading_match = PATTERNS["effective_date_heading"].search(clean_text)
        if heading_match is not None:
            return _clean_clause(f"Effective date. {heading_match.group('body')}")
        sentence_match = PATTERNS["effective_date_sentence"].search(clean_text)
        if sentence_match is not None:
            return _clean_clause(sentence_match.group(1))
        return None
    except Exception as exc:
        LOGGER.warning("effective-date parsing failed: %s", exc)
        return None


def parse_appropriations(text: str) -> dict | None:
    """Detect appropriation content and extract amounts with fund names.

    Args:
        text: Full bill text.

    Returns:
        Appropriation dictionary, or ``None`` when no appropriation appears.
    """

    try:
        clean_text = strip_line_numbers(text)
        if PATTERNS["appropriation"].search(clean_text) is None:
            return None
        amounts = []
        for match in PATTERNS["dollar_amount"].finditer(clean_text):
            context = _window(clean_text, match.start(), match.end(), 220)
            fund = _extract_fund_name(context)
            amounts.append({"amount": _clean_amount(match.group(0)), "fund": fund})
        return {"has_appropriation": True, "amounts": amounts}
    except Exception as exc:
        LOGGER.warning("appropriation parsing failed: %s", exc)
        return None


def parse_bill(extracted_json_path: str) -> dict:
    """Parse one extracted-text JSON file into a structured bill record.

    Args:
        extracted_json_path: Path to an extractor output JSON file.

    Returns:
        Structured parsed bill record.
    """

    path = Path(extracted_json_path)
    payload = _read_extraction_payload(path)
    full_text = strip_line_numbers(str(payload.get("full_text", "")))
    source_file = str(payload.get("source_file", path.name))
    bill_number = parse_bill_number(full_text) or parse_bill_number(source_file)
    bill_number = bill_number or _fallback_bill_number(path)
    return {
        "bill_number": bill_number,
        "title": parse_title(full_text) or "",
        "sponsors": parse_sponsors(full_text),
        "sections": parse_sections(full_text),
        "crs_references": parse_crs_references(full_text),
        "effective_date": parse_effective_date(full_text),
        "appropriations": parse_appropriations(full_text),
        "metadata": {
            "source_file": source_file,
            "page_count": int(payload.get("page_count", 0) or 0),
            "parse_timestamp": datetime.now(timezone.utc).isoformat(),
            "parser_version": PARSER_VERSION,
        },
    }


def parse_all(
    input_dir: str = "data/extracted_text",
    output_dir: str = "data/structured_output",
) -> dict:
    """Parse all extracted-text JSON files in a directory.

    Args:
        input_dir: Directory containing ``*_extracted.json`` files.
        output_dir: Directory where parsed bill JSON should be written.

    Returns:
        Batch summary with processed, skipped, failed, and failure details.
    """

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"processed": 0, "skipped": 0, "failed": 0, "failures": []}
    extracted_paths = sorted(input_path.glob("*.json"))

    for extracted_path in tqdm(extracted_paths, desc="Parsing bills", unit="bill"):
        candidate_output = output_path / f"{_base_stem(extracted_path)}_parsed.json"
        if candidate_output.exists():
            summary["skipped"] += 1
            continue
        try:
            record = parse_bill(str(extracted_path))
            bill_number = _safe_file_stem(
                str(record.get("bill_number") or _base_stem(extracted_path))
            )
            final_output = output_path / f"{bill_number}_parsed.json"
            if final_output.exists():
                summary["skipped"] += 1
                continue
            _write_json(final_output, record)
            summary["processed"] += 1
        except Exception as exc:
            summary["failed"] += 1
            failure = {"file": extracted_path.name, "error": str(exc)}
            summary["failures"].append(failure)
            LOGGER.error("%s: parse failed: %s", extracted_path.name, exc)
    return summary


def _front_matter(text: str) -> str:
    """Return the pre-enacting-clause portion of a bill.

    Args:
        text: Full bill text.

    Returns:
        Front-matter text slice.
    """

    enacting = PATTERNS["enacting_clause"].search(text)
    section = PATTERNS["section_header"].search(text)
    cut_points = [match.start() for match in (enacting, section) if match is not None]
    end = min(cut_points) if cut_points else min(len(text), 8000)
    return text[:end]


def _split_sponsor_names(raw_names: str) -> list[str]:
    """Split and normalize sponsor names from a sponsor block.

    Args:
        raw_names: Raw sponsor block text.

    Returns:
        Ordered sponsor names.
    """

    cleaned = re.sub(r"\([^)]*\)", " ", raw_names)
    cleaned = re.sub(
        r"\b(?:Representative|Representatives|Senator|Senators)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\b(?:and|with|also)\b", ",", cleaned, flags=re.IGNORECASE)
    pieces = re.split(r"[,;\n]+", cleaned)
    sponsors: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        name = _clean_person_name(piece)
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            sponsors.append(name)
    return sponsors


def _clean_person_name(value: str) -> str:
    """Clean one legislator name.

    Args:
        value: Raw sponsor name candidate.

    Returns:
        Normalized name string.
    """

    cleaned = re.sub(r"\s+", " ", value).strip(" .:-")
    cleaned = re.sub(
        r"\b(?:prime|primary|co-?sponsors?|sponsors?)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", cleaned).strip(" .:-")


def _clean_title_text(value: str) -> str:
    """Normalize whitespace and punctuation in a title clause.

    Args:
        value: Raw title text.

    Returns:
        Clean title text.
    """

    cleaned = re.sub(r"\s+", " ", value)
    cleaned = re.sub(r"\bA\s+BILL\s+FOR\s+AN\s+ACT\b", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" .:-") + ("." if cleaned.strip(" .:-") else "")


def _extract_section_heading(section_text: str) -> str | None:
    """Extract a short section heading when one is obvious.

    Args:
        section_text: Text for one bill section.

    Returns:
        Heading string or ``None``.
    """

    first_line = next((line.strip() for line in section_text.splitlines() if line.strip()), "")
    if not first_line or len(first_line) > 160:
        return None
    if re.search(
        r"\b(?:Colorado Revised Statutes|is amended|is repealed)\b",
        first_line,
        re.IGNORECASE,
    ):
        return None
    if first_line.endswith("."):
        return first_line
    return None


def _detect_section_action(section_text: str) -> str | None:
    """Detect the legislative action for one section.

    Args:
        section_text: Text for one bill section.

    Returns:
        ``amend``, ``add``, ``repeal``, ``new``, or ``None``.
    """

    lead_text = section_text[:1200]
    if PATTERNS["repealed"].search(lead_text):
        return "repeal"
    if PATTERNS["addition"].search(lead_text):
        return "add"
    if PATTERNS["amended"].search(lead_text):
        return "amend"
    if PATTERNS["new_statute"].search(lead_text):
        return "new"
    return None


def _clean_clause(value: str) -> str | None:
    """Clean a raw effective-date clause.

    Args:
        value: Raw clause text.

    Returns:
        Cleaned clause or ``None``.
    """

    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _extract_fund_name(context: str) -> str:
    """Extract a fund name from text near an appropriation amount.

    Args:
        context: Text surrounding a dollar amount.

    Returns:
        Best fund-name match or an empty string.
    """

    match = PATTERNS["fund_name"].search(context)
    if match is None:
        return ""
    return re.sub(r"\s+", " ", match.group(0)).strip().title()


def _clean_amount(value: str) -> str:
    """Normalize a dollar amount string.

    Args:
        value: Raw dollar amount.

    Returns:
        Cleaned amount string.
    """

    return re.sub(r"\s+", "", value)


def _window(text: str, start: int, end: int, radius: int) -> str:
    """Return a bounded text window around an index range.

    Args:
        text: Source text.
        start: Match start.
        end: Match end.
        radius: Number of characters to include on each side.

    Returns:
        Text window.
    """

    return text[max(0, start - radius) : min(len(text), end + radius)]


def _nearest_number(numbers: list[int | None], index: int, direction: int) -> int | None:
    """Find the nearest numbered line before or after an index.

    Args:
        numbers: Parsed line-start numbers.
        index: Current line index.
        direction: ``-1`` for previous or ``1`` for next.

    Returns:
        Nearest number or ``None``.
    """

    cursor = index + direction
    while 0 <= cursor < len(numbers):
        number = numbers[cursor]
        if number is not None:
            return number
        cursor += direction
    return None


def _is_sequential_line_number(
    current: int | None,
    previous_number: int | None,
    next_number: int | None,
) -> bool:
    """Determine whether a line-start number is likely a margin number.

    Args:
        current: Current line-start number.
        previous_number: Nearest prior line-start number.
        next_number: Nearest next line-start number.

    Returns:
        ``True`` when the number participates in a sequence or page reset.
    """

    if current is None or current > 200:
        return False
    if previous_number is not None and current == previous_number + 1:
        return True
    if previous_number is not None and current == 1 and previous_number >= 10:
        return True
    return next_number is not None and next_number == current + 1


def _read_extraction_payload(path: Path) -> dict:
    """Read an extractor JSON payload defensively.

    Args:
        path: Extractor JSON path.

    Returns:
        Extractor payload, or an empty fallback payload.
    """

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.error("%s: could not read extracted JSON: %s", path.name, exc)
        return {"source_file": path.name, "page_count": 0, "full_text": ""}
    if isinstance(payload, dict):
        return payload
    return {"source_file": path.name, "page_count": 0, "full_text": ""}


def _fallback_bill_number(path: Path) -> str:
    """Build a fallback bill number from the extracted JSON filename.

    Args:
        path: Extracted JSON path.

    Returns:
        Filename-derived fallback identifier.
    """

    return _base_stem(path).upper()


def _base_stem(path: Path) -> str:
    """Return the bill-ish stem for an extracted JSON path.

    Args:
        path: Extracted JSON path.

    Returns:
        Stem without the ``_extracted`` suffix.
    """

    stem = path.stem
    return stem[:-10] if stem.endswith("_extracted") else stem


def _safe_file_stem(value: str) -> str:
    """Convert a value into a safe output filename stem.

    Args:
        value: Raw filename stem.

    Returns:
        Safe filename stem.
    """

    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "UNKNOWN"


def _write_json(path: Path, payload: dict) -> None:
    """Write parsed bill JSON using deterministic formatting.

    Args:
        path: Target JSON path.
        payload: JSON-serializable payload.
    """

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser.

    Returns:
        Configured parser.
    """

    parser = argparse.ArgumentParser(description="Parse extracted Colorado bill text.")
    parser.add_argument(
        "--input-dir",
        default="data/extracted_text",
        help='Directory containing extraction JSON files, default "data/extracted_text".',
    )
    parser.add_argument(
        "--output-dir",
        default="data/structured_output",
        help='Directory for parsed bill JSON, default "data/structured_output".',
    )
    parser.add_argument("--single", help="Optional path to one extracted JSON file.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the bill parser command-line interface.

    Args:
        argv: Optional argument sequence.

    Returns:
        Process exit code.
    """

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)
    args = _build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.single:
        record = parse_bill(args.single)
        bill_number = _safe_file_stem(str(record.get("bill_number") or "UNKNOWN"))
        output_path = output_dir / f"{bill_number}_parsed.json"
        _write_json(output_path, record)
        print(f"Parsed 1 bill. output={output_path}")
        return 0

    summary = parse_all(args.input_dir, args.output_dir)
    print(
        "Processed {processed}. Skipped {skipped}. Failed {failed}.".format(**summary)
    )
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
