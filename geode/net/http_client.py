"""Reusable HTTP client helpers for official public-source scraping."""

from __future__ import annotations

import importlib
import logging
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({403, 429, 502, 503, 504})
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRY_DELAY_SECONDS = 60.0
REQUESTS_ACCEPT_ENCODING = "gzip, deflate"
DEFAULT_RETRY_JITTER_RATIO = 0.25

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


ThrottleHook = Callable[["GeodeHttpRequest"], None]
RetryHook = Callable[["GeodeHttpAttempt"], None]
ResponseHook = Callable[["GeodeHttpResponse"], None]
ContentValidator = Callable[["GeodeHttpResponse"], None]


@dataclass(frozen=True)
class GeodeHttpClientConfig:
    """Configuration for a reusable Geode HTTP client."""

    default_headers: Mapping[str, str] = field(default_factory=dict)
    use_browser_headers: bool = True
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = 4
    base_delay: float = 2.0
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS
    retry_jitter_ratio: float = DEFAULT_RETRY_JITTER_RATIO
    retry_statuses: frozenset[int] = RETRY_STATUSES
    respect_retry_after: bool = True
    throttle_delay_seconds: float = 0.0
    throttle_jitter_seconds: float = 0.0
    throttle_hook: ThrottleHook | None = None
    retry_hook: RetryHook | None = None
    response_hook: ResponseHook | None = None
    log_level: int = logging.DEBUG


@dataclass(frozen=True)
class GeodeHttpRequest:
    """One outbound HTTP request attempt."""

    method: str
    url: str
    headers: Mapping[str, str]
    timeout_seconds: float
    attempt: int
    max_retries: int


@dataclass(frozen=True)
class GeodeHttpResponse:
    """Stable response facade returned by ``GeodeHttpClient``."""

    method: str
    requested_url: str
    url: str
    status_code: int | None
    headers: Mapping[str, str]
    content: bytes
    text: str
    elapsed_seconds: float
    attempts: int
    raw_response: Any


@dataclass(frozen=True)
class GeodeHttpAttempt:
    """Retry telemetry for one failed or retryable request attempt."""

    method: str
    url: str
    attempt: int
    max_retries: int
    status_code: int | None
    elapsed_seconds: float
    retry_reason: str
    delay_seconds: float
    exception: Exception | None = None


@dataclass(frozen=True)
class GeodeThrottleConfig:
    """Configuration for a reusable request throttle."""

    delay_seconds: float = 0.0
    jitter_seconds: float = 0.0
    label: str = "http"


class GeodeThrottle:
    """Reusable throttle with optional jitter and injectable sleep/random functions."""

    def __init__(
        self,
        config: GeodeThrottleConfig | None = None,
        *,
        sleep_func: Callable[[float], None] = time.sleep,
        random_func: Callable[[float, float], float] = random.uniform,
    ) -> None:
        """Create a throttle.

        Args:
            config: Base delay, jitter range, and label for logs.
            sleep_func: Injectable sleep function for deterministic tests.
            random_func: Injectable uniform random function for deterministic tests.
        """

        self.config = config or GeodeThrottleConfig()
        _validate_throttle_options(self.config.delay_seconds, self.config.jitter_seconds)
        self._sleep = sleep_func
        self._random = random_func

    def delay(self) -> float:
        """Return the next throttle delay in seconds."""

        delay = self.config.delay_seconds
        if self.config.jitter_seconds > 0:
            delay += self._random(0.0, self.config.jitter_seconds)
        return delay

    def wait(self, *, reason: str = "") -> float:
        """Sleep for the next throttle interval and return the applied delay."""

        delay = self.delay()
        if delay <= 0:
            return 0.0
        LOGGER.debug(
            "http_throttle label=%s reason=%s delay_seconds=%.3f",
            self.config.label,
            reason,
            delay,
            extra={
                "http_throttle_label": self.config.label,
                "http_throttle_reason": reason,
                "http_throttle_delay_seconds": delay,
            },
        )
        self._sleep(delay)
        return delay


