"""Hardened HTTP helpers for official public-source scraping."""

from __future__ import annotations

import importlib
import logging
import random
import time
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)

RETRY_STATUSES = {403, 429, 502, 503, 504}
DEFAULT_TIMEOUT_SECONDS = 30.0

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
        "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Google Chrome";v="120", "Chromium";v="120", "Not:A-Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}


class GeodeFetchError(RuntimeError):
    """Raised when a polite fetch cannot get a usable response."""

    def __init__(
        self,
        message: str,
        *,
        url: str,
        status_code: int | None = None,
        attempts: int = 0,
        last_response: Any | None = None,
    ) -> None:
        """Create a fetch error with status and response context."""

        super().__init__(message)
        self.url = url
        self.status_code = status_code
        self.attempts = attempts
        self.last_response = last_response


def build_session(impersonate: bool = True) -> Any:
    """Build a cookie-persisting session with browser-like defaults.

    Args:
        impersonate: Whether to use ``curl_cffi`` Chrome impersonation when
            available.

    Returns:
        A ``curl_cffi.requests.Session`` when installed, otherwise a standard
        ``requests.Session`` with browser headers applied.
    """

    if impersonate:
        try:
            curl_requests = importlib.import_module("curl_cffi.requests")
        except ImportError:
            curl_requests = None
        if curl_requests is not None:
            session = curl_requests.Session(impersonate="chrome120")
            _apply_headers(session)
            return session

    session = requests.Session()
    _apply_headers(session)
    return session


def polite_get(
    session: Any,
    url: str,
    referer: str | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
) -> Any:
    """GET a URL with browser headers, cookies, and retry backoff.

    Args:
        session: Cookie-persisting HTTP session.
        url: Target URL.
        referer: Optional referer header for this request.
        max_retries: Total attempts before raising ``GeodeFetchError``.
        base_delay: Base delay in seconds for exponential backoff.

    Returns:
        HTTP response object.

    Raises:
        GeodeFetchError: If retryable or failing statuses persist.
    """

    if max_retries < 1:
        raise ValueError("max_retries must be at least 1")

    headers = dict(BROWSER_HEADERS)
    if referer:
        headers["Referer"] = referer

    last_response: Any | None = None
    last_error: Exception | None = None
    last_status: int | None = None

    for attempt in range(1, max_retries + 1):
        delay = 0.0
        try:
            response = _session_get(session, url, headers)
            last_response = response
            last_status = _status_code(response)
            should_retry = last_status in RETRY_STATUSES
            LOGGER.info(
                "GET %s attempt %s/%s status=%s delay=0.00",
                url,
                attempt,
                max_retries,
                last_status,
            )
            if not should_retry and last_status is not None and last_status >= 400:
                raise GeodeFetchError(
                    f"GET {url} failed with status {last_status}",
                    url=url,
                    status_code=last_status,
                    attempts=attempt,
                    last_response=response,
                )
            if not should_retry:
                return response
        except GeodeFetchError:
            raise
        except Exception as exc:
            last_error = exc
            last_status = None
            should_retry = True
            LOGGER.warning(
                "GET %s attempt %s/%s status=%s delay=0.00",
                url,
                attempt,
                max_retries,
                type(exc).__name__,
            )

        if attempt >= max_retries:
            break

        delay = _retry_delay(attempt, base_delay)
        LOGGER.warning(
            "GET %s attempt %s/%s status=%s delay=%.2f",
            url,
            attempt,
            max_retries,
            last_status if last_status is not None else type(last_error).__name__,
            delay,
        )
        time.sleep(delay)

    status_message = (
        f"status {last_status}" if last_status is not None else f"error {last_error}"
    )
    raise GeodeFetchError(
        f"GET {url} failed after {max_retries} attempts ({status_message})",
        url=url,
        status_code=last_status,
        attempts=max_retries,
        last_response=last_response,
    )


def is_curl_cffi_session(session: Any) -> bool:
    """Return whether a session appears to be backed by ``curl_cffi``."""

    return session.__class__.__module__.startswith("curl_cffi")


def _apply_headers(session: Any) -> None:
    """Apply browser headers when a session exposes a headers mapping."""

    headers = getattr(session, "headers", None)
    if headers is not None and hasattr(headers, "update"):
        headers.update(BROWSER_HEADERS)


def _session_get(session: Any, url: str, headers: dict[str, str]) -> Any:
    """Call a session's GET while tolerating simple fake clients in tests."""

    try:
        return session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)
    except TypeError:
        try:
            return session.get(url, headers=headers)
        except TypeError:
            return session.get(url)


def _status_code(response: Any) -> int | None:
    """Extract an integer status code from a response object."""

    status = getattr(response, "status_code", None)
    if status is None:
        return None
    try:
        return int(status)
    except (TypeError, ValueError):
        return None


def _retry_delay(attempt: int, base_delay: float) -> float:
    """Calculate exponential backoff with a small jitter component."""

    jitter = random.uniform(0.0, max(base_delay, 0.0) * 0.25)
    return max(base_delay, 0.0) * (2 ** (attempt - 1)) + jitter
