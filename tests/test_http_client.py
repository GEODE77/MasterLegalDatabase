"""Tests for hardened Geode HTTP client helpers."""

from __future__ import annotations

import importlib

import pytest

from geode.net.http_client import (
    BROWSER_HEADERS,
    REQUESTS_ACCEPT_ENCODING,
    GeodeBlockedError,
    GeodeFetchError,
    GeodeHttpClient,
    GeodeHttpClientConfig,
    GeodeHttpResponse,
    GeodeHttpStatusError,
    GeodeInvalidContentError,
    build_session,
    polite_get,
)


class FakeResponse:
    """Minimal response object for retry tests."""

    def __init__(
        self,
        status_code: int,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Create a fake response."""

        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.headers = headers or {}


class FakeSession:
    """Fake session returning a programmed sequence of statuses."""

    def __init__(
        self,
        statuses: list[int],
        response_headers: list[dict[str, str] | None] | None = None,
    ) -> None:
        """Create a fake session."""

        self.statuses = list(statuses)
        self.response_headers = list(response_headers or [])
        self.calls: list[dict[str, object]] = []
        self.headers: dict[str, str] = {}

    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> FakeResponse:
        """Return the next fake response."""

        self.calls.append({"url": url, "headers": headers or {}, "timeout": timeout})
        status = self.statuses.pop(0)
        response_headers = self.response_headers.pop(0) if self.response_headers else None
        return FakeResponse(status, text=f"status={status}", headers=response_headers)


def test_build_session_falls_back_to_requests_with_browser_user_agent(monkeypatch) -> None:
    """When curl_cffi is missing, a requests session gets Chrome headers."""

    original_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        if name == "curl_cffi.requests":
            raise ImportError("curl_cffi unavailable")
        return original_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    session = build_session(impersonate=True)
    try:
        assert session.headers["User-Agent"] == BROWSER_HEADERS["User-Agent"]
        assert "Chrome/120.0.0.0" in session.headers["User-Agent"]
        assert session.headers["Accept-Encoding"] == REQUESTS_ACCEPT_ENCODING
    finally:
        session.close()


def test_polite_get_retries_403_then_succeeds(monkeypatch) -> None:
    """Retryable 403 responses are retried before returning success."""

    sleeps: list[float] = []
    monkeypatch.setattr("geode.net.http_client.random.uniform", lambda *_args: 0.0)
    monkeypatch.setattr("geode.net.http_client.time.sleep", sleeps.append)
    session = FakeSession([403, 403, 200])

    response = polite_get(session, "https://example.test/resource", max_retries=3, base_delay=1.0)

    assert response.status_code == 200
    assert len(session.calls) == 3
    assert sleeps == [1.0, 2.0]
    assert session.calls[0]["headers"]["User-Agent"] == BROWSER_HEADERS["User-Agent"]


def test_http_client_exposes_stable_response_and_hooks() -> None:
    """The reusable client applies headers and exposes hook-friendly response data."""

    response_events: list[GeodeHttpResponse] = []
    throttle_attempts: list[int] = []
    session = FakeSession([200], response_headers=[{"Content-Type": "text/html"}])
    client = GeodeHttpClient(
        session=session,
        config=GeodeHttpClientConfig(
            default_headers={"X-Geode": "test"},
            response_hook=response_events.append,
            throttle_hook=lambda request: throttle_attempts.append(request.attempt),
        ),
    )

    response = client.get(
        "https://example.test/page",
        referer="https://example.test/",
        if_none_match='"version-1"',
        allowed_content_types={"text/html"},
    )

    headers = session.calls[0]["headers"]
    assert response.status_code == 200
    assert response.raw_response.status_code == 200
    assert response.attempts == 1
    assert headers["User-Agent"] == BROWSER_HEADERS["User-Agent"]
    assert headers["X-Geode"] == "test"
    assert headers["Referer"] == "https://example.test/"
    assert headers["If-None-Match"] == '"version-1"'
    assert throttle_attempts == [1]
    assert response_events == [response]


def test_http_client_retry_hook_receives_retry_context(monkeypatch) -> None:
    """Retry hooks receive method, status, attempt, reason, and delay context."""

    sleeps: list[float] = []
    retry_events = []
    monkeypatch.setattr("geode.net.http_client.random.uniform", lambda *_args: 0.0)
    monkeypatch.setattr("geode.net.http_client.time.sleep", sleeps.append)
    session = FakeSession([503, 200])
    client = GeodeHttpClient(
        session=session,
        config=GeodeHttpClientConfig(retry_hook=retry_events.append),
    )

    client.get("https://example.test/retry", max_retries=2, base_delay=1.0)

    assert sleeps == [1.0]
    assert len(retry_events) == 1
    assert retry_events[0].method == "GET"
    assert retry_events[0].status_code == 503
    assert retry_events[0].attempt == 1
    assert retry_events[0].retry_reason == "status_503"
    assert retry_events[0].delay_seconds == 1.0


def test_http_client_raises_status_and_content_errors() -> None:
    """Status and content validation failures have explicit exception types."""

    with pytest.raises(GeodeHttpStatusError):
        GeodeHttpClient(session=FakeSession([404])).get("https://example.test/missing")

    with pytest.raises(GeodeInvalidContentError):
        GeodeHttpClient(
            session=FakeSession([200], response_headers=[{"Content-Type": "application/pdf"}])
        ).get(
            "https://example.test/file",
            allowed_content_types={"text/html"},
        )


def test_polite_get_raises_after_retry_exhaustion(monkeypatch) -> None:
    """Persistent retryable statuses raise GeodeFetchError after max attempts."""

    sleeps: list[float] = []
    monkeypatch.setattr("geode.net.http_client.random.uniform", lambda *_args: 0.0)
    monkeypatch.setattr("geode.net.http_client.time.sleep", sleeps.append)
    session = FakeSession([403, 403])

    with pytest.raises(GeodeFetchError) as exc_info:
        polite_get(session, "https://example.test/blocked", max_retries=2, base_delay=1.5)

    assert isinstance(exc_info.value, GeodeBlockedError)
    assert exc_info.value.status_code == 403
    assert exc_info.value.attempts == 2
    assert len(session.calls) == 2
    assert sleeps == [1.5]


def test_polite_get_backoff_includes_exponential_delay_and_jitter(monkeypatch) -> None:
    """Backoff delay follows exponential timing plus deterministic jitter."""

    sleeps: list[float] = []
    monkeypatch.setattr("geode.net.http_client.random.uniform", lambda *_args: 0.25)
    monkeypatch.setattr("geode.net.http_client.time.sleep", sleeps.append)
    session = FakeSession([503, 503, 200])

    polite_get(session, "https://example.test/retry", max_retries=3, base_delay=2.0)

    assert sleeps == [2.25, 4.25]


def test_polite_get_can_disable_retry_jitter(monkeypatch) -> None:
    """Retry jitter is configurable for deterministic downloader runs."""

    sleeps: list[float] = []
    monkeypatch.setattr("geode.net.http_client.random.uniform", lambda *_args: 99.0)
    monkeypatch.setattr("geode.net.http_client.time.sleep", sleeps.append)
    session = FakeSession([503, 200])

    polite_get(
        session,
        "https://example.test/retry",
        max_retries=2,
        base_delay=2.0,
        retry_jitter_ratio=0.0,
    )

    assert sleeps == [2.0]


def test_polite_get_passes_configured_timeout() -> None:
    """Configured request timeouts are passed to compatible sessions."""

    session = FakeSession([200])

    polite_get(session, "https://example.test/timeout", timeout_seconds=12.5)

    assert session.calls[0]["timeout"] == 12.5


def test_polite_get_respects_retry_after_header(monkeypatch) -> None:
    """429 Retry-After controls the next retry delay when it exceeds backoff."""

    sleeps: list[float] = []
    monkeypatch.setattr("geode.net.http_client.random.uniform", lambda *_args: 0.0)
    monkeypatch.setattr("geode.net.http_client.time.sleep", sleeps.append)
    session = FakeSession([429, 200], response_headers=[{"Retry-After": "7"}, None])

    polite_get(session, "https://example.test/rate-limited", max_retries=2, base_delay=1.0)

    assert sleeps == [7.0]


def test_polite_get_exposes_blocked_error_context(monkeypatch) -> None:
    """Persistent 403s surface a blocked-source error state."""

    monkeypatch.setattr("geode.net.http_client.random.uniform", lambda *_args: 0.0)
    monkeypatch.setattr("geode.net.http_client.time.sleep", lambda _delay: None)
    session = FakeSession([403])

    with pytest.raises(GeodeFetchError) as exc_info:
        polite_get(session, "https://example.test/blocked", max_retries=1)

    assert exc_info.value.is_blocked
    assert not exc_info.value.is_rate_limited
    assert "access denied or blocked" in str(exc_info.value)