class GeodeHttpError(RuntimeError):
    """Base exception for Geode HTTP failures."""

    def __init__(
        self,
        message: str,
        *,
        method: str = "GET",
        url: str,
        status_code: int | None = None,
        attempts: int = 0,
        response: Any | None = None,
        retry_reason: str | None = None,
    ) -> None:
        """Create an HTTP error with request and response context."""

        super().__init__(message)
        self.method = method
        self.url = url
        self.status_code = status_code
        self.attempts = attempts
        self.last_response = response
        self.retry_reason = retry_reason

    @property
    def is_blocked(self) -> bool:
        """Return whether the failure looks like source-side access denial."""

        return self.status_code == 403

    @property
    def is_rate_limited(self) -> bool:
        """Return whether the failure looks like source-side rate limiting."""

        return self.status_code == 429


class GeodeFetchError(GeodeHttpError):
    """Compatibility base for fetch failures raised by older helpers."""


class GeodeHttpStatusError(GeodeFetchError):
    """Raised when a response has an unacceptable HTTP status."""


class GeodeRetryExhaustedError(GeodeFetchError):
    """Raised when retryable responses or transport failures persist."""


class GeodeBlockedError(GeodeRetryExhaustedError):
    """Raised when persistent failures look like blocking or anti-bot denial."""


class GeodeInvalidContentError(GeodeFetchError):
    """Raised when a response body or content type does not match expectations."""


