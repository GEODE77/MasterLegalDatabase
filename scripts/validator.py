"""Validate structured Colorado bill records against schema and integrity rules.

This module is the deterministic validation stage for Project Geode's bill
pipeline. It checks enriched parsed bill records against the local JSON Schema,
adds logical completeness checks that schema alone cannot express, and writes a
batch validation report for downstream review.
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

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from tqdm import tqdm

DEFAULT_SCHEMA_PATH = "schemas/bill_schema.json"
DEFAULT_INPUT_DIR = "data/structured_output"

LOGGER = logging.getLogger(__name__)

# Matches normalized Colorado Revised Statutes references emitted by bill_parser.
CRS_REFERENCE_RE = re.compile(
    r"^\u00a7\s+(?P<title>\d{1,2}(?:\.\d+)?)-"
    r"\d{1,3}(?:\.\d+)?-\d{1,4}(?:\.\d+)?,\s+C\.R\.S\.$"
)


def _load_json(path: Path) -> Any:
    """Load a JSON document from disk using UTF-8."""
    with path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def _write_json(path: Path, payload: Any) -> None:
    """Write a JSON document using UTF-8 and stable indentation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2, ensure_ascii=False)
        file_obj.write("\n")


def _format_schema_error(error: Any) -> str:
    """Convert a jsonschema error into a concise path-aware message."""
    location = ".".join(str(part) for part in error.absolute_path)
    prefix = location if location else "<root>"
    return f"{prefix}: {error.message}"


def _is_iso_datetime(value: Any) -> bool:
    """Return True when a value can be parsed as an ISO 8601 datetime."""
    if not isinstance(value, str) or not value.strip():
        return False

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return True


