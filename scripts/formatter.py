"""Format validated bill records into clean AI-readable output files.

This module is the final deterministic stage of the Project Geode bill
pipeline. It renders parsed and enriched bill JSON into consistent Markdown or
flattened JSON files designed for downstream AI consumption, without making any
network requests or LLM calls.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tqdm import tqdm

try:
    import jinja2
except ModuleNotFoundError as exc:
    jinja2 = None
    JINJA2_IMPORT_ERROR = exc
else:
    JINJA2_IMPORT_ERROR = None

DEFAULT_INPUT_DIR = "data/structured_output"
DEFAULT_OUTPUT_DIR = "data/structured_output"
DEFAULT_TEMPLATE_PATH = "scripts/templates/bill_template.md.j2"

LOGGER = logging.getLogger(__name__)


def load_template(
    template_path: str = DEFAULT_TEMPLATE_PATH,
) -> "jinja2.Template":
    """Load the bill Markdown template.

    Args:
        template_path: Path to the Jinja2 template file.

    Returns:
        Loaded Jinja2 template.

    Raises:
        RuntimeError: If Jinja2 is not installed.
    """
    jinja = _require_jinja2()
    path = Path(template_path)
    template_dir = path.parent if str(path.parent) else Path(".")
    environment = jinja.Environment(
        loader=jinja.FileSystemLoader(str(template_dir)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    return environment.get_template(path.name)


def format_bill_markdown(bill: dict, template: "jinja2.Template") -> str:
    """Render one bill record as AI-readable Markdown.

    Args:
        bill: Parsed and enriched bill record.
        template: Loaded Jinja2 template.

    Returns:
        Rendered Markdown string.
    """
    context = _template_context(bill)
    return template.render(**context).strip() + "\n"


def format_bill_json(bill: dict) -> str:
    """Render one bill record as cleaned flattened JSON.

    Args:
        bill: Parsed and enriched bill record.

    Returns:
        Pretty-printed JSON optimized for AI ingestion.
    """
    context = _template_context(bill)
    cleaned = {
        "bill_number": context["bill_number"],
        "title": context["title"],
        "effective_date": context["effective_date"],
        "status": context["status"],
        "generated_at": context["generated_at"],
        "parser_version": context["parser_version"],
        "summary_statistics": {
            "sections": context["section_count"],
            "crs_references": context["crs_reference_count"],
            "has_appropriation": context["has_appropriation"],
            "defined_terms": context["defined_terms_count"],
            "sponsor_count": context["sponsor_count"],
        },
        "sponsors": context["sponsors"],
        "sections": context["sections"],
        "crs_references": context["crs_references"],
        "entities": context["entities"],
        "appropriations": context["appropriations"],
        "metadata": context["metadata"],
    }
    return json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n"


def write_bill(
    bill: dict, output_dir: str = DEFAULT_OUTPUT_DIR, fmt: str = "markdown"
) -> str:
    """Write one formatted bill file.

    Args:
        bill: Parsed and enriched bill record.
        output_dir: Directory where final output files are written.
        fmt: Output format, either ``markdown`` or ``json``.

    Returns:
        Path to the written file.

    Raises:
        ValueError: If ``fmt`` is unsupported.
    """
    if fmt not in {"markdown", "json"}:
        raise ValueError(f"Unsupported output format: {fmt}")

    destination_dir = Path(output_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    bill_number = _safe_bill_number(bill)

    if fmt == "markdown":
        template = load_template()
        content = format_bill_markdown(bill, template)
        output_path = destination_dir / f"{bill_number}_final.md"
    else:
        content = format_bill_json(bill)
        output_path = destination_dir / f"{bill_number}_final.json"

    with output_path.open("w", encoding="utf-8", newline="\n") as file_obj:
        file_obj.write(content)

    return str(output_path)


def write_all(
    input_dir: str = DEFAULT_INPUT_DIR,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    fmt: str = "markdown",
) -> dict:
    """Format all parsed bill records in a directory.

    Args:
        input_dir: Directory containing ``*_parsed.json`` files.
        output_dir: Directory where final output files are written.
        fmt: Output format, one of ``markdown``, ``json``, or ``both``.

    Returns:
        Summary counts for processed, written, and failed bills.

    Raises:
        ValueError: If ``fmt`` is unsupported.
    """
    if fmt not in {"markdown", "json", "both"}:
        raise ValueError(f"Unsupported output format: {fmt}")

    input_path = Path(input_dir)
    parsed_paths = sorted(input_path.glob("*_parsed.json"))
    summary = {"processed": 0, "written": 0, "failed": 0}

    for parsed_path in tqdm(parsed_paths, desc="Formatting bills", unit="bill"):
        try:
            bill = _load_bill(parsed_path)
            formats = ("markdown", "json") if fmt == "both" else (fmt,)
            for output_format in formats:
                write_bill(bill, output_dir=output_dir, fmt=output_format)
                summary["written"] += 1
            summary["processed"] += 1
        except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
            LOGGER.error("Failed to format %s: %s", parsed_path, exc)
            summary["failed"] += 1

    return summary


def _load_bill(path: Path) -> dict:
    """Load one bill JSON object from disk."""
    with path.open("r", encoding="utf-8") as file_obj:
        bill = json.load(file_obj)
    if not isinstance(bill, dict):
        raise ValueError("top-level JSON value is not an object")
    return bill


def _template_context(bill: dict) -> dict[str, Any]:
    """Create a fully defaulted render context for Markdown and JSON output."""
    metadata = _dict_value(bill.get("metadata"))
    sponsors = _normalize_sponsors(bill.get("sponsors"))
    sections = _normalize_sections(bill.get("sections"))
    crs_references = _string_list(bill.get("crs_references"))
    entities = _normalize_entities(bill.get("entities"))
    appropriations = _normalize_appropriations(bill.get("appropriations"))
    effective_date = bill.get("effective_date")
    parser_version = str(metadata.get("parser_version") or "unknown")
    house_sponsors = sponsors["house_sponsors"]
    senate_sponsors = sponsors["senate_sponsors"]

    return {
        "bill_number": _safe_bill_number(bill),
        "title": _string_or_default(bill.get("title"), "Untitled"),
        "effective_date": effective_date if effective_date is not None else None,
        "effective_date_text": _string_or_default(effective_date, "Not specified"),
        "status": _string_or_default(metadata.get("overall_status"), "unknown"),
        "parser_version": parser_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "sponsors": sponsors,
        "house_sponsors_text": _join_or_none(house_sponsors),
        "senate_sponsors_text": _join_or_none(senate_sponsors),
        "sponsor_count": len(house_sponsors) + len(senate_sponsors),
        "section_count": len(sections),
        "crs_reference_count": len(crs_references),
        "has_appropriation": bool(appropriations.get("has_appropriation")),
        "has_appropriation_text": (
            "Yes" if appropriations.get("has_appropriation") else "No"
        ),
        "defined_terms_count": len(entities["definitions"]),
        "sections": sections,
        "crs_references": crs_references,
        "entities": entities,
        "appropriations": appropriations,
    }


def _normalize_sponsors(value: Any) -> dict[str, list[str]]:
    """Normalize sponsor lists from a bill record."""
    sponsors = _dict_value(value)
    return {
        "house_sponsors": _string_list(sponsors.get("house_sponsors")),
        "senate_sponsors": _string_list(sponsors.get("senate_sponsors")),
    }


def _normalize_sections(value: Any) -> list[dict[str, Any]]:
    """Normalize section dictionaries for template rendering."""
    if not isinstance(value, list):
        return []

    sections: list[dict[str, Any]] = []
    for index, raw_section in enumerate(value, start=1):
        section = _dict_value(raw_section)
        references = _string_list(section.get("crs_references"))
        action = section.get("action")
        sections.append(
            {
                "section_number": section.get("section_number", index),
                "heading": section.get("heading"),
                "action": action,
                "action_text": _string_or_default(action, "N/A"),
                "crs_references": references,
                "crs_references_text": _join_or_none(references),
                "text": _string_or_default(section.get("text"), ""),
            }
        )
    return sections


def _normalize_entities(value: Any) -> dict[str, Any]:
    """Normalize the entity extraction block."""
    entities = _dict_value(value)
    fiscal_impact = entities.get("fiscal_impact")
    return {
        "committees": _dict_list(entities.get("committees")),
        "dates": _dict_list(entities.get("dates")),
        "fiscal_impact": _normalize_fiscal_impact(fiscal_impact),
        "penalties": _dict_list(entities.get("penalties")),
        "definitions": _dict_list(entities.get("definitions")),
    }


def _normalize_fiscal_impact(value: Any) -> dict[str, Any]:
    """Normalize fiscal impact data for rendering."""
    fiscal = _dict_value(value)
    return {
        "dollar_amounts": _dict_list(fiscal.get("dollar_amounts")),
        "fte_mentions": _string_list(fiscal.get("fte_mentions")),
        "fund_names": _string_list(fiscal.get("fund_names")),
    }


def _normalize_appropriations(value: Any) -> dict[str, Any]:
    """Normalize appropriation data for rendering."""
    appropriations = _dict_value(value)
    amounts = _dict_list(appropriations.get("amounts"))
    return {
        "has_appropriation": bool(appropriations.get("has_appropriation")),
        "amounts": amounts,
    }


def _dict_value(value: Any) -> dict[str, Any]:
    """Return a dictionary value or an empty dictionary."""
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    """Return only dictionary items from a possible list."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    """Return stripped non-empty strings from a possible list."""
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            cleaned.append(item.strip())
    return cleaned


def _string_or_default(value: Any, default: str) -> str:
    """Return a stripped string or a default value."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _join_or_none(values: list[str]) -> str:
    """Join a string list, or return ``None`` for empty lists."""
    return ", ".join(values) if values else "None"


