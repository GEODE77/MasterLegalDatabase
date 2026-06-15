"""Fingerprinting and conversion-routing tests."""

from __future__ import annotations

from pathlib import Path

from geode.extractors.converter import detect_if_scanned, select_conversion_path
from geode.extractors.fingerprint import (
    compute_preservation_score,
    fingerprint_source,
    verify_integrity,
)


def test_fingerprint_source_and_verify_integrity(tmp_path: Path) -> None:
    """Fingerprinting records SHA-256 and verifies file integrity."""

    source = tmp_path / "rule.txt"
    source.write_text("legal text", encoding="utf-8")
    fingerprint = fingerprint_source(source, "https://www.sos.state.co.us/CCR/Welcome.do")
    assert fingerprint.size_bytes > 0
    assert verify_integrity(fingerprint.sha256, source)


def test_preservation_score_threshold() -> None:
    """Preservation reports pass only at or above the 0.95 threshold."""

    report = compute_preservation_score("alpha beta", "alpha beta")
    assert report.passed
    low_report = compute_preservation_score("alpha beta gamma", "alpha")
    assert not low_report.passed


def test_select_conversion_path_prefers_docx() -> None:
    """Conversion routing follows DOCX, PDF, OCR priority."""

    assert select_conversion_path({"docx_url": "x", "pdf_url": "y"}) == "path_1_docx"
    assert select_conversion_path({"pdf_url": "y"}) == "path_2_pdf_markitdown"
    assert (
        select_conversion_path({"pdf_url": "y", "complex_layout": True})
        == "path_2_pdf_marker_llm"
    )
    assert select_conversion_path({"pdf_url": "y", "is_scanned": True}) == "path_3_ocr"


def test_detect_if_scanned_without_pdf_dependency(tmp_path: Path) -> None:
    """The fallback scanned detector handles simple PDF-like bytes."""

    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF /Image")
    assert detect_if_scanned(pdf)
