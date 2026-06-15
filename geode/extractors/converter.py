"""Markdown conversion routing for source legal documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from geode.extractors.fingerprint import (
    PreservationReport,
    SourceFingerprint,
    compute_preservation_score,
    fingerprint_source,
)


class ConversionResult(BaseModel):
    """Result from a source-to-Markdown conversion attempt."""

    model_config = ConfigDict(extra="forbid")

    markdown_text: str
    conversion_path: str
    tool_used: str
    preservation_score: PreservationReport
    fingerprint: SourceFingerprint
    warnings: list[str] = Field(default_factory=list)


def select_conversion_path(rule_entry: dict[str, Any]) -> str:
    """Select a conversion path using the B14 routing policy."""

    if rule_entry.get("docx_path") or rule_entry.get("docx_url"):
        return "path_1_docx"
    if rule_entry.get("is_scanned"):
        return "path_3_ocr"
    if rule_entry.get("pdf_path") or rule_entry.get("pdf_url"):
        if rule_entry.get("complex_layout"):
            return "path_2_pdf_marker_llm"
        return "path_2_pdf_markitdown"
    return "unsupported"


def _convert_with_markitdown(path: Path) -> str | None:
    """Try MarkItDown conversion if the optional dependency is installed."""

    try:
        from markitdown import MarkItDown
    except ImportError:
        return None
    result = MarkItDown().convert(str(path))
    return str(result.text_content)


def _convert_docx_with_python_docx(path: Path) -> str | None:
    """Try DOCX conversion with python-docx if installed."""

    try:
        from docx import Document
    except ImportError:
        return None
    document = Document(str(path))
    return "\n\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text)


def _source_text_for_preservation(path: Path) -> str:
    """Best-effort source text for preservation scoring."""

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def convert_docx_to_markdown(
    docx_path: Path,
    source_url: str = "https://www.sos.state.co.us/CCR/Welcome.do",
) -> ConversionResult:
    """Convert a DOCX source document to Markdown."""

    warnings: list[str] = []
    markdown = _convert_with_markitdown(docx_path)
    tool_used = "markitdown"
    if markdown is None:
        markdown = _convert_docx_with_python_docx(docx_path)
        tool_used = "python-docx"
    if markdown is None:
        markdown = ""
        tool_used = "unavailable"
        warnings.append("DOCX conversion dependencies are not installed.")
    source_text = _source_text_for_preservation(docx_path)
    return ConversionResult(
        markdown_text=markdown,
        conversion_path="path_1_docx",
        tool_used=tool_used,
        preservation_score=compute_preservation_score(source_text, markdown),
        fingerprint=fingerprint_source(docx_path, source_url),
        warnings=warnings,
    )


def detect_if_scanned(pdf_path: Path) -> bool:
    """Best-effort scanned-PDF detector using text extraction when available."""

    content = pdf_path.read_bytes()
    try:
        import fitz
    except ImportError:
        return b"/Image" in content and b"BT" not in content
    try:
        document = fitz.open(str(pdf_path))
    except Exception:
        return b"/Image" in content and b"BT" not in content
    try:
        text = "\n".join(page.get_text().strip() for page in document)
    finally:
        document.close()
    return not bool(text.strip())


def convert_pdf_to_markdown(
    pdf_path: Path,
    use_llm: bool = False,
    source_url: str = "https://www.sos.state.co.us/CCR/Welcome.do",
) -> ConversionResult:
    """Convert a PDF source document to Markdown."""

    warnings: list[str] = []
    markdown = _convert_with_markitdown(pdf_path)
    tool_used = "markitdown"
    if markdown is None:
        try:
            import fitz
        except ImportError:
            markdown = ""
            tool_used = "unavailable"
            warnings.append("PDF conversion dependencies are not installed.")
        else:
            try:
                document = fitz.open(str(pdf_path))
            except Exception:
                markdown = ""
                tool_used = "unavailable"
                warnings.append("PDF conversion failed for the supplied file.")
            else:
                try:
                    markdown = "\n\n".join(page.get_text().strip() for page in document)
                finally:
                    document.close()
                tool_used = "pymupdf"
    source_text = _source_text_for_preservation(pdf_path)
    return ConversionResult(
        markdown_text=markdown,
        conversion_path="path_2_pdf_marker_llm" if use_llm else "path_2_pdf_markitdown",
        tool_used=tool_used,
        preservation_score=compute_preservation_score(source_text, markdown),
        fingerprint=fingerprint_source(pdf_path, source_url),
        warnings=warnings,
    )
