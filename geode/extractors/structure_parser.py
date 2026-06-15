"""Shared structure parsing primitives."""

from __future__ import annotations

from dataclasses import dataclass, field

from geode.extractors.regex_patterns import PATTERNS


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


def parse_structure(markdown_text: str) -> StructureTree:
    """Build a part-section-subsection structure from Markdown or numbered text."""

    tree = StructureTree()
    current_part: StructurePart | None = None
    current_section: StructureSection | None = None
    current_subsection: StructureSubsection | None = None
    section_lines: list[str] = []
    subsection_lines: list[str] = []

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

        part_heading = line.startswith("### Part ") or PATTERNS["part_boundary"].match(line)
        if part_heading:
            flush_part()
            if line.startswith("### Part "):
                heading = line.removeprefix("### ").strip()
            else:
                heading = line
            current_part = StructurePart(label=heading.split()[1], heading=heading)
            continue

        if line.startswith("#### "):
            flush_section()
            heading_text = line.removeprefix("#### ").strip()
            number, _, heading = heading_text.partition(".")
            current_section = StructureSection(number=number.strip(), heading=heading.strip())
            continue

        subsection_match = (
            PATTERNS["subsection_number"].match(line)
            or PATTERNS["subsection_letter"].match(line)
            or PATTERNS["subsection_roman"].match(line)
            or PATTERNS["subsubsection_letter"].match(line)
        )
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
