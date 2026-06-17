"""Extract raw bill text from downloaded Colorado legislative PDF files."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Sequence

import fitz
import pdfplumber
from tqdm import tqdm

PAGE_BREAK = "\n\n---PAGE BREAK---\n\n"
MIN_TEXT_CHARS = 100
MAX_NON_ASCII_RATIO = 0.30
QUALITY_VALUES = ("good", "uncertain", "garbled", "empty")

LOGGER = logging.getLogger(__name__)


class ExtractionError(RuntimeError):
    """Raised when a PDF cannot be extracted by the available engines."""


def extract_text_pdfplumber(pdf_path: str) -> dict:
    """Extract PDF text page by page with pdfplumber.

    Args:
        pdf_path: Path to the source PDF.

    Returns:
        Extraction dictionary containing page text and full concatenated text.

    Raises:
        ExtractionError: If pdfplumber cannot open or process the PDF.
    """

    path = Path(pdf_path)
    try:
        with pdfplumber.open(path) as pdf:
            pages = []
            for index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append(
                    {
                        "page_number": index,
                        "text": text,
                        "char_count": len(text),
                    }
                )
    except Exception as exc:
        raise ExtractionError(f"pdfplumber failed for {path}: {exc}") from exc

    return _build_extraction(path, "pdfplumber", pages)


def extract_text_pymupdf(pdf_path: str) -> dict:
    """Extract PDF text page by page with PyMuPDF.

    Args:
        pdf_path: Path to the source PDF.

    Returns:
        Extraction dictionary containing page text and full concatenated text.

    Raises:
        ExtractionError: If PyMuPDF cannot open or process the PDF.
    """

    path = Path(pdf_path)
    pages = []
    try:
        with fitz.open(path) as document:
            for index, page in enumerate(document, start=1):
                text = page.get_text("text") or ""
                pages.append(
                    {
                        "page_number": index,
                        "text": text,
                        "char_count": len(text),
                    }
                )
    except Exception as exc:
        raise ExtractionError(f"pymupdf failed for {path}: {exc}") from exc

    return _build_extraction(path, "pymupdf", pages)


def assess_quality(extraction: dict) -> dict:
    """Assess whether extracted text appears usable for bill parsing.

    Args:
        extraction: Extraction dictionary from pdfplumber or PyMuPDF.

    Returns:
        Quality report with ``quality`` and ``issues`` keys.
    """

    full_text = str(extraction.get("full_text", ""))
    issues: list[str] = []
    stripped_text = full_text.strip()
    if len(stripped_text) < MIN_TEXT_CHARS:
        issues.append("full_text is empty or below 100 characters")
        return {"quality": "empty", "issues": issues}

    non_ascii_ratio = _non_ascii_ratio(full_text)
    if non_ascii_ratio > MAX_NON_ASCII_RATIO:
        issues.append("full_text contains more than 30% non-ASCII characters")
        return {"quality": "garbled", "issues": issues}

    upper_text = full_text.upper()
    if "BE IT ENACTED" in upper_text or "CONCERNING" in upper_text:
        return {"quality": "good", "issues": issues}

    issues.append("Colorado bill markers not found")
    return {"quality": "uncertain", "issues": issues}


def extract_bill(pdf_path: str, output_dir: str = "data/extracted_text") -> str:
    """Extract one bill PDF and save the extraction JSON.

    Args:
        pdf_path: Path to a downloaded bill PDF.
        output_dir: Directory where extraction JSON should be written.

    Returns:
        Path to the written extraction JSON file.

    Raises:
        ExtractionError: If both extraction engines fail or produce unusable output.
    """

    source_path = Path(pdf_path)
    output_path = Path(output_dir) / f"{source_path.stem}_extracted.json"

    try:
        extraction = extract_text_pdfplumber(str(source_path))
    except ExtractionError as exc:
        LOGGER.error("%s: %s", source_path.name, exc)
        extraction = _fallback_extract(source_path)
    else:
        quality_report = assess_quality(extraction)
        if quality_report["quality"] in {"empty", "garbled"}:
            LOGGER.warning(
                "%s: pdfplumber quality %s; trying PyMuPDF fallback",
                source_path.name,
                quality_report["quality"],
            )
            extraction = _fallback_extract(source_path)

    quality_report = assess_quality(extraction)
    extraction["quality"] = quality_report["quality"]
    extraction["quality_issues"] = quality_report["issues"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, extraction)
    return str(output_path)


def extract_all(
    input_dir: str = "data/raw_pdfs",
    output_dir: str = "data/extracted_text",
) -> dict:
    """Extract text from every PDF in a directory.

    Args:
        input_dir: Directory containing downloaded PDFs.
        output_dir: Directory where extraction JSON files should be written.

    Returns:
        Batch summary including processed, skipped, failed, and quality counts.
    """

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    pdf_paths = sorted(input_path.glob("*.pdf"))
    summary = _empty_summary()

    for pdf_path in tqdm(pdf_paths, desc="Extracting PDFs", unit="pdf"):
        target_path = output_path / f"{pdf_path.stem}_extracted.json"
        if target_path.exists():
            summary["skipped"] += 1
            _increment_quality(summary, _quality_from_existing_json(target_path))
            continue
        try:
            written_path = extract_bill(str(pdf_path), str(output_path))
        except ExtractionError as exc:
            summary["failed"] += 1
            LOGGER.error("%s: extraction failed: %s", pdf_path.name, exc)
            continue
        summary["processed"] += 1
        _increment_quality(summary, _quality_from_existing_json(Path(written_path)))

    return summary


def _fallback_extract(pdf_path: Path) -> dict:
    """Run PyMuPDF extraction for one source PDF.

    Args:
        pdf_path: Source PDF path.

    Returns:
        PyMuPDF extraction dictionary.

    Raises:
        ExtractionError: If PyMuPDF cannot extract the PDF.
    """

    return extract_text_pymupdf(str(pdf_path))


def _build_extraction(path: Path, extractor: str, pages: list[dict[str, Any]]) -> dict:
    """Build the standard extraction dictionary.

    Args:
        path: Source PDF path.
        extractor: Extractor engine name.
        pages: Page dictionaries.

    Returns:
        Standard extraction payload.
    """

    page_texts = [str(page.get("text", "")) for page in pages]
    full_text = PAGE_BREAK.join(page_texts)
    return {
        "source_file": path.name,
        "extractor": extractor,
        "page_count": len(pages),
        "pages": pages,
        "full_text": full_text,
        "total_chars": len(full_text),
    }


def _non_ascii_ratio(text: str) -> float:
    """Calculate the proportion of non-ASCII characters in text.

    Args:
        text: Text to inspect.

    Returns:
        Ratio from 0.0 to 1.0.
    """

    if not text:
        return 0.0
    non_ascii_count = sum(1 for char in text if ord(char) > 127)
    return non_ascii_count / len(text)


def _empty_summary() -> dict:
    """Create an empty batch extraction summary.

    Returns:
        Summary dictionary with all quality buckets initialized.
    """

    return {
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "quality_breakdown": {quality: 0 for quality in QUALITY_VALUES},
    }


def _increment_quality(summary: dict, quality: str) -> None:
    """Increment one quality bucket on a summary dictionary.

    Args:
        summary: Mutable extraction summary.
        quality: Quality label to increment.
    """

    breakdown = summary.get("quality_breakdown")
    if isinstance(breakdown, dict):
        breakdown[quality if quality in QUALITY_VALUES else "uncertain"] += 1


def _quality_from_existing_json(path: Path) -> str:
    """Read quality from an extraction JSON file.

    Args:
        path: Extraction JSON path.

    Returns:
        Stored quality or ``"uncertain"`` when unavailable.
    """

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("%s: could not read quality from existing JSON: %s", path.name, exc)
        return "uncertain"
    quality = str(payload.get("quality", "uncertain"))
    return quality if quality in QUALITY_VALUES else "uncertain"


def _write_json(path: Path, payload: dict) -> None:
    """Write a JSON payload with deterministic formatting.

    Args:
        path: Target JSON path.
        payload: JSON-serializable payload.
    """

    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(content, encoding="utf-8", newline="\n")


def _build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser.

    Returns:
        Configured argument parser.
    """

    parser = argparse.ArgumentParser(description="Extract raw text from bill PDFs.")
    parser.add_argument(
        "--input-dir",
        default="data/raw_pdfs",
        help='Directory containing PDFs, default "data/raw_pdfs".',
    )
    parser.add_argument(
        "--output-dir",
        default="data/extracted_text",
        help='Directory for extraction JSON, default "data/extracted_text".',
    )
    parser.add_argument("--single", help="Optional path to one PDF to extract.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the extraction command-line interface.

    Args:
        argv: Optional argument sequence for embedded callers or tests.

    Returns:
        Process exit code.
    """

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)
    args = _build_parser().parse_args(argv)
    if args.single:
        try:
            output_path = extract_bill(args.single, args.output_dir)
        except ExtractionError as exc:
            LOGGER.error("%s", exc)
            return 1
        quality = _quality_from_existing_json(Path(output_path))
        print(f"Extracted 1 PDF. quality={quality}. output={output_path}")
        return 0

    summary = extract_all(args.input_dir, args.output_dir)
    print(
        "Processed {processed}. Skipped {skipped}. Failed {failed}. "
        "Quality breakdown: {quality_breakdown}".format(**summary)
    )
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
