"""Table-oriented extraction helpers for Colorado Register publications."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from geode.connectors.archive_paths import safe_archive_stem

CCR_RE = re.compile(r"\b(?P<ccr>\d{1,2}\s+CCR\s+\d+-\d+(?:-\d+)?)\b", re.IGNORECASE)
EDOCKET_HREF_RE = re.compile(
    r"""href=['"](?P<href>[^'"]*eDocket[^'"]*)['"]""",
    re.IGNORECASE,
)
TRACKING_RE = re.compile(r"\btrackingNum=(?P<tracking>[A-Za-z0-9_-]+)", re.IGNORECASE)
DATE_RE = re.compile(r"\b(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>20\d{2})\b")
ROW_RE = re.compile(r"<tr\b[^>]*>.*?</tr>", re.IGNORECASE | re.DOTALL)
CELL_RE = re.compile(r"<td\b[^>]*>(?P<cell>.*?)</td>", re.IGNORECASE | re.DOTALL)
HEADING_RE = re.compile(
    r"<(?:h[1-6]|p|div)\b[^>]*(?:pagehead|header|smallheader|section)[^>]*>"
    r"(?P<heading>.*?)</(?:h[1-6]|p|div)>",
    re.IGNORECASE | re.DOTALL,
)

SECTION_NOTICE_TYPES: tuple[tuple[str, str], ...] = (
    ("adopted", "adopted"),
    ("permanent", "adopted"),
    ("proposed", "proposed"),
    ("hearing", "hearing"),
    ("emergency", "emergency"),
    ("temporary", "temporary"),
    ("repeal", "repealed"),
)


class RegisterTableNotice(BaseModel):
    """One notice-like row parsed from a Colorado Register HTML table."""

    model_config = ConfigDict(extra="forbid")

    row_number: int = Field(ge=1)
    section_heading: str | None = None
    department: str | None = None
    agency: str | None = None
    ccr_citation: str = Field(min_length=1)
    ccr_rule_affected: str = Field(min_length=1)
    edocket_tracking_number: str | None = None
    edocket_href: str | None = None
    hearing_date: str | None = None
    effective_date: str | None = None
    summary: str = Field(min_length=1)
    notice_type: str = Field(min_length=1)
    notice_type_source: str = Field(min_length=1)
    evidence: str = Field(min_length=1)


@dataclass(frozen=True)
class _Token:
    """A heading or row token found in source order."""

    kind: str
    start: int
    html: str


def extract_register_table_notices(html: str) -> list[RegisterTableNotice]:
    """Extract notice-like rows from Register HTML tables."""

    notices: list[RegisterTableNotice] = []
    section_heading: str | None = None
    row_number = 0
    for token in _source_tokens(html):
        if token.kind == "heading":
            heading = _clean_html(token.html)
            if _looks_like_section_heading(heading):
                section_heading = heading
            continue
        cells = [_clean_html(match.group("cell")) for match in CELL_RE.finditer(token.html)]
        if len(cells) < 3:
            continue
        ccr_match = CCR_RE.search(" ".join(cells))
        if not ccr_match:
            continue
        row_number += 1
        ccr_citation = _clean(ccr_match.group("ccr"))
        tracking, href = _edocket_from_row(token.html)
        row_date = _date_from_cells(cells)
        agency = _agency_from_cells(cells, ccr_citation)
        department = cells[0] if cells else None
        summary = _summary_from_cells(cells, ccr_citation)
        notice_type, notice_type_source = _notice_type(section_heading, " ".join(cells))
        notices.append(
            RegisterTableNotice(
                row_number=row_number,
                section_heading=section_heading,
                department=department,
                agency=agency,
                ccr_citation=ccr_citation,
                ccr_rule_affected=_canonical_ccr_id(ccr_citation),
                edocket_tracking_number=tracking,
                edocket_href=href,
                hearing_date=row_date if notice_type in {"hearing", "proposed"} else None,
                effective_date=row_date if notice_type in {"adopted", "emergency", "temporary"} else None,
                summary=summary,
                notice_type=notice_type,
                notice_type_source=notice_type_source,
                evidence=_clean_html(token.html)[:1000],
            )
        )
    return notices


def _source_tokens(html: str) -> Iterable[_Token]:
    """Yield heading and row tokens in source order."""

    tokens: list[_Token] = []
    for match in HEADING_RE.finditer(html):
        tokens.append(_Token("heading", match.start(), match.group(0)))
    for match in ROW_RE.finditer(html):
        tokens.append(_Token("row", match.start(), match.group(0)))
    return sorted(tokens, key=lambda token: token.start)


def _looks_like_section_heading(text: str) -> bool:
    """Return whether heading text can help classify rulemaking rows."""

    lowered = text.casefold()
    return any(token in lowered for token in ("rule", "notice", "hearing", "adopted", "emergency"))


def _edocket_from_row(row_html: str) -> tuple[str | None, str | None]:
    """Extract eDocket tracking number and relative/absolute link from a table row."""

    href_match = EDOCKET_HREF_RE.search(row_html)
    href = unescape(href_match.group("href")) if href_match else None
    tracking_match = TRACKING_RE.search(href or row_html)
    tracking = safe_archive_stem(tracking_match.group("tracking")) if tracking_match else None
    return tracking, href


def _date_from_cells(cells: list[str]) -> str | None:
    """Return the first US-format date found in table cells."""

    for cell in cells:
        match = DATE_RE.search(cell)
        if match:
            return (
                f"{match.group('year')}-{int(match.group('month')):02d}-"
                f"{int(match.group('day')):02d}"
            )
    return None


def _agency_from_cells(cells: list[str], ccr_citation: str) -> str | None:
    """Infer agency from the table cells near the CCR citation."""

    try:
        ccr_index = next(index for index, cell in enumerate(cells) if ccr_citation in cell)
    except StopIteration:
        ccr_index = -1
    if ccr_index > 0:
        return cells[ccr_index - 1]
    if len(cells) >= 2:
        return cells[1]
    return None


def _summary_from_cells(cells: list[str], ccr_citation: str) -> str:
    """Return the most descriptive table cell as summary text."""

    candidates = [
        cell
        for cell in cells
        if cell
        and ccr_citation not in cell
        and not DATE_RE.search(cell)
        and "tracking" not in cell.casefold()
    ]
    if not candidates:
        candidates = cells
    return max(candidates, key=len)[:1000]


def _notice_type(section_heading: str | None, row_text: str) -> tuple[str, str]:
    """Infer notice type from section heading first, then row text."""

    for source, text in (("register_section_heading", section_heading or ""), ("row_text", row_text)):
        lowered = text.casefold()
        for token, notice_type in SECTION_NOTICE_TYPES:
            if token in lowered:
                return notice_type, source
    return "rulemaking", "default"


def _canonical_ccr_id(value: str) -> str:
    """Normalize a CCR citation into Geode regulation ID form."""

    return re.sub(r"\s+", "_", _clean(value))


def _clean_html(value: str) -> str:
    """Strip simple HTML markup and collapse whitespace."""

    text = re.sub(r"<[^>]+>", " ", value or "")
    return _clean(unescape(text))


def _clean(value: str) -> str:
    """Collapse whitespace."""

    return re.sub(r"\s+", " ", value or "").strip()
