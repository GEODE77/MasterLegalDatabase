"""Shared structure parsing primitives."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from geode.extractors.regex_patterns import PATTERNS

LOGGER = logging.getLogger(__name__)

CCR_PAGE_HEADER_RE = re.compile(r"^CODE OF COLORADO REGULATIONS\b", re.IGNORECASE)
CCR_RULE_HEADING_RE = re.compile(
    r"^(?P<number>R\s*-?\s*\d+(?:(?:\s*-\s*|\s+)\d+(?:\.\d+)?[A-Za-z]?)+)"
    r"\s+(?P<heading>\S.*)$"
)
PAGE_NUMBER_RE = re.compile(r"^\d{1,4}$")
SEPARATOR_RE = re.compile(r"^_{4,}$")
MAX_PLAIN_SECTION_HEADING_LENGTH = 180


@dataclass
class StructureSubsection:
    """A parsed subsection node."""

    label: str
    text: str


@dataclass
class StructureSection:
    """A parsed section node."""

    number: str
    heading: str
    text: str = ""
    subsections: list[StructureSubsection] = field(default_factory=list)


@dataclass
class StructurePart:
    """A parsed part node."""

    label: str
    heading: str
    sections: list[StructureSection] = field(default_factory=list)


@dataclass
class StructureTree:
    """Parsed deterministic structure tree."""

    parts: list[StructurePart] = field(default_factory=list)
    sections: list[StructureSection] = field(default_factory=list)


def split_frontmatter(raw_text: str) -> tuple[dict[str, str], str]:
    """Split simple `key: value` frontmatter from a fixture document."""

    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw_text

    metadata: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body = "\n".join(lines[index + 1 :]).strip()
            return metadata, body
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')

    raise ValueError("frontmatter is missing closing delimiter")


def _part_from_line(line: str) -> tuple[str, str] | None:
    """Return a part label and heading from Markdown or plain CCR text."""

    heading = line.removeprefix("### ").strip() if line.startswith("### ") else line
    match = PATTERNS["part_boundary"].match(heading)
    if match is None:
        return None
    label = heading.split(maxsplit=2)[1].rstrip(".")
    return label, heading


def _section_from_line(line: str) -> tuple[str, str] | None:
    """Return a section number and heading from supported section boundary lines."""

    if line.startswith("#### "):
        heading_text = line.removeprefix("#### ").strip()
        number, _, heading = heading_text.partition(".")
        return number.strip(), heading.strip()

    ccr_rule_match = CCR_RULE_HEADING_RE.match(line)
    if ccr_rule_match is not None:
        heading = ccr_rule_match.group("heading").strip()
        if _looks_like_plain_section_heading(heading):
            return _normalize_ccr_rule_number(ccr_rule_match.group("number")), heading

    section_match = PATTERNS["section_number"].match(line)
    if section_match is None:
        return None

    heading = line[section_match.end() :].strip()
    if not _looks_like_plain_section_heading(heading):
        return None
    return section_match.group("section"), heading


def _normalize_ccr_rule_number(value: str) -> str:
    """Normalize OCR/PDF spacing around CCR rule identifiers."""

    compacted = re.sub(r"\s+", "", value)
    if compacted.startswith("R") and not compacted.startswith("R-"):
        return f"R-{compacted[1:].lstrip('-')}"
    return compacted


def _looks_like_plain_section_heading(heading: str) -> bool:
    """Guard plain-text section detection against decimal values in body text."""

    if not heading or len(heading) > MAX_PLAIN_SECTION_HEADING_LENGTH:
        return False
    if not any(character.isalpha() for character in heading):
        return False
    return not heading[0].islower()


def _is_navigation_noise(line: str) -> bool:
    """Return True for recurring PDF page artifacts that are not legal text."""

    return bool(
        CCR_PAGE_HEADER_RE.match(line)
        or PAGE_NUMBER_RE.match(line)
        or SEPARATOR_RE.match(line)
    )


def parse_structure(markdown_text: str) -> StructureTree:
    """Build a part-section-subsection structure from Markdown or numbered text."""

    tree = StructureTree()
    current_part: StructurePart | None = None
    current_section: StructureSection | None = None
    current_subsection: StructureSubsection | None = None
    section_lines: list[str] = []
    subsection_lines: list[str] = []
    skip_next_repeated_header_line = False

    def flush_subsection() -> None:
        """Store any pending subsection text."""

        nonlocal current_subsection, subsection_lines
        if current_subsection is not None:
            current_subsection.text = "\n".join(subsection_lines).strip()
            if current_section is not None:
                current_section.subsections.append(current_subsection)
        current_subsection = None
        subsection_lines = []

    def flush_section() -> None:
        """Store any pending section text."""

        nonlocal current_section, section_lines
        flush_subsection()
        if current_section is not None:
            current_section.text = "\n".join(section_lines).strip()
            if current_part is not None:
                current_part.sections.append(current_section)
            else:
                tree.sections.append(current_section)
        current_section = None
        section_lines = []

    def flush_part() -> None:
        """Store any pending part."""

        nonlocal current_part
        flush_section()
        if current_part is not None:
            tree.parts.append(current_part)
        current_part = None

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if _is_navigation_noise(line):
            skip_next_repeated_header_line = bool(CCR_PAGE_HEADER_RE.match(line))
            continue

        part_heading = _part_from_line(line)
        section_heading = _section_from_line(line)
        subsection_match = (
            PATTERNS["subsection_number"].match(line)
            or PATTERNS["subsection_letter"].match(line)
            or PATTERNS["subsection_roman"].match(line)
            or PATTERNS["subsubsection_letter"].match(line)
        )

        if (
            skip_next_repeated_header_line
            and part_heading is None
            and section_heading is None
            and subsection_match is None
        ):
            skip_next_repeated_header_line = False
            continue
        skip_next_repeated_header_line = False

        if part_heading is not None:
            flush_part()
            label, heading = part_heading
            current_part = StructurePart(label=label, heading=heading)
            continue

        if section_heading is not None:
            flush_section()
            number, heading = section_heading
            current_section = StructureSection(number=number, heading=heading)
            continue

        if subsection_match and current_section is not None:
            flush_subsection()
            label = subsection_match.group(0)
            current_subsection = StructureSubsection(label=label, text="")
            subsection_lines.append(line)
            continue

        if current_subsection is not None:
            subsection_lines.append(line)
        elif current_section is not None:
            section_lines.append(line)

    flush_part()
    flush_section()
    nested_sections = sum(len(part.sections) for part in tree.parts)
    subsection_count = sum(
        len(section.subsections)
        for part in tree.parts
        for section in part.sections
    ) + sum(len(section.subsections) for section in tree.sections)
    LOGGER.debug(
        "Structure parse summary parts=%s sections=%s subsections=%s",
        len(tree.parts),
        nested_sections + len(tree.sections),
        subsection_count,
    )
    return tree


def extract_metadata(text: str) -> dict[str, object]:
    """Run deterministic regex metadata extraction over text."""

    metadata: dict[str, object] = {"fields": {}, "confidence_flags": {}}
    fields = metadata["fields"]
    flags = metadata["confidence_flags"]
    if not isinstance(fields, dict) or not isinstance(flags, dict):
        raise TypeError("metadata containers must be dictionaries")

    for name, pattern in PATTERNS.items():
        matches = [
            match.groupdict() or {"match": match.group(0)}
            for match in pattern.finditer(text)
        ]
        if matches:
            fields[name] = matches
            flags[name] = "deterministic"
        else:
            fields[name] = []
            flags[name] = "needs_llm"
    return metadata