class GeodeHttpClient:
    """Reusable request client with retries, hooks, and response normalization."""

    def __init__(
        self,
        session: Any | None = None,
        config: GeodeHttpClientConfig | None = None,
    ) -> None:
        """Create a client around a persistent session.

        Args:
            session: Optional session-like object. If omitted, ``build_session`` is used.
            config: HTTP retry, timeout, header, logging, and hook configuration.
        """

        self.config = config or GeodeHttpClientConfig()
        self.session = session if session is not None else build_session()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        referer: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        base_delay: float | None = None,
        max_retry_delay_seconds: float | None = None,
        retry_jitter_ratio: float | None = None,
        retry_statuses: set[int] | frozenset[int] | None = None,
        respect_retry_after: bool | None = None,
        expected_statuses: set[int] | frozenset[int] | None = None,
        allowed_content_types: set[str] | frozenset[str] | None = None,
        require_content: bool = False,
        content_validator: ContentValidator | None = None,
        if_none_match: str | None = None,
        if_modified_since: str | None = None,
    ) -> GeodeHttpResponse:
        """Send a request and return a normalized response facade.

        Args:
            method: HTTP method.
            url: Target URL.
            headers: Optional per-request headers.
            referer: Optional referer header.
            timeout_seconds: Per-request timeout override.
            max_retries: Attempt count override.
            base_delay: Exponential backoff base delay override.
            max_retry_delay_seconds: Maximum retry sleep override.
            retry_jitter_ratio: Maximum retry jitter as a ratio of ``base_delay``.
            retry_statuses: Status codes that should be retried.
            respect_retry_after: Whether to honor ``Retry-After``.
            expected_statuses: Optional exact acceptable status set.
            allowed_content_types: Optional allowed response content types.
            require_content: Whether an empty response body should fail.
            content_validator: Optional caller-supplied response validator.
            if_none_match: Optional ETag value for conditional GET.
            if_modified_since: Optional Last-Modified value for conditional GET.

        Returns:
            Normalized HTTP response with stable attributes.

        Raises:
            GeodeHttpStatusError: If a non-retryable status is unacceptable.
            GeodeRetryExhaustedError: If retryable failures persist.
            GeodeBlockedError: If retry exhaustion looks like access blocking.
            GeodeInvalidContentError: If content validation fails.
        """

        method_name = method.upper()
        timeout = timeout_seconds if timeout_seconds is not None else self.config.timeout_seconds
        retries = max_retries if max_retries is not None else self.config.max_retries
        backoff = base_delay if base_delay is not None else self.config.base_delay
        max_delay = (
            max_retry_delay_seconds
            if max_retry_delay_seconds is not None
            else self.config.max_retry_delay_seconds
        )
        jitter_ratio = (
            retry_jitter_ratio
            if retry_jitter_ratio is not None
            else self.config.retry_jitter_ratio
        )
        retryable_statuses = retry_statuses or self.config.retry_statuses
        honor_retry_after = (
            respect_retry_after
            if respect_retry_after is not None
            else self.config.respect_retry_after
        )
        _validate_retry_options(retries, backoff, timeout, max_delay, jitter_ratio)

        request_headers = self._request_headers(
            headers=headers,
            referer=referer,
            if_none_match=if_none_match,
            if_modified_since=if_modified_since,
        )

        last_response: GeodeHttpResponse | None = None
        last_error: Exception | None = None
        last_status: int | None = None

        for attempt in range(1, retries + 1):
            request_info = GeodeHttpRequest(
                method=method_name,
                url=url,
                headers=request_headers,
                timeout_seconds=timeout,
                attempt=attempt,
                max_retries=retries,
            )
            self._throttle(request_info)
            started = time.perf_counter()
            try:
                raw_response = self._send(method_name, url, request_headers, timeout)
            except Exception as exc:
                elapsed = time.perf_counter() - started
                last_error = exc
                last_status = None
                retry_reason = type(exc).__name__
                self._log_attempt(
                    method_name,
                    url,
                    status_code=None,
                    attempt=attempt,
                    max_retries=retries,
                    elapsed_seconds=elapsed,
                    retry_reason=retry_reason,
                )
                if attempt >= retries:
                    raise self._retry_exhausted(
                        method_name,
                        url,
                        retries,
                        None,
                        None,
                        retry_reason,
                        exc,
                    ) from exc
                self._sleep_before_retry(
                    method_name,
                    url,
                    attempt,
                    retries,
                    None,
                    elapsed,
                    retry_reason,
                    backoff,
                    max_delay,
                    jitter_ratio,
                    None,
                )
                continue

            elapsed = time.perf_counter() - started
            response = _build_response(method_name, url, raw_response, elapsed, attempt)
            last_response = response
            last_status = response.status_code
            retry_reason = _retry_reason(response.status_code, retryable_statuses)
            self._log_attempt(
                method_name,
                url,
                status_code=response.status_code,
                attempt=attempt,
                max_retries=retries,
                elapsed_seconds=elapsed,
                retry_reason=retry_reason,
            )
            if self.config.response_hook is not None:
                self.config.response_hook(response)

            if retry_reason is not None:
                if attempt >= retries:
                    raise self._retry_exhausted(
                        method_name,
                        url,
                        retries,
                        response.status_code,
                        response,
                        retry_reason,
                        None,
                    )
                retry_after = (
                    _retry_after_delay(response)
                    if honor_retry_after
                    else None
                )
                self._sleep_before_retry(
                    method_name,
                    url,
                    attempt,
                    retries,
                    response.status_code,
                    elapsed,
                    retry_reason,
                    backoff,
                    max_delay,
                    jitter_ratio,
                    retry_after,
                )
                continue

            _validate_status(method_name, url, response, attempt, expected_statuses)
            _validate_content(
                method_name,
                url,
                response,
                allowed_content_types,
                require_content,
                content_validator,
            )
            return response

        status_message = (
            f"status {last_status}" if last_status is not None else f"error {last_error}"
        )
        raise self._retry_exhausted(
            method_name,
            url,
            retries,
            last_status,
            last_response,
            status_message,
            last_error,
        )

    def get(self, url: str, **kwargs: Any) -> GeodeHttpResponse:
        """Send a GET request."""

        return self.request("GET", url, **kwargs)

    def close(self) -> None:
        """Close the wrapped session if it exposes a close method."""

        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _request_headers(
        self,
        *,
        headers: Mapping[str, str] | None,
        referer: str | None,
        if_none_match: str | None,
        if_modified_since: str | None,
    ) -> dict[str, str]:
        """Build request headers from defaults and per-request overrides."""

        request_headers: dict[str, str] = {}
        if self.config.use_browser_headers:
            request_headers.update(_browser_headers_for_session(self.session))
        request_headers.update(
            {
                str(key): str(value)
                for key, value in self.config.default_headers.items()
            }
        )
        if headers:
            request_headers.update({str(key): str(value) for key, value in headers.items()})
        if referer:
            request_headers["Referer"] = referer
        if if_none_match:
            request_headers["If-None-Match"] = if_none_match
        if if_modified_since:
            request_headers["If-Modified-Since"] = if_modified_since
        return request_headers

    def _throttle(self, request: GeodeHttpRequest) -> None:
        """Apply configured pre-request throttle behavior."""

        if self.config.throttle_hook is not None:
            self.config.throttle_hook(request)
        if (
            self.config.throttle_delay_seconds > 0
            or self.config.throttle_jitter_seconds > 0
        ):
            GeodeThrottle(
                GeodeThrottleConfig(
                    delay_seconds=self.config.throttle_delay_seconds,
                    jitter_seconds=self.config.throttle_jitter_seconds,
                    label="http_client",
                )
            ).wait(reason=f"{request.method} {request.url}")

    def _send(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Any:
        """Execute one HTTP request against the wrapped session."""

        request = getattr(self.session, "request", None)
        if callable(request):
            try:
                return request(method, url, headers=dict(headers), timeout=timeout_seconds)
            except TypeError:
                try:
                    return request(method, url, headers=dict(headers))
                except TypeError:
                    return request(method, url)

        method_call = getattr(self.session, method.lower(), None)
        if not callable(method_call):
            raise TypeError(f"session does not support HTTP method {method}")
        try:
            return method_call(url, headers=dict(headers), timeout=timeout_seconds)
        except TypeError:
            try:
                return method_call(url, headers=dict(headers))
            except TypeError:
                return method_call(url)

    def _sleep_before_retry(
        self,
        method: str,
        url: str,
        attempt: int,
        max_retries: int,
        status_code: int | None,
        elapsed_seconds: float,
        retry_reason: str,
        base_delay: float,
        max_delay: float | None,
        jitter_ratio: float,
        retry_after_delay: float | None,
    ) -> None:
        """Run retry hooks, log retry context, and sleep before the next attempt."""

        delay = _retry_delay(
            attempt,
            base_delay,
            retry_after_delay=retry_after_delay,
            max_delay_seconds=max_delay,
            jitter_ratio=jitter_ratio,
        )
        retry_attempt = GeodeHttpAttempt(
            method=method,
            url=url,
            attempt=attempt,
            max_retries=max_retries,
            status_code=status_code,
            elapsed_seconds=elapsed_seconds,
            retry_reason=retry_reason,
            delay_seconds=delay,
        )
        if self.config.retry_hook is not None:
            self.config.retry_hook(retry_attempt)
        LOGGER.warning(
            "http_retry method=%s url=%s status_code=%s attempt=%s/%s "
            "elapsed_seconds=%.3f retry_reason=%s delay_seconds=%.2f",
            method,
            url,
            status_code,
            attempt,
            max_retries,
            elapsed_seconds,
            retry_reason,
            delay,
            extra={
                "http_method": method,
                "http_url": url,
                "http_status_code": status_code,
                "http_attempt": attempt,
                "http_max_retries": max_retries,
                "http_elapsed_seconds": elapsed_seconds,
                "http_retry_reason": retry_reason,
                "http_retry_delay_seconds": delay,
            },
        )
        time.sleep(delay)

    def _log_attempt(
        self,
        method: str,
        url: str,
        *,
        status_code: int | None,
        attempt: int,
        max_retries: int,
        elapsed_seconds: float,
        retry_reason: str | None,
    ) -> None:
        """Log structured request attempt context."""

        LOGGER.log(
            self.config.log_level,
            "http_request method=%s url=%s status_code=%s attempt=%s/%s "
            "elapsed_seconds=%.3f retry_reason=%s",
            method,
            url,
            status_code,
            attempt,
            max_retries,
            elapsed_seconds,
            retry_reason or "",
            extra={
                "http_method": method,
                "http_url": url,
                "http_status_code": status_code,
                "http_attempt": attempt,
                "http_max_retries": max_retries,
                "http_elapsed_seconds": elapsed_seconds,
                "http_retry_reason": retry_reason,
            },
        )

    def _retry_exhausted(
        self,
        method: str,
        url: str,
        attempts: int,
        status_code: int | None,
        response: GeodeHttpResponse | None,
        retry_reason: str,
        error: Exception | None,
    ) -> GeodeRetryExhaustedError:
        """Build the appropriate retry exhaustion exception."""

        status_message = (
            f"status {status_code}" if status_code is not None else f"error {error}"
        )
        message = (
            f"{method} {url} failed after {attempts} attempts "
            f"({status_message}; {_status_context(status_code)})"
        )
        error_class: type[GeodeRetryExhaustedError]
        error_class = GeodeBlockedError if status_code == 403 else GeodeRetryExhaustedError
        return error_class(
            message,
            method=method,
            url=url,
            status_code=status_code,
            attempts=attempts,
            response=response,
            retry_reason=retry_reason,
        )


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
    retry_jitter_ratio: float = DEFAULT_RETRY_JITTER_RATIO,
    retry_statuses: set[int] | None = None,
    respect_retry_after: bool = True,
) -> Any:
    """GET a URL with browser headers, cookies, and retry backoff.

    This legacy helper is backed by ``GeodeHttpClient`` and returns the wrapped
    session's raw response for compatibility with older connectors.
    """

    client = (
        session
        if isinstance(session, GeodeHttpClient)
        else GeodeHttpClient(
            session=session,
            config=GeodeHttpClientConfig(
                max_retries=max_retries,
                base_delay=base_delay,
                timeout_seconds=timeout_seconds,
                max_retry_delay_seconds=max_retry_delay_seconds,
                retry_jitter_ratio=retry_jitter_ratio,
                retry_statuses=frozenset(retry_statuses or RETRY_STATUSES),
                respect_retry_after=respect_retry_after,
            ),
        )
    )
    response = client.get(
        url,
        referer=referer,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
        retry_statuses=frozenset(retry_statuses or RETRY_STATUSES),
        respect_retry_after=respect_retry_after,
    )
    return response.raw_response


