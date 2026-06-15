"""Regular expression patterns shared by extractors."""

from __future__ import annotations

import re

PATTERNS = {
    "ccr_number": re.compile(r"\b(?P<ccr_number>\d{1,2}\s+CCR\s+\d+-\d+(?:-\d+)?)\b"),
    "crs_citation": re.compile(
        r"(?:section|§|sec\.)\s*"
        r"(?P<citation>\d{1,3}-\d+(?:\.\d+)?-\d+(?:\.\d+)?(?:\s*\([^)]+\))*)"
        r",?\s*C\.R\.S\.",
        re.IGNORECASE,
    ),
    "crs_citation_alt": re.compile(
        r"C\.R\.S\.\s*§?\s*"
        r"(?P<citation>\d{1,3}-\d+(?:\.\d+)?-\d+(?:\.\d+)?)",
        re.IGNORECASE,
    ),
    "part_boundary": re.compile(r"^(?:PART|Part)\s+(?P<part>\d+|[A-Z]|[IVX]+)[.\s]"),
    "section_number": re.compile(r"^(?P<section>\d+\.\d+(?:\.\d+)?)\s"),
    "subsection_number": re.compile(r"^\((?P<number>\d{1,3})\)"),
    "subsection_letter": re.compile(r"^\((?P<letter>[a-z]{1,2})\)"),
    "subsection_roman": re.compile(r"^\((?P<roman>[IVXivx]+)\)"),
    "subsubsection_letter": re.compile(r"^\((?P<letter>[A-Z]{1,2})\)"),
    "defined_term": re.compile(r"[\"“](?P<term>[^\"”]+)[\"”]\s+means\b"),
    "effective_date": re.compile(r"[Ee]ffective\s+(?P<date>\w+\s+\d{1,2},?\s+\d{4})"),
    "adopted_date": re.compile(r"[Aa]dopted\s+(?P<date>\w+\s+\d{1,2},?\s+\d{4})"),
    "cfr_citation": re.compile(r"\b(?P<citation>\d+\s+C\.?F\.?R\.?\s+[\d.]+(?:\([^)]+\))?)"),
    "usc_citation": re.compile(r"\b(?P<citation>\d+\s+U\.?S\.?C\.?\s+(?:§\s*)?\d+[a-z]?)"),
    "department": re.compile(r"\bDepartment\s+of\s+(?P<department>[A-Z][A-Za-z &,-]+)"),
    "agency": re.compile(r"\b(?P<agency>[A-Z][A-Za-z &,-]+(?:Board|Commission|Division|Office))\b"),
}

ARTICLE_HEADING_RE = re.compile(r"^##\s+Article\s+(?P<number>[\d.]+)\s+-\s+(?P<name>.+)$")
PART_HEADING_RE = re.compile(r"^###\s+Part\s+(?P<number>[\d.]+)\s+-\s+(?P<name>.+)$")
SECTION_HEADING_RE = re.compile(
    r"^####\s+(?P<title>\d{1,2}(?:\.\d+)?)-(?P<article>\d+(?:\.\d+)?)-"
    r"(?P<section>\d+(?:\.\d+)?)\.\s+(?P<heading>.+)$"
)
TITLE_HEADING_RE = re.compile(
    r"^#\s+Title\s+(?P<number>\d{1,2}(?:\.\d+)?)\s+-\s+(?P<name>.+)$"
)