def _as_string_list(value: Any) -> list[str]:
    """Return a list containing only string values from a possible array."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _extract_crs_title(reference: str) -> str | None:
    """Extract the CRS title component from a normalized CRS reference."""
    match = CRS_REFERENCE_RE.match(reference)
    if not match:
        return None
    return match.group("title")


def validate_schema(
    bill: dict[str, Any], schema_path: str = DEFAULT_SCHEMA_PATH
) -> dict[str, Any]:
    """Validate a bill record against the local JSON Schema.

    Args:
        bill: Parsed and enriched bill record to validate.
        schema_path: Path to the JSON Schema file.

    Returns:
        A validation result with a boolean ``valid`` flag and error messages.
    """
    try:
        schema = _load_json(Path(schema_path))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(
            validator.iter_errors(bill),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        return {"valid": False, "errors": [f"Schema validation setup failed: {exc}"]}

    return {
        "valid": not errors,
        "errors": [_format_schema_error(error) for error in errors],
    }


def check_completeness(bill: dict[str, Any]) -> dict[str, Any]:
    """Run logical completeness checks that go beyond JSON Schema.

    Args:
        bill: Parsed and enriched bill record to inspect.

    Returns:
        A completeness report with warnings for missing or suspicious content.
    """
    warnings: list[str] = []

    sponsors = bill.get("sponsors")
    if isinstance(sponsors, dict):
        house_sponsors = _as_string_list(sponsors.get("house_sponsors"))
        senate_sponsors = _as_string_list(sponsors.get("senate_sponsors"))
    else:
        house_sponsors = []
        senate_sponsors = []

    if not house_sponsors and not senate_sponsors:
        warnings.append("Bill has no house or senate sponsors.")

    sections = bill.get("sections")
    if isinstance(sections, list):
        top_level_refs = set(_as_string_list(bill.get("crs_references")))
        missing_refs: set[str] = set()

        for index, section in enumerate(sections, start=1):
            if not isinstance(section, dict):
                warnings.append(f"Section at index {index} is not an object.")
                continue

            section_number = section.get("section_number", index)
            section_text = section.get("text")
            if not isinstance(section_text, str) or not section_text.strip():
                warnings.append(f"Section {section_number} has empty text.")

            for ref in _as_string_list(section.get("crs_references")):
                if ref not in top_level_refs:
                    missing_refs.add(ref)

        for ref in sorted(missing_refs):
            warnings.append(
                f"Section-level CRS reference is missing from top-level list: {ref}"
            )
    else:
        warnings.append("Bill sections are missing or not an array.")

    metadata = bill.get("metadata")
    parse_timestamp = (
        metadata.get("parse_timestamp") if isinstance(metadata, dict) else None
    )
    if not _is_iso_datetime(parse_timestamp):
        warnings.append("metadata.parse_timestamp is not a valid ISO 8601 datetime.")

    title = bill.get("title")
    title_text = title.strip() if isinstance(title, str) else ""
    if not title_text or title_text.upper() == "UNTITLED" or len(title_text) < 5:
        warnings.append("Bill title is missing or not descriptive.")

    return {"complete": not warnings, "warnings": warnings}


def check_cross_references(
    bill: dict[str, Any], all_crs_titles: list[str] | None = None
) -> dict[str, Any]:
    """Check CRS references against an optional known-title allowlist.

    Args:
        bill: Parsed and enriched bill record to inspect.
        all_crs_titles: Optional list of valid CRS title identifiers, such as
            ``["1", "2", "6", "24"]``.

    Returns:
        Cross-reference report. If no title list is provided, the check is
        marked as skipped.
    """
    if all_crs_titles is None:
        return {"checked": False, "unknown_references": []}

    known_titles = {str(title).strip() for title in all_crs_titles if str(title).strip()}
    unknown_references: list[str] = []

    for reference in _as_string_list(bill.get("crs_references")):
        title = _extract_crs_title(reference)
        if title is None or title not in known_titles:
            unknown_references.append(reference)

    return {"checked": True, "unknown_references": unknown_references}


def _generate_report_with_schema(
    bill: dict[str, Any], schema_path: str = DEFAULT_SCHEMA_PATH
) -> dict[str, Any]:
    """Generate a validation report using a caller-selected schema path."""
    schema_result = validate_schema(bill, schema_path=schema_path)
    completeness_result = check_completeness(bill)
    cross_ref_result = check_cross_references(bill)

    if not schema_result["valid"]:
        overall_status = "fail"
    elif completeness_result["warnings"] or cross_ref_result["unknown_references"]:
        overall_status = "warn"
    else:
        overall_status = "pass"

    return {
        "bill_number": str(bill.get("bill_number", "UNKNOWN")),
        "schema_valid": schema_result["valid"],
        "schema_errors": schema_result["errors"],
        "completeness": completeness_result["complete"],
        "completeness_warnings": completeness_result["warnings"],
        "cross_ref_issues": cross_ref_result["unknown_references"],
        "overall_status": overall_status,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_report(bill: dict[str, Any]) -> dict[str, Any]:
    """Run all validation checks and return a unified report.

    Args:
        bill: Parsed and enriched bill record to validate.

    Returns:
        A report containing schema, completeness, cross-reference, and overall
        status fields.
    """
    return _generate_report_with_schema(bill, schema_path=DEFAULT_SCHEMA_PATH)


def _summarize_reports(reports: list[dict[str, Any]]) -> dict[str, int]:
    """Count pass, warn, and fail statuses in a report list."""
    summary = {"pass": 0, "warn": 0, "fail": 0}
    for report in reports:
        status = report.get("overall_status")
        if status in summary:
            summary[status] += 1
        else:
            summary["fail"] += 1
    return summary


def _validate_all_with_schema(
    input_dir: str = DEFAULT_INPUT_DIR, schema_path: str = DEFAULT_SCHEMA_PATH
) -> dict[str, int]:
    """Validate all parsed bill files using a selected schema path."""
    directory = Path(input_dir)
    bill_paths = sorted(directory.glob("*_parsed.json"))
    reports: list[dict[str, Any]] = []

    for bill_path in tqdm(bill_paths, desc="Validating bills", unit="bill"):
        try:
            bill = _load_json(bill_path)
            if not isinstance(bill, dict):
                raise ValueError("Top-level JSON value is not an object.")
            report = _generate_report_with_schema(bill, schema_path=schema_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            LOGGER.error("Failed to validate %s: %s", bill_path, exc)
            report = {
                "bill_number": bill_path.stem.replace("_parsed", ""),
                "schema_valid": False,
                "schema_errors": [str(exc)],
                "completeness": False,
                "completeness_warnings": [],
                "cross_ref_issues": [],
                "overall_status": "fail",
                "validated_at": datetime.now(timezone.utc).isoformat(),
            }
        reports.append(report)

    summary = _summarize_reports(reports)
    report_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(directory),
        "schema_path": schema_path,
        "summary": summary,
        "results": reports,
    }
    _write_json(directory / "validation_report.json", report_payload)
    return summary


def validate_all(input_dir: str = DEFAULT_INPUT_DIR) -> dict[str, int]:
    """Validate every parsed bill in a directory and write a batch report.

    Args:
        input_dir: Directory containing ``*_parsed.json`` bill records.

    Returns:
        Summary counts keyed by ``pass``, ``warn``, and ``fail``.
    """
    return _validate_all_with_schema(
        input_dir=input_dir, schema_path=DEFAULT_SCHEMA_PATH
    )


def _print_summary(summary: dict[str, int]) -> None:
    """Print a compact validation summary table to stdout."""
    print("Validation Summary")
    print("------------------")
    print(f"{'Status':<8}Count")
    for status in ("pass", "warn", "fail"):
        print(f"{status:<8}{summary.get(status, 0)}")


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Validate parsed and enriched Colorado bill records."
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help=f"Directory of *_parsed.json files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--single",
        help="Validate one parsed bill JSON file instead of a full directory.",
    )
    parser.add_argument(
        "--schema-path",
        default=DEFAULT_SCHEMA_PATH,
        help=f"Path to bill JSON Schema. Default: {DEFAULT_SCHEMA_PATH}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the validator CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = _build_parser().parse_args(argv)

    if args.single:
        try:
            bill = _load_json(Path(args.single))
            if not isinstance(bill, dict):
                raise ValueError("Top-level JSON value is not an object.")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"Failed to read bill record: {exc}", file=sys.stderr)
            return 1

        report = _generate_report_with_schema(bill, schema_path=args.schema_path)
        summary = _summarize_reports([report])
        print(json.dumps(report, indent=2, ensure_ascii=False))
        _print_summary(summary)
        return 0 if report["overall_status"] != "fail" else 1

    summary = _validate_all_with_schema(
        input_dir=args.input_dir, schema_path=args.schema_path
    )
    _print_summary(summary)
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
