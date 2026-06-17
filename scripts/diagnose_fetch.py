"""Diagnose an official-source fetch with Geode's hardened HTTP client."""

from __future__ import annotations

import argparse
import sys
from typing import Any
from urllib.parse import urlparse

from geode.net.http_client import (
    GeodeFetchError,
    build_session,
    is_curl_cffi_session,
    polite_get,
)

GOOGLE_REFERER = "https://www.google.com/"
SOS_HOME_URL = "https://www.sos.state.co.us/"
CCR_WELCOME_URL = "https://www.sos.state.co.us/CCR/Welcome.do"
CCR_INDEX_URL = "https://www.sos.state.co.us/CCR/NumericalDeptList.do"
KEY_HEADERS = (
    "content-type",
    "content-length",
    "server",
    "date",
    "set-cookie",
    "location",
)


def diagnose(url: str) -> int:
    """Fetch one URL and print response diagnostics."""

    session = build_session()
    referer = GOOGLE_REFERER
    if _is_sos_ccr_url(url) and url != SOS_HOME_URL:
        _warm_sos_session(session)
        referer = _referer_for_sos_url(url)

    try:
        response = polite_get(session, url, referer=referer)
    except GeodeFetchError as exc:
        print(f"FETCH FAILED: {exc}", file=sys.stderr)
        response = exc.last_response
        if response is None:
            print(f"curl_cffi active: {is_curl_cffi_session(session)}")
            return 1

    print(f"status_code: {getattr(response, 'status_code', 'unknown')}")
    print(f"curl_cffi active: {is_curl_cffi_session(session)}")
    print("headers:")
    for key, value in _response_headers(response).items():
        if key.lower() in KEY_HEADERS:
            print(f"  {key}: {value}")
    print("body_preview:")
    print(_response_text(response)[:500])
    return 0 if int(getattr(response, "status_code", 0) or 0) < 400 else 1


def _warm_sos_session(session: Any) -> None:
    """Walk the public SOS CCR referer chain before a target diagnostic fetch."""

    try:
        polite_get(session, SOS_HOME_URL, referer=GOOGLE_REFERER)
        next_referer = SOS_HOME_URL
    except GeodeFetchError as exc:
        if exc.status_code != 403:
            raise
        polite_get(session, CCR_WELCOME_URL, referer=GOOGLE_REFERER)
        next_referer = CCR_WELCOME_URL
    polite_get(session, CCR_WELCOME_URL, referer=next_referer)
    polite_get(session, CCR_INDEX_URL, referer=CCR_WELCOME_URL)


def _referer_for_sos_url(url: str) -> str:
    """Return the most realistic referer for a SOS diagnostic target."""

    parsed = urlparse(url)
    if parsed.path.endswith("/CCR/DisplayRule.do"):
        return CCR_INDEX_URL
    if "GenerateRule" in parsed.path:
        return CCR_INDEX_URL
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
    parser.add_argument("url", help="URL to fetch.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the diagnostic CLI."""

    _configure_console_output()
    args = _build_parser().parse_args(argv)
    return diagnose(args.url)


def _configure_console_output() -> None:
    """Prefer UTF-8 output for diagnostic body previews."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
