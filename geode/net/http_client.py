"""Hardened HTTP helpers for official public-source scraping."""

from __future__ import annotations

import importlib
import logging
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)

RETRY_STATUSES = {403, 429, 502, 503, 504}
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRY_DELAY_SECONDS = 60.0

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

    @property
    def is_blocked(self) -> bool:
        """Return whether the failure looks like source-side access denial."""

        return self.status_code == 403

    @property
    def is_rate_limited(self) -> bool:
        """Return whether the failure looks like source-side rate limiting."""

        return self.status_code == 429


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
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_statuses: set[int] | None = None,
    respect_retry_after: bool = True,
) -> Any:
    """GET a URL with browser headers, cookies, and retry backoff.

    Args:
        session: Cookie-persisting HTTP session.
        url: Target URL.
        referer: Optional referer header for this request.
        max_retries: Total attempts before raising ``GeodeFetchError``.
        base_delay: Base delay in seconds for exponential backoff.
        timeout_seconds: Per-request timeout.
        max_retry_delay_seconds: Optional cap for any one retry sleep.
        retry_statuses: HTTP statuses that should be retried.
        respect_retry_after: Whether to honor server ``Retry-After`` headers.

    Returns:
        HTTP response object.

    Raises:
        GeodeFetchError: If retryable or failing statuses persist.
    """

    if max_retries < 1:
        raise ValueError("max_retries must be at least 1")
    if base_delay < 0:
        raise ValueError("base_delay cannot be negative")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than 0")
    if max_retry_delay_seconds is not None and max_retry_delay_seconds <= 0:
        raise ValueError("max_retry_delay_seconds must be greater than 0")

    headers = dict(BROWSER_HEADERS)
    if referer:
        headers["Referer"] = referer
    retryable_statuses = retry_statuses or RETRY_STATUSES

    last_response: Any | None = None
    last_error: Exception | None = None
    last_status: int | None = None

    for attempt in range(1, max_retries + 1):
        delay = 0.0
        try:
            response = _session_get(session, url, headers, timeout_seconds)
            last_response = response
            last_status = _status_code(response)
            should_retry = last_status in retryable_statuses
            LOGGER.debug(
                "GET %s attempt %s/%s status=%s delay=0.00",
                url,
                attempt,
                max_retries,
                last_status,
            )
            if not should_retry and last_status is not None and last_status >= 400:
                raise GeodeFetchError(
                    f"GET {url} failed with status {last_status} "
                    f"({_status_context(last_status)})",
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

        retry_after = (
            _retry_after_delay(last_response)
            if respect_retry_after and last_response is not None
            else None
        )
        delay = _retry_delay(
            attempt,
            base_delay,
            retry_after_delay=retry_after,
            max_delay_seconds=max_retry_delay_seconds,
        )
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
        f"GET {url} failed after {max_retries} attempts "
        f"({status_message}; {_status_context(last_status)})",
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


def _session_get(
    session: Any,
    url: str,
    headers: dict[str, str],
    timeout_seconds: float,
) -> Any:
    """Call a session's GET while tolerating simple fake clients in tests."""

    try:
        return session.get(url, headers=headers, timeout=timeout_seconds)
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


def _retry_delay(
    attempt: int,
    base_delay: float,
    retry_after_delay: float | None = None,
    max_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> float:
    """Calculate exponential backoff with a small jitter component."""

    jitter = random.uniform(0.0, max(base_delay, 0.0) * 0.25)
    delay = max(base_delay, 0.0) * (2 ** (attempt - 1)) + jitter
    if retry_after_delay is not None:
        delay = max(delay, retry_after_delay)
    if max_delay_seconds is not None:
        delay = min(delay, max_delay_seconds)
    return delay


def _retry_after_delay(response: Any) -> float | None:
    """Parse a Retry-After response header into seconds."""

    headers = getattr(response, "headers", None)
    if not headers:
        return None
    value = _header_value(headers, "Retry-After")
    if value is None:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        pass
    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max((retry_at - datetime.now(timezone.utc)).total_seconds(), 0.0)


def _header_value(headers: Any, name: str) -> str | None:
    """Return a header value from regular or case-insensitive mappings."""

    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(name)
        if value is None:
            value = getter(name.lower())
        if value is not None:
            return str(value)
    for key, value in getattr(headers, "items", lambda: [])():
        if str(key).casefold() == name.casefold():
            return str(value)
    return None


def _status_context(status_code: int | None) -> str:
    """Return a short explanation for common source-side fetch failures."""

    if status_code == 403:
        return "access denied or blocked by source"
    if status_code == 429:
        return "rate limited by source"
    if status_code is not None and status_code >= 500:
        return "transient source/server failure"
    if status_code is not None and status_code >= 400:
        return "non-retryable source/client failure"
    return "transport failure"