def is_curl_cffi_session(session: Any) -> bool:
    """Return whether a session appears to be backed by ``curl_cffi``."""

    return session.__class__.__module__.startswith("curl_cffi")


def _validate_retry_options(
    max_retries: int,
    base_delay: float,
    timeout_seconds: float,
    max_retry_delay_seconds: float | None,
    retry_jitter_ratio: float,
) -> None:
    """Validate retry and timeout options."""

    if max_retries < 1:
        raise ValueError("max_retries must be at least 1")
    if base_delay < 0:
        raise ValueError("base_delay cannot be negative")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than 0")
    if max_retry_delay_seconds is not None and max_retry_delay_seconds <= 0:
        raise ValueError("max_retry_delay_seconds must be greater than 0")
    if retry_jitter_ratio < 0:
        raise ValueError("retry_jitter_ratio cannot be negative")


def _validate_throttle_options(delay_seconds: float, jitter_seconds: float) -> None:
    """Validate throttle delay options."""

    if delay_seconds < 0:
        raise ValueError("delay_seconds cannot be negative")
    if jitter_seconds < 0:
        raise ValueError("jitter_seconds cannot be negative")


def _build_response(
    method: str,
    requested_url: str,
    raw_response: Any,
    elapsed_seconds: float,
    attempts: int,
) -> GeodeHttpResponse:
    """Build a stable response facade from a session response object."""

    content = _response_content(raw_response)
    return GeodeHttpResponse(
        method=method,
        requested_url=requested_url,
        url=str(getattr(raw_response, "url", requested_url)),
        status_code=_status_code(raw_response),
        headers=_response_headers(raw_response),
        content=content,
        text=_response_text(raw_response, content),
        elapsed_seconds=elapsed_seconds,
        attempts=attempts,
        raw_response=raw_response,
    )