def _safe_bill_number(bill: dict) -> str:
    """Return a filesystem-safe bill number or fallback identifier."""
    bill_number = bill.get("bill_number")
    if isinstance(bill_number, str) and bill_number.strip():
        return re.sub(r"[^A-Za-z0-9_-]+", "_", bill_number.strip().upper())

    source_file = _dict_value(bill.get("metadata")).get("source_file")
    if isinstance(source_file, str) and source_file.strip():
        return re.sub(r"[^A-Za-z0-9_-]+", "_", Path(source_file).stem.upper())

    return "UNKNOWN_BILL"


def _require_jinja2() -> Any:
    """Return the Jinja2 module or raise a clear dependency error."""
    if jinja2 is None:
        raise RuntimeError(
            "Jinja2 is required for Markdown formatting. Install dependencies "
            "with pip install -r requirements.txt."
        ) from JINJA2_IMPORT_ERROR
    return jinja2


def _print_json(payload: Any) -> None:
    """Print a JSON payload to stdout."""
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Format parsed Colorado bill records for AI consumption."
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help=f"Directory of *_parsed.json files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for final files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json", "both"),
        default="markdown",
        help='Output format. Default: "markdown".',
    )
    parser.add_argument(
        "--single",
        help="Format one parsed bill JSON file instead of a full directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the formatter CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = _build_parser().parse_args(argv)

    if args.single:
        try:
            bill = _load_bill(Path(args.single))
            formats = ("markdown", "json") if args.format == "both" else (args.format,)
            written_paths = [
                write_bill(bill, output_dir=args.output_dir, fmt=output_format)
                for output_format in formats
            ]
        except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
            print(f"Failed to format bill: {exc}", file=sys.stderr)
            return 1

        _print_json({"written": written_paths})
        return 0

    summary = write_all(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        fmt=args.format,
    )
    _print_json(summary)
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
