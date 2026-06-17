"""Tests for source document format detection and conversion dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from geode.extractors import converter


def test_detect_document_format(tmp_path: Path) -> None:
    """Document format detection uses byte signatures instead of suffixes."""

    fixtures = {
        "pdf": b"%PDF-1.7\nbody",
        "docx": b"PK\x03\x04docx body",
        "doc": b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1doc body",
        "unknown": b"not a known document",
    }

    for expected, content in fixtures.items():
        path = tmp_path / f"{expected}.bin"
        path.write_bytes(content)

        assert converter.detect_document_format(path) == expected


def test_convert_to_markdown_dispatches_by_signature(monkeypatch, tmp_path: Path) -> None:
    """The dispatcher routes to the converter matching the file signature."""

    calls: list[tuple[str, Path, str | None]] = []

    def fake_pdf(path: Path, *, source_url: str | None = None) -> str:
        calls.append(("pdf", path, source_url))
        return "pdf-result"

    def fake_docx(path: Path, source_url: str | None = None) -> str:
        calls.append(("docx", path, source_url))
        return "docx-result"

    def fake_doc(path: Path, *, source_url: str | None = None) -> str:
        calls.append(("doc", path, source_url))
        return "doc-result"

    monkeypatch.setattr(converter, "convert_pdf_to_markdown", fake_pdf)
    monkeypatch.setattr(converter, "convert_docx_to_markdown", fake_docx)
    monkeypatch.setattr(converter, "convert_doc_to_markdown", fake_doc)

    sources = [
        ("pdf", b"%PDF-1.7\nbody", "pdf-result"),
        ("docx", b"PK\x03\x04docx body", "docx-result"),
        ("doc", b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1doc body", "doc-result"),
    ]

    for name, content, expected in sources:
        path = tmp_path / f"{name}.source"
        path.write_bytes(content)

        result = converter.convert_to_markdown(path, source_url="https://example.test")

        assert result == expected

    assert [call[0] for call in calls] == ["pdf", "docx", "doc"]
    assert all(call[2] == "https://example.test" for call in calls)

    unknown = tmp_path / "unknown.source"
    unknown.write_bytes(b"unknown")
    with pytest.raises(ValueError, match="signature did not match pdf/docx/doc"):
        converter.convert_to_markdown(unknown)