def _validate_status(
    method: str,
    url: str,
    response: GeodeHttpResponse,
    attempts: int,
    expected_statuses: set[int] | frozenset[int] | None,
) -> None:
    """Raise when a response status is not acceptable."""

    status_code = response.status_code
    if expected_statuses is not None and status_code not in expected_statuses:
        raise GeodeHttpStatusError(
            f"{method} {url} returned status {status_code}; expected "
            f"{sorted(expected_statuses)}",
            method=method,
            url=url,
            status_code=status_code,
            attempts=attempts,
            response=response,
        )
    if expected_statuses is None and status_code is not None and status_code >= 400:
        raise GeodeHttpStatusError(
            f"{method} {url} failed with status {status_code} "
            f"({_status_context(status_code)})",
            method=method,
            url=url,
            status_code=status_code,
            attempts=attempts,
            response=response,
        )


def _validate_content(
    method: str,
    url: str,
    response: GeodeHttpResponse,
    allowed_content_types: set[str] | frozenset[str] | None,
    require_content: bool,
    content_validator: ContentValidator | None,
) -> None:
    """Raise when response content does not match caller expectations."""

    if require_content and not response.content:
        raise GeodeInvalidContentError(
            f"{method} {url} returned an empty response body",
            method=method,
            url=url,
            status_code=response.status_code,
            attempts=response.attempts,
            response=response,
        )
    if allowed_content_types is not None:
        content_type = _header_value(response.headers, "Content-Type") or ""
        if not _content_type_matches(content_type, allowed_content_types):
            raise GeodeInvalidContentError(
                f"{method} {url} returned content-type {content_type!r}; "
                f"expected one of {sorted(allowed_content_types)}",
                method=method,
                url=url,
                status_code=response.status_code,
                attempts=response.attempts,
                response=response,
            )
    if content_validator is not None:
        try:
            content_validator(response)
        except GeodeInvalidContentError:
            raise
        except Exception as exc:
            raise GeodeInvalidContentError(
                f"{method} {url} failed content validation: {exc}",
                method=method,
                url=url,
                status_code=response.status_code,
                attempts=response.attempts,
                response=response,
            ) from exc


