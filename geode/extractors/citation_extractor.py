"""Citation extraction helpers for Colorado legal text."""

from __future__ import annotations

from dataclasses import dataclass
import re

from geode.extractors.regex_patterns import PATTERNS
from geode.schemas.validators import canonical_crs_id

CRS_NUMERIC_CITATION_RE = re.compile(
    r"\b(?P<title>\d{1,3}(?:\.\d+)?)-(?P<article>\d+(?:\.\d+)?)-"
    r"(?P<section>\d+(?:\.\d+)?)\b"
)


@dataclass(frozen=True)
class Citation:
    """Structured legal citation finding."""

    canonical_form: str
    as_written: str
    location: int
    found_by: str


def _canonical_crs_from_numeric(value: str) -> str | None:
    """Convert a numeric CRS citation into canonical form."""

    match = re.search(
        r"(?P<title>\d{1,3})-(?P<article>\d+(?:\.\d+)?)-(?P<section>\d+(?:\.\d+)?)",
        value,
    )
    if not match:
        return None
    return canonical_crs_id(match.group("title"), match.group("article"), match.group("section"))


def extract_crs_citations(text: str) -> list[Citation]:
    """Extract canonical CRS citations from legal text."""

    findings: dict[str, Citation] = {}
    for pattern_name in ("crs_citation", "crs_citation_alt"):
        for match in PATTERNS[pattern_name].finditer(text):
            as_written = match.group("citation")
            canonical = _canonical_crs_from_numeric(as_written)
            if canonical:
                findings.setdefault(
                    canonical,
                    Citation(
                        canonical_form=canonical,
                        as_written=as_written,
                        location=match.start(),
                        found_by="regex",
                    ),
                )
    for match in CRS_NUMERIC_CITATION_RE.finditer(text):
        canonical = canonical_crs_id(
            match.group("title"),
            match.group("article"),
            match.group("section"),
        )
        findings.setdefault(
            canonical,
            Citation(
                canonical_form=canonical,
                as_written=match.group(0),
                location=match.start(),
                found_by="regex",
            ),
        )
    return [findings[key] for key in sorted(findings)]


def extract_ccr_references(text: str) -> list[Citation]:
    """Extract CCR references from legal text."""

    citations: list[Citation] = []
    for match in PATTERNS["ccr_number"].finditer(text):
        as_written = match.group("ccr_number")
        canonical = "_".join(as_written.split())
        citations.append(
            Citation(
                canonical_form=canonical,
                as_written=as_written,
                location=match.start(),
                found_by="regex",
            )
        )
    return citations


def extract_federal_references(text: str) -> list[Citation]:
    """Extract CFR and USC references from legal text."""

    citations: list[Citation] = []
    for pattern_name in ("cfr_citation", "usc_citation"):
        for match in PATTERNS[pattern_name].finditer(text):
            as_written = match.group("citation")
            canonical = re.sub(r"\s+", " ", as_written).strip()
            citations.append(
                Citation(
                    canonical_form=canonical,
                    as_written=as_written,
                    location=match.start(),
                    found_by="regex",
                )
            )
    return citations


def extract_defined_terms(text: str) -> list[str]:
    """Extract quoted defined terms from legal text."""

    return sorted({match.group("term") for match in PATTERNS["defined_term"].finditer(text)})
