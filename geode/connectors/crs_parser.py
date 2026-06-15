"""Fixture-first parser for Colorado Revised Statutes title text."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from geode.constants import CRS_LAYER
from geode.extractors.citation_extractor import extract_crs_citations
from geode.extractors.regex_patterns import (
    ARTICLE_HEADING_RE,
    PART_HEADING_RE,
    SECTION_HEADING_RE,
    TITLE_HEADING_RE,
)
from geode.extractors.structure_parser import split_frontmatter
from geode.schemas import CRSTitleDocument, SourceDocument, StatuteSection
from geode.schemas.validators import canonical_crs_id, normalize_crs_number
from geode.utils.hashing import sha256_file


class CRSParseError(ValueError):
    """Raised when a CRS fixture cannot be parsed without inventing data."""


ATTR_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*)=[\"']([^\"']*)[\"']")
TITLE_TAG_RE = re.compile(r"<TITLE\b(?P<attrs>[^>]*)>(?P<body>.*?)</TITLE>", re.DOTALL)
ARTICLE_TAG_RE = re.compile(r"<ARTICLE\b(?P<attrs>[^>]*)>(?P<body>.*?)</ARTICLE>", re.DOTALL)
PART_TAG_RE = re.compile(r"<PART\b(?P<attrs>[^>]*)>(?P<body>.*?)</PART>", re.DOTALL)
SGML_SECTION_RE = re.compile(r"<SECTION\b(?P<attrs>[^>]*)>(?P<body>.*?)</SECTION>", re.DOTALL)
TAG_STRIP_RE = re.compile(r"<[^>]+>")


def parse_crs_sgml(
    input_path: Path,
    title_number: str,
    publication_year: int,
) -> CRSTitleDocument:
    """Parse bulk CRS SGML-like input into a validated title document."""

    raw_text = input_path.read_text(encoding="utf-8")
    title_match = TITLE_TAG_RE.search(raw_text)
    if not title_match:
        raise CRSParseError("missing TITLE tag")
    title_attrs = _attrs(title_match.group("attrs"))
    normalized_title = normalize_crs_number(title_number)
    metadata_title = normalize_crs_number(title_attrs.get("number", ""))
    if metadata_title != normalized_title:
        raise CRSParseError("TITLE number does not match requested title")
    title_name = _required_attr(title_attrs, "name")
    source_url = title_attrs.get(
        "source_url",
        "https://content.leg.colorado.gov/agencies/office-legislative-legal-services/"
        "colorado-revised-statutes",
    )
    retrieved_at = datetime.now(timezone.utc)
    sections: list[StatuteSection] = []

    for article_match in ARTICLE_TAG_RE.finditer(title_match.group("body")):
        article_attrs = _attrs(article_match.group("attrs"))
        article_number = normalize_crs_number(_required_attr(article_attrs, "number"))
        article_name = _required_attr(article_attrs, "name")
        article_body = article_match.group("body")
        direct_article_body = PART_TAG_RE.sub("", article_body)
        section_contexts = _sgml_sections(direct_article_body, None, None)
        for part_match in PART_TAG_RE.finditer(article_body):
            part_attrs = _attrs(part_match.group("attrs"))
            part_number = normalize_crs_number(_required_attr(part_attrs, "number"))
            part_name = _required_attr(part_attrs, "name")
            section_contexts.extend(
                _sgml_sections(part_match.group("body"), part_number, part_name)
            )
        for section_attrs, section_text, part_number, part_name in section_contexts:
            section_number = normalize_crs_number(_required_attr(section_attrs, "number"))
            heading = _required_attr(section_attrs, "heading")
            text = _clean_sgml_text(section_text)
            if not text:
                raise CRSParseError(f"section {section_number} has no text")
            entity_id = canonical_crs_id(normalized_title, article_number, section_number)
            citations = [citation.canonical_form for citation in extract_crs_citations(text)]
            if entity_id not in citations:
                citations.append(entity_id)
                citations.sort()
            sections.append(
                StatuteSection(
                    id=entity_id,
                    title_num=normalized_title,
                    title_name=title_name,
                    article_num=article_number,
                    article_name=article_name,
                    part_num=part_number,
                    part_name=part_name,
                    section_num=f"{normalized_title}-{article_number}-{section_number}",
                    section_heading=heading,
                    full_text=text,
                    subject_tags=[],
                    industry_tags=[],
                    cross_references_outbound=citations,
                    source_url=source_url,
                    data_retrieved=retrieved_at.date(),
                    data_version=f"{publication_year}_sgml",
                    confidence={"overall": 1.0},
                    source_path=input_path.as_posix(),
                    publication_year=publication_year,
                )
            )
    if not sections:
        raise CRSParseError("no SGML sections found")
    source = SourceDocument(
        source_id=f"crs_{publication_year}_title_{normalized_title}_sgml",
        layer=CRS_LAYER,
        source_owner="Office of Legislative Legal Services",
        source_url=source_url,
        source_format="sgml",
        retrieved_at=retrieved_at,
        raw_path=input_path.as_posix(),
        sha256=sha256_file(input_path),
        immutable=True,
        confidence=1.0,
        notes="Bulk SGML CRS source metadata.",
    )
    return CRSTitleDocument(
        entity_id=f"CRS-TITLE-{normalized_title}",
        title_number=normalized_title,
        title_name=title_name,
        publication_year=publication_year,
        generated_at=retrieved_at,
        source_document=source,
        sections=sections,
    )


def write_crs_sgml_title(
    root: Path,
    input_path: Path,
    title_number: str,
    publication_year: int,
) -> list[Path]:
    """Parse CRS SGML and write Markdown, metadata, index, manifest, and log."""

    from geode.pipeline.writer import write_crs_title

    return write_crs_title(root, parse_crs_sgml(input_path, title_number, publication_year))


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO datetime and preserve timezone information."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CRSParseError("retrieved_at must include timezone information")
    return parsed


def _required(metadata: dict[str, str], key: str) -> str:
    """Return a required frontmatter value or raise a parse error."""

    value = metadata.get(key)
    if value is None or not value.strip():
        raise CRSParseError(f"missing required frontmatter value: {key}")
    return value


def _attrs(raw_attrs: str) -> dict[str, str]:
    """Parse SGML/XML-ish attributes."""

    return {match.group(1): match.group(2) for match in ATTR_RE.finditer(raw_attrs)}


def _required_attr(attrs: dict[str, str], key: str) -> str:
    """Return a required SGML attribute."""

    value = attrs.get(key)
    if value is None or not value.strip():
        raise CRSParseError(f"missing required SGML attribute: {key}")
    return value


def _sgml_sections(
    body: str,
    part_number: str | None,
    part_name: str | None,
) -> list[tuple[dict[str, str], str, str | None, str | None]]:
    """Extract SECTION tags from one SGML body."""

    return [
        (_attrs(match.group("attrs")), match.group("body"), part_number, part_name)
        for match in SGML_SECTION_RE.finditer(body)
    ]


def _clean_sgml_text(text: str) -> str:
    """Strip tags and normalize SGML section text."""

    stripped = TAG_STRIP_RE.sub("", text)
    lines = [line.strip() for line in stripped.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def parse_crs_fixture(
    input_path: Path,
    title_number: str,
    publication_year: int,
) -> CRSTitleDocument:
    """Parse a CRS fixture into validated title and section records."""

    raw_text = input_path.read_text(encoding="utf-8")
    metadata, body = split_frontmatter(raw_text)
    normalized_title = normalize_crs_number(title_number)
    metadata_title = normalize_crs_number(_required(metadata, "title_number"))
    if metadata_title != normalized_title:
        raise CRSParseError("frontmatter title_number does not match requested title")
    metadata_year = int(_required(metadata, "publication_year"))
    if metadata_year != publication_year:
        raise CRSParseError("frontmatter publication_year does not match requested year")

    source_url = _required(metadata, "source_url")
    title_name = _required(metadata, "title_name")
    retrieved_at = _parse_datetime(_required(metadata, "retrieved_at"))
    source_format = metadata.get("source_format", "fixture")
    source_id = metadata.get("source_id", f"crs_{publication_year}_title_{normalized_title}")

    title_match = None
    sections: list[StatuteSection] = []
    current_article: tuple[str, str] | None = None
    current_part: tuple[str, str] | None = None
    pending_heading: tuple[str, str, str, str] | None = None
    pending_lines: list[str] = []

    def flush_section() -> None:
        """Validate and store the pending section."""

        nonlocal pending_heading, pending_lines
        if pending_heading is None:
            return
        if current_article is None:
            raise CRSParseError("section encountered before article heading")
        section_title, section_article, section_number, heading = pending_heading
        text = "\n".join(line.rstrip() for line in pending_lines).strip()
        if not text:
            raise CRSParseError(f"section {section_number} has no text")
        citations = [citation.canonical_form for citation in extract_crs_citations(text)]
        self_citation = canonical_crs_id(section_title, section_article, section_number)
        if self_citation not in citations:
            citations.append(self_citation)
            citations.sort()
        part_number = current_part[0] if current_part else None
        part_name = current_part[1] if current_part else None
        sections.append(
            StatuteSection(
                id=self_citation,
                title_num=section_title,
                title_name=title_name,
                article_num=section_article,
                article_name=current_article[1],
                part_num=part_number,
                part_name=part_name,
                section_num=f"{section_title}-{section_article}-{section_number}",
                section_heading=heading,
                full_text=text,
                subject_tags=[],
                industry_tags=[],
                cross_references_outbound=citations,
                effective_date=None,
                last_amended_session=None,
                last_amended_by=[],
                history_note=None,
                enabling_agencies=[],
                related_regulations=[],
                source_url=source_url,
                data_retrieved=retrieved_at.date(),
                data_version=f"{publication_year}_fixture",
                confidence={"overall": 1.0},
                source_path=input_path.as_posix(),
                publication_year=publication_year,
            )
        )
        pending_heading = None
        pending_lines = []

    for line in body.splitlines():
        title_heading = TITLE_HEADING_RE.match(line)
        if title_heading:
            title_match = title_heading
            continue

        article_heading = ARTICLE_HEADING_RE.match(line)
        if article_heading:
            flush_section()
            current_article = (article_heading.group("number"), article_heading.group("name"))
            current_part = None
            continue

        part_heading = PART_HEADING_RE.match(line)
        if part_heading:
            flush_section()
            current_part = (part_heading.group("number"), part_heading.group("name"))
            continue

        section_heading = SECTION_HEADING_RE.match(line)
        if section_heading:
            flush_section()
            heading_title = normalize_crs_number(section_heading.group("title"))
            if heading_title != normalized_title:
                raise CRSParseError("section title number does not match requested title")
            pending_heading = (
                heading_title,
                normalize_crs_number(section_heading.group("article")),
                normalize_crs_number(section_heading.group("section")),
                section_heading.group("heading"),
            )
            pending_lines = []
            continue

        if pending_heading is not None:
            pending_lines.append(line)

    flush_section()

    if title_match is None:
        raise CRSParseError("missing title heading")
    if not sections:
        raise CRSParseError("no CRS sections found")

    source = SourceDocument(
        source_id=source_id,
        layer=CRS_LAYER,
        source_owner="Office of Legislative Legal Services",
        source_url=source_url,
        source_format=source_format,
        retrieved_at=retrieved_at,
        raw_path=input_path.as_posix(),
        sha256=sha256_file(input_path),
        immutable=True,
        confidence=1.0,
        notes="Fixture-first CRS source metadata.",
    )
    return CRSTitleDocument(
        entity_id=f"CRS-TITLE-{normalized_title}",
        title_number=normalized_title,
        title_name=title_name,
        publication_year=publication_year,
        generated_at=datetime.now(timezone.utc),
        source_document=source,
        sections=sections,
    )
