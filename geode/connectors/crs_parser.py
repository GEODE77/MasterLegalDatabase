"""Fixture-first parser for Colorado Revised Statutes title text."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

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
TITLE_NUM_RE = re.compile(r"<TITLE_NUM>\s*(?P<body>.*?)\s*</TITLE_NUM>", re.DOTALL)
TITLE_TEXT_RE = re.compile(r"<TITLE_TEXT>\s*(?P<body>.*?)\s*</TITLE_TEXT>", re.DOTALL)
OFFICIAL_BLOCK_RE = re.compile(
    r"<(?P<tag>ARTICLE_NUM|ARTICLE_TEXT|ARTICLE_PART|SECTION_TEXT|SOURCE_NOTE)\b[^>]*>"
    r"(?P<body>.*?)</(?P=tag)>",
    re.DOTALL,
)
OFFICIAL_CATCH_LINE_RE = re.compile(
    r"<CATCH_LINE>\s*(?P<body>.*?)\s*</CATCH_LINE>",
    re.DOTALL,
)
OFFICIAL_CATCH_NUMBER_RE = re.compile(
    r"<RHFTO>\s*(?P<number>.*?)\s*</RHFTO>\s*\.\s*(?P<heading>.*)",
    re.DOTALL,
)
CRS_NUMBER_RE = re.compile(
    r"^(?P<title>\d{1,2}(?:\.\d+)?)-(?P<article>\d+(?:\.\d+)?)-"
    r"(?P<section>\d+(?:\.\d+)?)$"
)
SOURCE_URL = "https://leg.colorado.gov/colorado-revised-statutes"
EDITOR_EFFECTIVE_RE = re.compile(
    r"\[Editor's note:\s*This version of this (?:section|part) is effective "
    r"(?P<until>until\s+)?(?P<date>[A-Za-z]+ \d{1,2}, \d{4})\.",
    re.IGNORECASE,
)


class CRSSourceMetadata(BaseModel):
    """Detected metadata for one archived CRS source file."""

    model_config = ConfigDict(extra="forbid")

    title_number: str | None = Field(default=None)
    title_name: str | None = None
    publication_year: int | None = Field(default=None)
    source_format: str


def detect_crs_source_metadata(input_path: Path) -> CRSSourceMetadata:
    """Detect title number, title name, year, and source format from a CRS source file."""

    raw_text = _read_crs_text(input_path)
    official_title = _official_title_number(raw_text)
    if official_title:
        return CRSSourceMetadata(
            title_number=official_title,
            title_name=_official_title_name(raw_text),
            publication_year=_year_from_text(input_path.name),
            source_format="official_sgml",
        )

    title_match = TITLE_TAG_RE.search(raw_text)
    if title_match:
        attrs = _attrs(title_match.group("attrs"))
        title_number = attrs.get("number")
        return CRSSourceMetadata(
            title_number=normalize_crs_number(title_number) if title_number else None,
            title_name=attrs.get("name"),
            publication_year=_year_from_text(input_path.name),
            source_format="sgml",
        )

    metadata, _body = split_frontmatter(raw_text)
    title_number = metadata.get("title_number")
    publication_year = metadata.get("publication_year")
    return CRSSourceMetadata(
        title_number=normalize_crs_number(title_number) if title_number else None,
        title_name=metadata.get("title_name"),
        publication_year=int(publication_year) if publication_year else _year_from_text(input_path.name),
        source_format=metadata.get("source_format", "fixture"),
    )


def parse_crs_source(
    input_path: Path,
    title_number: str | None = None,
    publication_year: int | None = None,
) -> CRSTitleDocument:
    """Parse a CRS source file by detecting the fixture or SGML parser path."""

    metadata = detect_crs_source_metadata(input_path)
    title = title_number or metadata.title_number
    year = publication_year or metadata.publication_year
    if not title:
        raise CRSParseError("could not determine CRS title number")
    if year is None:
        raise CRSParseError("could not determine CRS publication year")
    if metadata.source_format in {"sgml", "official_sgml"}:
        return parse_crs_sgml(input_path, title, year)
    return parse_crs_fixture(input_path, title, year)


def parse_crs_sgml(
    input_path: Path,
    title_number: str,
    publication_year: int,
) -> CRSTitleDocument:
    """Parse bulk CRS SGML-like input into a validated title document."""

    raw_text = _read_crs_text(input_path)
    if _official_title_number(raw_text):
        return _parse_official_crs_sgml(input_path, title_number, publication_year, raw_text)
    return _parse_tagged_crs_sgml(input_path, title_number, publication_year, raw_text)


def _parse_tagged_crs_sgml(
    input_path: Path,
    title_number: str,
    publication_year: int,
    raw_text: str,
) -> CRSTitleDocument:
    """Parse the simplified tagged SGML fixture shape."""

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


def _parse_official_crs_sgml(
    input_path: Path,
    title_number: str,
    publication_year: int,
    raw_text: str,
) -> CRSTitleDocument:
    """Parse the official OLLS CRS SGML title format."""

    normalized_title = normalize_crs_number(title_number)
    metadata_title = _official_title_number(raw_text)
    if metadata_title != normalized_title:
        raise CRSParseError("TITLE_NUM does not match requested title")
    title_name = _official_title_name(raw_text)
    if not title_name:
        raise CRSParseError("missing TITLE_TEXT")

    retrieved_at = datetime.now(timezone.utc)
    sections: list[StatuteSection] = []
    current_article: tuple[str, str] | None = None
    pending_article_number: str | None = None
    current_part: tuple[str, str | None] | None = None
    pending_part_number: str | None = None

    for block in OFFICIAL_BLOCK_RE.finditer(raw_text):
        tag = block.group("tag")
        body = block.group("body")
        if tag == "ARTICLE_NUM":
            pending_article_number = _official_article_number(body)
            current_article = None
            current_part = None
            pending_part_number = None
            continue
        if tag == "ARTICLE_TEXT":
            if not pending_article_number:
                raise CRSParseError("ARTICLE_TEXT encountered before ARTICLE_NUM")
            article_name = _clean_official_text(body, collapse=True)
            if not article_name:
                raise CRSParseError(f"article {pending_article_number} has no name")
            current_article = (pending_article_number, article_name)
            continue
        if tag == "ARTICLE_PART":
            part_text = _clean_official_text(body, collapse=True)
            part_number = _official_part_number(part_text)
            if part_number:
                pending_part_number = part_number
                current_part = (part_number, None)
            elif pending_part_number:
                current_part = (pending_part_number, part_text or None)
                pending_part_number = None
            continue
        if tag == "SOURCE_NOTE":
            if sections:
                source_note = _clean_official_text(body, collapse=False)
                if source_note:
                    sections[-1] = sections[-1].model_copy(
                        update={"history_note": source_note}
                    )
            continue
        if tag != "SECTION_TEXT":
            continue
        if current_article is None:
            raise CRSParseError("SECTION_TEXT encountered before article heading")
        section = _official_section(
            input_path=input_path,
            title_number=normalized_title,
            title_name=title_name,
            publication_year=publication_year,
            retrieved_at=retrieved_at,
            article=current_article,
            part=current_part,
            raw_section=body,
        )
        if section is not None:
            sections.append(section)

    sections = _dedupe_official_sections(sections)
    if not sections:
        raise CRSParseError("no official SGML sections found")
    source = SourceDocument(
        source_id=f"crs_{publication_year}_title_{normalized_title}_official_sgml",
        layer=CRS_LAYER,
        source_owner="Office of Legislative Legal Services",
        source_url=SOURCE_URL,
        source_format="official_sgml",
        retrieved_at=retrieved_at,
        raw_path=input_path.as_posix(),
        sha256=sha256_file(input_path),
        immutable=True,
        confidence=1.0,
        notes="Official OLLS CRS SGML title source.",
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


def _official_section(
    *,
    input_path: Path,
    title_number: str,
    title_name: str,
    publication_year: int,
    retrieved_at: datetime,
    article: tuple[str, str],
    part: tuple[str, str | None] | None,
    raw_section: str,
) -> StatuteSection | None:
    """Parse one official SECTION_TEXT block into a statute section."""

    catch_match = OFFICIAL_CATCH_LINE_RE.search(raw_section)
    if not catch_match:
        raise CRSParseError("SECTION_TEXT missing CATCH_LINE")
    number, heading = _official_catch_line(catch_match.group("body"))
    if _is_unkeyed_repealed_range(number, heading):
        return None
    parsed_number = CRS_NUMBER_RE.match(number)
    if not parsed_number:
        if _is_unkeyed_range(number):
            return None
        raise CRSParseError(f"invalid CRS section number: {number}")
    section_title = normalize_crs_number(parsed_number.group("title"))
    article_number = normalize_crs_number(parsed_number.group("article"))
    section_number = normalize_crs_number(parsed_number.group("section"))
    if section_title != title_number:
        raise CRSParseError("section title number does not match requested title")
    if article_number != article[0]:
        raise CRSParseError("section article number does not match current article")

    body_without_catch = OFFICIAL_CATCH_LINE_RE.sub("", raw_section, count=1)
    text = _clean_official_text(body_without_catch, collapse=False)
    if not text:
        text = heading
    effective_date = _official_effective_date(text)
    entity_id = canonical_crs_id(section_title, article_number, section_number)
    citations = [citation.canonical_form for citation in extract_crs_citations(text)]
    if entity_id not in citations:
        citations.append(entity_id)
        citations.sort()
    return StatuteSection(
        id=entity_id,
        title_num=section_title,
        title_name=title_name,
        article_num=article_number,
        article_name=article[1],
        part_num=part[0] if part else None,
        part_name=part[1] if part else None,
        section_num=f"{section_title}-{article_number}-{section_number}",
        section_heading=heading,
        full_text=text,
        subject_tags=[],
        industry_tags=[],
        cross_references_outbound=citations,
        effective_date=effective_date,
        last_amended_session=None,
        last_amended_by=[],
        history_note=None,
        enabling_agencies=[],
        related_regulations=[],
        source_url=SOURCE_URL,
        data_retrieved=retrieved_at.date(),
        data_version=f"{publication_year}_official_sgml",
        confidence={"overall": 1.0},
        source_path=input_path.as_posix(),
        publication_year=publication_year,
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


def _official_title_number(raw_text: str) -> str | None:
    """Return the title number from official OLLS SGML text when present."""

    match = TITLE_NUM_RE.search(raw_text)
    if not match:
        return None
    cleaned = _clean_official_text(match.group("body"), collapse=True)
    number_match = re.search(r"\bTITLE\s+(\d{1,2}(?:\.\d+)?)\b", cleaned, re.IGNORECASE)
    return normalize_crs_number(number_match.group(1)) if number_match else None


def _official_title_name(raw_text: str) -> str | None:
    """Return the title name from official OLLS SGML text when present."""

    match = TITLE_TEXT_RE.search(raw_text)
    if not match:
        return None
    cleaned = _clean_official_text(match.group("body"), collapse=True)
    return cleaned or None


def _official_article_number(raw_text: str) -> str:
    """Return the article number from an official ARTICLE_NUM block."""

    cleaned = _clean_official_text(raw_text, collapse=True)
    match = re.search(r"\bARTICLE\s+(\d+(?:\.\d+)?)\b", cleaned, re.IGNORECASE)
    if not match:
        raise CRSParseError(f"invalid ARTICLE_NUM block: {cleaned}")
    return normalize_crs_number(match.group(1))


def _official_part_number(value: str) -> str | None:
    """Return a part number from official ARTICLE_PART text."""

    match = re.match(r"PART\s+(\d+(?:\.\d+)?)\b", value, re.IGNORECASE)
    return normalize_crs_number(match.group(1)) if match else None


def _official_catch_line(raw_text: str) -> tuple[str, str]:
    """Return section number and heading from an official CATCH_LINE body."""

    match = OFFICIAL_CATCH_NUMBER_RE.search(raw_text)
    if not match:
        cleaned = _clean_official_text(raw_text, collapse=True)
        range_match = re.match(
            r"(?P<number>\d{1,2}(?:\.\d+)?-\d+(?:\.\d+)?-\d+(?:\.\d+)?"
            r"(?:\s+(?:to|and)\s+\d{1,2}(?:\.\d+)?-\d+(?:\.\d+)?-\d+(?:\.\d+)?))"
            r"\.?\s*(?P<heading>.*)",
            cleaned,
            re.IGNORECASE,
        )
        if range_match:
            return range_match.group("number"), range_match.group("heading").strip()
        raise CRSParseError(f"invalid CATCH_LINE block: {cleaned}")
    number = _clean_official_text(match.group("number"), collapse=True)
    heading = _clean_official_text(match.group("heading"), collapse=True)
    heading = heading.lstrip(". ").strip()
    if not number or (not heading and not _is_unkeyed_range(number)):
        raise CRSParseError("CATCH_LINE missing section number or heading")
    return number, heading


def _clean_official_text(raw_text: str, *, collapse: bool) -> str:
    """Clean official SGML tags without adding text that is not present."""

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<NL\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<P\b[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(?:T|M|N|I|B|RHFTO|RHRTC|CTR|S1|S2|S3)\b[^>]*>", "", text)
    text = TAG_STRIP_RE.sub("", text)
    text = unescape(text)
    if collapse:
        return re.sub(r"\s+", " ", text).strip()
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _read_crs_text(input_path: Path) -> str:
    """Read official CRS text with a conservative encoding fallback."""

    try:
        return input_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return input_path.read_text(encoding="cp1252")


def _is_unkeyed_repealed_range(number: str, heading: str) -> bool:
    """Return whether a catch line is a repealed range without a single section ID."""

    return _is_unkeyed_range(number) and "repealed" in heading.casefold()


def _is_unkeyed_range(number: str) -> bool:
    """Return whether a catch line names a range instead of one section."""

    lowered = number.casefold()
    return " to " in lowered or " and " in lowered


def _official_effective_date(text: str) -> date | None:
    """Return an editor-note effective date when the text states one."""

    match = EDITOR_EFFECTIVE_RE.search(text)
    if not match or match.group("until"):
        return None
    try:
        return datetime.strptime(match.group("date"), "%B %d, %Y").date()
    except ValueError:
        return None


def _dedupe_official_sections(sections: list[StatuteSection]) -> list[StatuteSection]:
    """Keep one current/latest official section record per canonical CRS ID."""

    selected: dict[str, tuple[tuple[int, int, int], StatuteSection]] = {}
    for index, section in enumerate(sections):
        rank = _official_section_rank(section, index)
        existing = selected.get(section.entity_id)
        if existing is None or rank > existing[0]:
            selected[section.entity_id] = (rank, section)
    return [payload[1] for payload in selected.values()]


def _official_section_rank(section: StatuteSection, index: int) -> tuple[int, int, int]:
    """Rank duplicate official versions by effective-note status and source order."""

    text = section.full_text
    match = EDITOR_EFFECTIVE_RE.search(text)
    if match:
        if match.group("until"):
            return (0, 0, index)
        try:
            effective = datetime.strptime(match.group("date"), "%B %d, %Y").date()
        except ValueError:
            return (1, 0, index)
        return (2, effective.toordinal(), index)
    return (1, 0, index)


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


def _year_from_text(value: str) -> int | None:
    """Return a four-digit publication year from filename-like text."""

    match = re.search(r"\b(20\d{2}|19\d{2}|18\d{2})\b", value)
    return int(match.group(1)) if match else None


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
