"""Diagnose official-source fetches with Geode's hardened HTTP client."""

from __future__ import annotations

import argparse
import sys
from typing import Any
from urllib.parse import urljoin, urlparse

from geode.connectors.ccr_scraper import (
    CCR_DEPARTMENT_LIST_URL,
    CCR_WELCOME_URL,
    GOOGLE_REFERER,
    SOS_HOME_URL,
    _agency_links,
    _download_urls_from_rule_scripts,
    _is_javascript_href,
    _looks_docx,
    _looks_pdf,
    _parse_links,
    _rule_entries_from_page,
)
from geode.net.http_client import (
    GeodeFetchError,
    GeodeHttpClient,
    GeodeHttpClientConfig,
    is_curl_cffi_session,
)

KEY_HEADERS = (
    "content-type",
    "content-length",
    "server",
    "date",
    "set-cookie",
    "location",
    "retry-after",
)


def diagnose(
    url: str,
    *,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = 30.0,
) -> int:
    """Fetch one URL and print response diagnostics."""

    client = _build_client(
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
    )
    referer = GOOGLE_REFERER
    if _is_sos_ccr_url(url) and url != SOS_HOME_URL:
        _warm_sos_session(client)
        referer = _referer_for_sos_url(url)

    result = _fetch_step(client, "target", url, referer=referer, preview=True)
    return 0 if result.ok else 1


def diagnose_ccr_chain(
    *,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = 30.0,
    verbose: bool = False,
) -> int:
    """Walk one browser-like CCR discovery path and report where it fails."""

    client = _build_client(
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
    )
    print(f"curl_cffi active: {is_curl_cffi_session(client.session)}")

    home = _fetch_step(client, "sos_home", SOS_HOME_URL, referer=GOOGLE_REFERER)
    next_referer = SOS_HOME_URL if home.ok else GOOGLE_REFERER

    welcome = _fetch_step(
        client,
        "ccr_welcome",
        CCR_WELCOME_URL,
        referer=next_referer,
        preview=verbose,
    )
    if not welcome.ok:
        return 1

    department = _fetch_step(
        client,
        "department_list",
        CCR_DEPARTMENT_LIST_URL,
        referer=CCR_WELCOME_URL,
        preview=verbose,
    )
    if not department.ok or department.response is None:
        return 1

    agency_links = _agency_links(department.response.text, CCR_DEPARTMENT_LIST_URL)
    print(f"discovered_agency_links: {len(agency_links)}")
    if not agency_links:
        _print_preview(department.response)
        return 1

    agency_url, department_name, agency_name = agency_links[0]
    agency = _fetch_step(
        client,
        "first_agency",
        agency_url,
        referer=CCR_DEPARTMENT_LIST_URL,
        preview=verbose,
    )
    if not agency.ok or agency.response is None:
        return 1

    rules = _rule_entries_from_page(
        agency.response.text,
        agency_url,
        department_name,
        agency_name,
    )
    print(f"first_agency_rule_candidates: {len(rules)}")
    if not rules:
        _print_preview(agency.response)
        return 1

    rule = rules[0]
    document_url = str(rule.pdf_url or rule.docx_url or "")
    document_referer = agency_url
    if not document_url and str(rule.source_page_url) != agency_url:
        rule_page = _fetch_step(
            client,
            "first_rule_page",
            str(rule.source_page_url),
            referer=agency_url,
            preview=verbose,
        )
        if not rule_page.ok or rule_page.response is None:
            return 1
        document_url = _document_url_from_rule_page(
            rule_page.response.text,
            str(rule.source_page_url),
        )
        document_referer = str(rule.source_page_url)

    if not document_url:
        print("downstream_document_url: none discovered")
        return 1

    document = _fetch_step(
        client,
        "first_document",
        document_url,
        referer=document_referer,
        preview=verbose,
    )
    return 0 if document.ok else 1


def _build_client(
    *,
    max_retries: int,
    base_delay: float,
    timeout_seconds: float,
) -> GeodeHttpClient:
    """Build the diagnostic HTTP client."""

    return GeodeHttpClient(
        config=GeodeHttpClientConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
        )
    )


def _warm_sos_session(client: GeodeHttpClient) -> None:
    """Walk the public SOS CCR referer chain before a target diagnostic fetch."""

    home = _fetch_step(client, "warm_sos_home", SOS_HOME_URL, referer=GOOGLE_REFERER)
    next_referer = SOS_HOME_URL if home.ok else GOOGLE_REFERER
    _fetch_step(client, "warm_ccr_welcome", CCR_WELCOME_URL, referer=next_referer)
    _fetch_step(
        client,
        "warm_department_list",
        CCR_DEPARTMENT_LIST_URL,
        referer=CCR_WELCOME_URL,
    )