def _content_type_matches(
    content_type: str,
    allowed_content_types: set[str] | frozenset[str],
) -> bool:
    """Return whether a response content type matches an allowed type."""

    normalized = content_type.split(";", 1)[0].strip().casefold()
    return any(normalized == item.casefold() for item in allowed_content_types)


def _response_headers(response: Any) -> dict[str, str]:
    """Return response headers as a plain string dictionary."""

    headers = getattr(response, "headers", None)
    if not headers or not hasattr(headers, "items"):
        return {}
    return {str(key): str(value) for key, value in headers.items()}


def _response_content(response: Any) -> bytes:
    """Return response content as bytes."""

    content = getattr(response, "content", b"")
    if isinstance(content, bytes):
        return content
    if isinstance(content, str):
        return content.encode("utf-8")
    return bytes(content or b"")


def _response_text(response: Any, content: bytes) -> str:
    """Return response text as a string."""

    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    return content.decode("utf-8", errors="replace")


def _apply_headers(session: Any) -> None:
    """Apply browser headers when a session exposes a headers mapping."""

    headers = getattr(session, "headers", None)
    if headers is not None and hasattr(headers, "update"):
        headers.update(_browser_headers_for_session(session))


def _browser_headers_for_session(session: Any) -> dict[str, str]:
    """Return browser-like headers compatible with the selected HTTP stack."""

    headers = dict(BROWSER_HEADERS)
    if not is_curl_cffi_session(session):
        headers["Accept-Encoding"] = REQUESTS_ACCEPT_ENCODING
    return headers


def _session_get(
    session: Any,
    url: str,
    headers: dict[str, str],
    timeout_seconds: float,
) -> Any:
    """Call a session's GET while tolerating simple fake clients in tests."""

    return GeodeHttpClient(session=session).get(
        url,
        headers=headers,
        timeout_seconds=timeout_seconds,
    ).raw_response


def _status_code(response: Any) -> int | None:
    """Extract an integer status code from a response object."""

    status = getattr(response, "status_code", None)
    if status is None:
        return None
    try:
        return int(status)
    except (TypeError, ValueError):
        return None


def _retry_reason(
    status_code: int | None,
    retry_statuses: set[int] | frozenset[int],
) -> str | None:
    """Return a retry reason for a status code, if retryable."""

    if status_code in retry_statuses:
        return f"status_{status_code}"
    return None


def _retry_delay(
    attempt: int,
    base_delay: float,
    retry_after_delay: float | None = None,
    max_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    jitter_ratio: float = DEFAULT_RETRY_JITTER_RATIO,
) -> float:
    """Calculate exponential backoff with a small jitter component."""

    jitter = 0.0
    if jitter_ratio > 0 and base_delay > 0:
        jitter = random.uniform(0.0, base_delay * jitter_ratio)
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
