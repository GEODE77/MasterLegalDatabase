"""Canonical identity helpers for Colorado CCR acquisition."""

from __future__ import annotations

import hashlib
import re
from html import unescape as html_unescape
from urllib.parse import parse_qsl, unquote_plus, urlparse

CCR_CITATION_RE = re.compile(
    r"\b(?P<title>\d{1,2})\s*CCR\s+"
    r"(?P<chapter>[A-Za-z0-9.]+)-(?P<rule>[A-Za-z0-9_.-]+)\b",
    re.IGNORECASE,
)
CCR_CANONICAL_ID_RE = re.compile(
    r"\b(?P<title>\d{1,2})_CCR_"
    r"(?P<chapter>[A-Za-z0-9.]+)-(?P<rule>[A-Za-z0-9_.-]+)\b",
    re.IGNORECASE,
)


def canonical_ccr_number(*values: object) -> str | None:
    """Return a normalized CCR citation from the first value that contains one."""

    for value in values:
        for text in _candidate_texts(value):
            match = CCR_CITATION_RE.search(text)
            if match is None:
                match = CCR_CANONICAL_ID_RE.search(text)
            if match is None:
                continue
            return (
                f"{match.group('title')} CCR "
                f"{match.group('chapter')}-{match.group('rule')}"
            )
    return None


def canonical_ccr_id(
    ccr_number: object | None = None,
    *,
    source_page_url: object | None = None,
    document_url: object | None = None,
) -> str:
    """Return the stable Geode CCR item ID for source metadata.

    The preferred identity is the official CCR citation, for example
    ``5 CCR 1001-9`` -> ``5_CCR_1001-9``. Fallbacks are deterministic SOS
    identifiers and finally a short hash of source URL metadata.
    """

    citation = canonical_ccr_number(ccr_number, source_page_url, document_url)
    if citation is not None:
        return _id_from_citation(citation)
    rule_id = _query_value(source_page_url, "ruleId")
    if rule_id:
        return f"CCR_RULEID_{_safe_token(rule_id)}"
    rule_version_id = _query_value(document_url, "ruleVersionId")
    if rule_version_id:
        return f"CCR_RULEVERSION_{_safe_token(rule_version_id)}"
    source_key = _first_text(source_page_url, document_url, ccr_number)
    if source_key:
        digest = hashlib.sha256(
            _canonical_urlish(source_key).encode("utf-8")
        ).hexdigest()[:16]
        return f"CCR_URL_{digest}"
    return "CCR_UNKNOWN"


def is_canonical_ccr_number(value: object) -> bool:
    """Return whether a value contains an official-looking CCR citation."""

    return canonical_ccr_number(value) is not None


def _id_from_citation(ccr_number: str) -> str:
    """Return a filesystem-safe ID from a normalized CCR citation."""

    return re.sub(r"[^A-Za-z0-9_-]+", "_", ccr_number.strip()).strip("_")


def _candidate_texts(value: object) -> list[str]:
    """Return decoded text candidates from raw text or URL query values."""

    text = _first_text(value)
    if not text:
        return []
    decoded = _canonical_urlish(text)
    candidates = [decoded]
    parsed = urlparse(decoded)
    if parsed.query:
        for key, item in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() in {"rule", "filename", "seriesnum", "ccrnumber"}:
                candidates.append(_canonical_urlish(item))
    return candidates


def _query_value(value: object, key: str) -> str | None:
    """Return one decoded query parameter value from a URL-like object."""

    text = _first_text(value)
    if not text:
        return None
    parsed = urlparse(_canonical_urlish(text))
    wanted = key.casefold()
    for item_key, item_value in parse_qsl(parsed.query, keep_blank_values=True):
        if item_key.casefold() == wanted and item_value.strip():
            return item_value.strip()
    return None


def _first_text(*values: object) -> str | None:
    """Return the first non-empty string-like value."""

    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _canonical_urlish(value: str) -> str:
    """Decode HTML and URL escapes repeatedly enough for SOS persisted URLs."""

    text = value
    for _ in range(3):
        decoded = unquote_plus(html_unescape(text))
        if decoded == text:
            return decoded
        text = decoded
    return text


def _safe_token(value: str) -> str:
    """Return a deterministic token for fallback IDs."""

    return re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_") or "unknown"