def _fetch_step(
    client: GeodeHttpClient,
    name: str,
    url: str,
    *,
    referer: str | None,
    preview: bool = False,
) -> "_FetchStepResult":
    """Fetch and print one diagnostic step."""

    try:
        response = client.get(url, referer=referer)
    except GeodeFetchError as exc:
        print(f"\n[{name}] FAILED: {exc}", file=sys.stderr)
        if exc.last_response is None:
            return _FetchStepResult(ok=False, response=None)
        response = exc.last_response
        _print_response(name, url, referer, response, preview=True)
        return _FetchStepResult(ok=False, response=response)

    _print_response(name, url, referer, response, preview=preview)
    status = int(response.status_code or 0)
    return _FetchStepResult(ok=status < 400, response=response)


class _FetchStepResult:
    """One diagnostic fetch result."""

    def __init__(self, *, ok: bool, response: Any | None) -> None:
        """Create a diagnostic fetch result."""

        self.ok = ok
        self.response = response


def _print_response(
    name: str,
    requested_url: str,
    referer: str | None,
    response: Any,
    *,
    preview: bool,
) -> None:
    """Print concise diagnostics for one response."""

    print(f"\n[{name}]")
    print(f"requested_url: {requested_url}")
    print(f"final_url: {getattr(response, 'url', requested_url)}")
    print(f"referer: {referer}")
    print(f"status_code: {getattr(response, 'status_code', 'unknown')}")
    print("headers:")
    for key, value in _response_headers(response).items():
        if key.lower() in KEY_HEADERS:
            print(f"  {key}: {value}")
    if preview:
        _print_preview(response)


def _print_preview(response: Any) -> None:
    """Print a small normalized response body preview."""

    print("body_preview:")
    print(_response_text(response)[:500])


def _document_url_from_rule_page(html: str, source_page_url: str) -> str:
    """Return the first PDF or DOCX URL found on a rule-info page."""

    pdf_url, docx_url = _download_urls_from_rule_scripts(html, source_page_url)
    if pdf_url or docx_url:
        return pdf_url or docx_url or ""

    parser = _parse_links(html)
    for link in parser.links:
        if _is_javascript_href(link.href):
            continue
        absolute = urljoin(source_page_url, link.href)
        lower = absolute.lower()
        if _looks_pdf(lower) or _looks_docx(lower):
            return absolute
    return ""


def _referer_for_sos_url(url: str) -> str:
    """Return the most realistic referer for a SOS diagnostic target."""

    parsed = urlparse(url)
    if parsed.path.endswith("/CCR/DisplayRule.do"):
        return CCR_DEPARTMENT_LIST_URL
    if "GenerateRule" in parsed.path:
        return CCR_DEPARTMENT_LIST_URL
    if parsed.path.startswith("/CCR/"):
        return CCR_WELCOME_URL
    return GOOGLE_REFERER


def _is_sos_ccr_url(url: str) -> bool:
    """Return whether a URL belongs to the SOS CCR surface."""

    parsed = urlparse(url)
    return parsed.netloc.lower() == "www.sos.state.co.us" and parsed.path.startswith("/CCR/")


def _response_headers(response: Any) -> dict[str, str]:
    """Return response headers as a plain string dictionary."""

    headers = getattr(response, "headers", {})
    if hasattr(headers, "items"):
        return {str(key): str(value) for key, value in headers.items()}
    return {}


def _response_text(response: Any) -> str:
    """Return response text for preview output."""

    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    content = getattr(response, "content", b"")
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return str(content)


def _build_parser() -> argparse.ArgumentParser:
    """Build the diagnostic CLI parser."""

    parser = argparse.ArgumentParser(description="Diagnose a Geode HTTP fetch.")
    parser.add_argument(
        "url",
        nargs="?",
        default=CCR_WELCOME_URL,
        help="URL to fetch in single-URL mode. Defaults to the CCR welcome page.",
    )
    parser.add_argument(
        "--ccr-chain",
        action="store_true",
        help="Walk landing, department, agency, rule, and document CCR requests.",
    )
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--base-delay", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--verbose", action="store_true", help="Print body previews.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the diagnostic CLI."""

    _configure_console_output()
    args = _build_parser().parse_args(argv)
    if args.ccr_chain:
        return diagnose_ccr_chain(
            max_retries=args.max_retries,
            base_delay=args.base_delay,
            timeout_seconds=args.timeout_seconds,
            verbose=args.verbose,
        )
    return diagnose(
        args.url,
        max_retries=args.max_retries,
        base_delay=args.base_delay,
        timeout_seconds=args.timeout_seconds,
    )


def _configure_console_output() -> None:
    """Prefer UTF-8 output for diagnostic body previews."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
