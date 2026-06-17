"""Download Colorado General Assembly bill PDFs from official public sources.

This is the Project Geode go-live acquisition module. It is deterministic and
contains no LLM calls, but it should be invoked by the pipeline only when live
downloads are explicitly requested.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path
from typing import Sequence
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from tqdm import tqdm

BASE_URL = "https://leg.colorado.gov"
DELAY_SECONDS = 0.5
MAX_RETRIES = 3
REQUEST_TIMEOUT_SECONDS = 30
PDF_MAGIC_BYTES = b"%PDF"
USER_AGENT = "ProjectGeode-MasterLegalDatabase/0.1"

BILL_NUMBER_RE = re.compile(
    r"\b(?P<type>HB|SB)\s*(?P<year>\d{2})[-\s]?(?P<number>\d{1,4})\b",
    re.IGNORECASE,
)
PDF_NEGATIVE_TERMS = (
    "fiscal note",
    "amendment",
    "committee report",
    "bill summary",
    "digest",
    "schedule",
)
PDF_POSITIVE_TERMS = (
    "bill text",
    "introduced",
    "engrossed",
    "reengrossed",
    "revised",
    "enrolled",
    "pdf",
)

LOGGER = logging.getLogger(__name__)


class ScraperError(RuntimeError):
    """Raised when a bill list or PDF cannot be fetched deterministically."""


def get_bill_list(session: str) -> list[dict]:
    """Scrape the Colorado bill index for one legislative session.

    Args:
        session: Session identifier such as ``"2025a"``.

    Returns:
        A list of bill dictionaries with ``bill_number``, ``url``, and ``title``.

    Raises:
        ScraperError: If no bill index page can be read or no bills are found.
    """

    session = session.strip()
    if not session:
        raise ValueError("session is required")

    pending_urls = _candidate_index_urls(session)
    visited_urls: set[str] = set()
    found_bills: dict[str, dict[str, str]] = {}
    fetched_any_page = False

    while pending_urls:
        page_url = pending_urls.pop(0)
        if page_url in visited_urls:
            continue
        visited_urls.add(page_url)

        try:
            html = _request_text(page_url, bill_number="SESSION_INDEX")
        except ScraperError as exc:
            LOGGER.error("SESSION_INDEX failed for %s with HTTP unavailable: %s", page_url, exc)
            continue

        fetched_any_page = True
        soup = BeautifulSoup(html, "lxml")
        for bill in _extract_bills_from_index(soup, page_url):
            found_bills.setdefault(bill["bill_number"], bill)
        for next_url in _pagination_links(soup, page_url):
            if next_url not in visited_urls and next_url not in pending_urls:
                pending_urls.append(next_url)

    if not fetched_any_page:
        raise ScraperError(f"could not fetch a bill index page for session {session}")
    if not found_bills:
        raise ScraperError(f"no HB or SB bills found for session {session}")

    return sorted(found_bills.values(), key=lambda item: _bill_sort_key(item["bill_number"]))


def download_pdf(bill_info: dict, output_dir: str) -> str:
    """Download one bill PDF to the output directory.

    Args:
        bill_info: Bill metadata with at least ``bill_number`` and ``url``.
        output_dir: Directory where the PDF should be written.

    Returns:
        The local PDF path as a string.

    Raises:
        ScraperError: If no PDF can be found or a fetched file is not a PDF.
    """

    bill_number = _required_bill_number(bill_info)
    output_path = Path(output_dir) / f"{bill_number}.pdf"
    if output_path.exists():
        if _path_has_pdf_magic(output_path):
            return str(output_path)
        raise ScraperError(f"existing file is not a valid PDF: {output_path}")

    pdf_urls = _pdf_url_candidates(bill_info)
    if not pdf_urls:
        raise ScraperError(f"PDF not found for {bill_number}")

    failures: list[str] = []
    for pdf_url in pdf_urls:
        try:
            response = _request_with_retries(pdf_url, bill_number=bill_number, stream=True)
        except ScraperError as exc:
            failures.append(f"{pdf_url}: {exc}")
            continue

        content = response.content
        if not content.startswith(PDF_MAGIC_BYTES):
            status = response.status_code
            LOGGER.error(
                "%s failed for %s with HTTP %s: response did not start with %%PDF",
                bill_number,
                pdf_url,
                status,
            )
            failures.append(f"{pdf_url}: response was not a PDF")
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_name(f"{output_path.name}.tmp")
        try:
            temp_path.write_bytes(content)
            temp_path.replace(output_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
        return str(output_path)

    raise ScraperError(f"PDF download failed for {bill_number}: {'; '.join(failures)}")


def download_session(session: str, output_dir: str = "data/raw_pdfs") -> list[str]:
    """Download all bill PDFs for one session without crashing on single failures.

    Args:
        session: Session identifier such as ``"2025a"``.
        output_dir: Directory where downloaded PDFs should be written.

    Returns:
        Local paths for successfully downloaded or already-present bill PDFs.
    """

    downloaded_paths, summary = _download_session_with_summary(session, output_dir)
    LOGGER.info("Download summary: %s", summary)
    return downloaded_paths


def _download_session_with_summary(
    session: str,
    output_dir: str,
) -> tuple[list[str], dict[str, object]]:
    """Download a session and return both paths and a structured summary.

    Args:
        session: Session identifier such as ``"2025a"``.
        output_dir: Directory where downloaded PDFs should be written.

    Returns:
        A tuple of successful local paths and a summary dictionary.
    """

    bills = get_bill_list(session)
    downloaded_paths: list[str] = []
    summary: dict[str, object] = {
        "session": session,
        "total": len(bills),
        "successes": [],
        "failures": [],
    }

    for bill in tqdm(bills, desc=f"Downloading {session} bills", unit="bill"):
        bill_number = str(bill.get("bill_number", "UNKNOWN"))
        try:
            local_path = download_pdf({**bill, "session": session}, output_dir)
        except ScraperError as exc:
            LOGGER.error("%s failed with HTTP unavailable: %s", bill_number, exc)
            _append_summary_item(
                summary,
                "failures",
                {"bill_number": bill_number, "error": str(exc)},
            )
            continue
        downloaded_paths.append(local_path)
        _append_summary_item(
            summary,
            "successes",
            {"bill_number": bill_number, "path": local_path},
        )

    return downloaded_paths, summary


def _candidate_index_urls(session: str) -> list[str]:
    """Build likely index URLs for a Colorado session.

    Args:
        session: Session identifier such as ``"2025a"``.

    Returns:
        Ordered candidate index URLs.
    """

    encoded = quote(session)
    encoded_upper = quote(session.upper())
    candidates = [
        f"{BASE_URL}/bills/{encoded}",
        f"{BASE_URL}/bills/{encoded_upper}",
        f"{BASE_URL}/bills?session={encoded}",
        f"{BASE_URL}/bills?field_session={encoded}",
        f"{BASE_URL}/bills?field_sessions={encoded}",
    ]
    return _unique_urls(candidates)


def _extract_bills_from_index(soup: BeautifulSoup, page_url: str) -> list[dict[str, str]]:
    """Extract HB/SB bill links from an index page.

    Args:
        soup: Parsed bill index page.
        page_url: Absolute URL of the current page.

    Returns:
        Bill dictionaries with number, URL, and title.
    """

    bills: dict[str, dict[str, str]] = {}
    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        href = str(anchor.get("href", ""))
        absolute_url = urljoin(page_url, href)
        if not _is_official_leg_url(absolute_url):
            continue
        text = _clean_text(anchor.get_text(" ", strip=True))
        bill_number = _normalize_bill_number(f"{text} {href}")
        if bill_number is None or "/bills" not in urlparse(absolute_url).path:
            continue
        bills.setdefault(
            bill_number,
            {
                "bill_number": bill_number,
                "url": absolute_url,
                "title": _title_for_bill_link(anchor, bill_number),
            },
        )
    return list(bills.values())


def _pagination_links(soup: BeautifulSoup, page_url: str) -> list[str]:
    """Extract pagination links from an index page.

    Args:
        soup: Parsed bill index page.
        page_url: Absolute URL of the current page.

    Returns:
        Absolute pagination URLs on the official legislative host.
    """

    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        href = str(anchor.get("href", ""))
        absolute_url = urljoin(page_url, href)
        if not _is_official_leg_url(absolute_url):
            continue
        text = _clean_text(anchor.get_text(" ", strip=True)).casefold()
        classes = " ".join(str(value) for value in anchor.get("class", [])).casefold()
        rel = " ".join(str(value) for value in anchor.get("rel", [])).casefold()
        context = f"{text} {classes} {rel} {href}".casefold()
        if "next" in context or ("pager" in context and "page=" in href):
            links.append(absolute_url)
    return _unique_urls(links)


def _pdf_url_candidates(bill_info: dict) -> list[str]:
    """Resolve likely PDF URLs for a bill.

    Args:
        bill_info: Bill metadata with bill number and page URL.

    Returns:
        Ordered candidate PDF URLs.
    """

    bill_number = _required_bill_number(bill_info)
    candidates: list[str] = []
    explicit_pdf = bill_info.get("pdf_url")
    if isinstance(explicit_pdf, str):
        candidates.append(explicit_pdf)

    page_url = str(bill_info.get("url", "")).strip()
    if not page_url:
        raise ScraperError(f"missing bill page URL for {bill_number}")
    if _looks_like_pdf_url(page_url):
        candidates.append(page_url)
    else:
        page_html = _request_text(page_url, bill_number=bill_number)
        soup = BeautifulSoup(page_html, "lxml")
        candidates.extend(_extract_pdf_links(soup, page_url, bill_number))

    session = str(bill_info.get("session", "")).strip() or None
    candidates.extend(_direct_pdf_candidates(bill_number, session))
    return _unique_urls(candidates)


def _extract_pdf_links(soup: BeautifulSoup, page_url: str, bill_number: str) -> list[str]:
    """Extract and rank PDF links from a bill page.

    Args:
        soup: Parsed bill detail page.
        page_url: Absolute URL of the bill detail page.
        bill_number: Canonical bill number used for ranking.

    Returns:
        Ordered PDF URLs, best candidate first.
    """

    scored_links: list[tuple[int, str]] = []
    for node in soup.find_all(["a", "iframe", "embed", "object"]):
        if not isinstance(node, Tag):
            continue
        raw_url = node.get("href") or node.get("src") or node.get("data")
        if not isinstance(raw_url, str):
            continue
        absolute_url = urljoin(page_url, raw_url)
        if not _is_official_leg_url(absolute_url) or not _looks_like_pdf_url(absolute_url):
            continue
        text = _clean_text(node.get_text(" ", strip=True))
        scored_links.append((_pdf_link_score(absolute_url, text, bill_number), absolute_url))
    return [url for _, url in sorted(scored_links, key=lambda item: item[0], reverse=True)]


def _direct_pdf_candidates(bill_number: str, session: str | None) -> list[str]:
    """Build direct PDF URL candidates from common legislative file patterns.

    Args:
        bill_number: Canonical bill number such as ``"HB25-1001"``.
        session: Optional session identifier such as ``"2025a"``.

    Returns:
        Ordered direct PDF URL candidates.
    """

    match = BILL_NUMBER_RE.match(bill_number)
    if match is None:
        return []
    prefix = match.group("type").lower()
    year = match.group("year")
    number = match.group("number")
    session_ids = [value for value in (session, f"20{year}a") if value]
    candidates: list[str] = []
    for session_id in session_ids:
        session_lower = session_id.lower()
        session_upper = session_id.upper()
        candidates.extend(
            [
                (
                    f"{BASE_URL}/sites/default/files/documents/{session_upper}/"
                    f"bills/{session_lower}_{number}_01.pdf"
                ),
                (
                    f"{BASE_URL}/sites/default/files/documents/{session_upper}/"
                    f"bills/{session_lower}_{prefix}{number}_01.pdf"
                ),
                f"{BASE_URL}/bills/{session_lower}/{bill_number.lower()}.pdf",
            ]
        )
    return _unique_urls(candidates)


def _pdf_link_score(url: str, text: str, bill_number: str) -> int:
    """Score a PDF link so bill text is preferred over ancillary documents.

    Args:
        url: Candidate PDF URL.
        text: Link text or nearby display text.
        bill_number: Canonical bill number used for matching.

    Returns:
        Integer score where higher is better.
    """

    haystack = f"{url} {text}".casefold()
    compact_haystack = re.sub(r"[^a-z0-9]", "", haystack)
    compact_bill = re.sub(r"[^a-z0-9]", "", bill_number.casefold())
    score = 10
    if compact_bill and compact_bill in compact_haystack:
        score += 50
    for term in PDF_POSITIVE_TERMS:
        if term in haystack:
            score += 10
    for term in PDF_NEGATIVE_TERMS:
        if term in haystack:
            score -= 40
    return score


def _request_text(url: str, bill_number: str) -> str:
    """Fetch a URL and return response text.

    Args:
        url: URL to fetch.
        bill_number: Bill number or context label for logging.

    Returns:
        Response text.

    Raises:
        ScraperError: If the request fails after retries.
    """

    response = _request_with_retries(url, bill_number=bill_number, stream=False)
    return response.text


def _request_with_retries(url: str, bill_number: str, stream: bool) -> requests.Response:
    """Fetch a URL with retry, backoff, and rate limiting.

    Args:
        url: URL to fetch.
        bill_number: Bill number or context label for stderr logging.
        stream: Whether to request a streaming response.

    Returns:
        Successful ``requests.Response`` object.

    Raises:
        ScraperError: If the request fails after all retries.
    """

    last_error = "unknown error"
    attempts = MAX_RETRIES + 1
    for attempt in range(attempts):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT_SECONDS,
                stream=stream,
            )
            if response.status_code == requests.codes.ok:
                time.sleep(DELAY_SECONDS)
                return response
            last_error = f"HTTP {response.status_code}"
            LOGGER.error(
                "%s failed for %s with HTTP %s",
                bill_number,
                url,
                response.status_code,
            )
        except requests.RequestException as exc:
            last_error = str(exc)
            LOGGER.error("%s failed for %s with HTTP unavailable: %s", bill_number, url, exc)

        time.sleep(DELAY_SECONDS)
        if attempt < MAX_RETRIES:
            time.sleep(2**attempt)

    raise ScraperError(f"{url} failed after {attempts} attempts: {last_error}")


def _required_bill_number(bill_info: dict) -> str:
    """Read and normalize a bill number from a bill dictionary.

    Args:
        bill_info: Bill metadata dictionary.

    Returns:
        Canonical bill number.

    Raises:
        ScraperError: If no HB/SB bill number can be found.
    """

    raw_value = str(bill_info.get("bill_number", "")).strip()
    bill_number = _normalize_bill_number(raw_value)
    if bill_number is None:
        raise ScraperError(f"invalid or missing bill_number: {raw_value!r}")
    return bill_number


def _normalize_bill_number(value: str) -> str | None:
    """Normalize an HB/SB bill reference.

    Args:
        value: Raw text containing a bill number.

    Returns:
        Canonical bill number, or ``None`` when no bill number is present.
    """

    match = BILL_NUMBER_RE.search(value)
    if match is None:
        return None
    prefix = match.group("type").upper()
    year = match.group("year")
    number = match.group("number")
    if len(number) < 3:
        number = number.zfill(3)
    return f"{prefix}{year}-{number}"


def _bill_sort_key(bill_number: str) -> tuple[str, int, int]:
    """Return a stable sort key for bill numbers.

    Args:
        bill_number: Canonical bill number.

    Returns:
        Tuple suitable for natural sorting.
    """

    match = BILL_NUMBER_RE.match(bill_number)
    if match is None:
        return (bill_number, 0, 0)
    return (
        match.group("type").upper(),
        int(match.group("year")),
        int(match.group("number")),
    )


def _title_for_bill_link(anchor: Tag, bill_number: str) -> str:
    """Derive a human-readable bill title from link or row text.

    Args:
        anchor: Anchor tag pointing to the bill.
        bill_number: Canonical bill number to remove from title text.

    Returns:
        Cleaned title string, possibly empty when the page has no title text.
    """

    candidates = [anchor.get_text(" ", strip=True)]
    for parent_name in ("tr", "li", "article", "div"):
        parent = anchor.find_parent(parent_name)
        if isinstance(parent, Tag):
            candidates.append(parent.get_text(" ", strip=True))
    for candidate in candidates:
        title = _clean_bill_title(candidate, bill_number)
        if title:
            return title
    return ""


def _clean_bill_title(value: str, bill_number: str) -> str:
    """Clean bill-number boilerplate from a candidate title.

    Args:
        value: Candidate title text.
        bill_number: Canonical bill number to remove.

    Returns:
        Cleaned candidate title.
    """

    text = _clean_text(value)
    text = BILL_NUMBER_RE.sub("", text)
    text = text.replace(bill_number, "")
    text = re.sub(r"\b(View|Bill Text|PDF|Details)\b", "", text, flags=re.IGNORECASE)
    return text.strip(" -:|\u2013\u2014")


def _path_has_pdf_magic(path: Path) -> bool:
    """Check whether an existing file starts with PDF magic bytes.

    Args:
        path: File path to inspect.

    Returns:
        ``True`` when the file starts with ``%PDF``.
    """

    with path.open("rb") as handle:
        return handle.read(len(PDF_MAGIC_BYTES)) == PDF_MAGIC_BYTES


def _looks_like_pdf_url(url: str) -> bool:
    """Return whether a URL appears to reference a PDF.

    Args:
        url: Candidate URL.

    Returns:
        ``True`` when the URL path or query points at a PDF.
    """

    parsed = urlparse(url)
    haystack = f"{parsed.path} {parsed.query}".casefold()
    return ".pdf" in haystack or "pdf" in haystack


def _is_official_leg_url(url: str) -> bool:
    """Return whether a URL is on the Colorado General Assembly host.

    Args:
        url: Candidate URL.

    Returns:
        ``True`` for HTTPS URLs under ``leg.colorado.gov``.
    """

    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.netloc.casefold() == "leg.colorado.gov"


def _clean_text(value: str) -> str:
    """Normalize whitespace in extracted page text.

    Args:
        value: Raw text.

    Returns:
        Whitespace-normalized text.
    """

    return re.sub(r"\s+", " ", value).strip()


def _unique_urls(urls: Sequence[str]) -> list[str]:
    """Return URLs in original order without duplicates.

    Args:
        urls: URL sequence that may contain duplicates or blanks.

    Returns:
        Ordered list of unique non-empty URLs.
    """

    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def _append_summary_item(
    summary: dict[str, object],
    key: str,
    item: dict[str, str],
) -> None:
    """Append one success or failure item to a summary dictionary.

    Args:
        summary: Mutable summary dictionary.
        key: Summary list key to append into.
        item: Item to append.
    """

    bucket = summary.setdefault(key, [])
    if isinstance(bucket, list):
        bucket.append(item)


def _build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser.

    Returns:
        Configured argument parser.
    """

    parser = argparse.ArgumentParser(
        description="Download Colorado General Assembly bill PDFs.",
    )
    parser.add_argument("--session", required=True, help='Session identifier, e.g. "2025a".')
    parser.add_argument(
        "--output-dir",
        default="data/raw_pdfs",
        help='Output directory for PDFs, default "data/raw_pdfs".',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List bills found for the session without downloading PDFs.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the scraper command-line interface.

    Args:
        argv: Optional argument sequence for tests or embedded callers.

    Returns:
        Process exit code.
    """

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)
    print(
        "NOTE: This module downloads real bill PDFs from the Colorado General "
        "Assembly. Use --dry-run to preview without downloading.",
        file=sys.stderr,
    )
    args = _build_parser().parse_args(argv)

    if args.dry_run:
        try:
            bills = get_bill_list(args.session)
        except ScraperError as exc:
            LOGGER.error("session %s failed with HTTP unavailable: %s", args.session, exc)
            return 1
        print(f"Found {len(bills)} bills for session {args.session}.")
        for bill in bills:
            bill_number = str(bill.get("bill_number", "UNKNOWN"))
            title = str(bill.get("title", "")).strip()
            url = str(bill.get("url", "")).strip()
            suffix = f" - {title}" if title else ""
            print(f"{bill_number}{suffix}\n  {url}")
        print("Dry run complete. No PDFs downloaded.")
        return 0

    try:
        downloaded_paths, summary = _download_session_with_summary(args.session, args.output_dir)
    except ScraperError as exc:
        LOGGER.error("session %s failed with HTTP unavailable: %s", args.session, exc)
        return 1

    total = int(summary["total"])
    failure_count = len(summary["failures"]) if isinstance(summary["failures"], list) else 0
    print(f"Downloaded {len(downloaded_paths)} of {total} bills. {failure_count} failures.")
    return 0 if failure_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
