"""Check every registered official source for live reachability and markers."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import urlencode, urlparse

from pydantic import BaseModel, ConfigDict, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.net.http_client import GeodeHttpClient, GeodeHttpClientConfig
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, atomic_write_text, load_json

REPORT_PATH = Path(CONTROL_PLANE_DIR) / "OFFICIAL_SOURCE_CHECK_REPORT.json"
ROWS_PATH = Path(CONTROL_PLANE_DIR) / "OFFICIAL_SOURCE_CHECKS.jsonl"
DOCS_REPORT_DIR = Path("docs") / "audits"

PASS = "pass"
WARN = "warn"
FAIL = "fail"

REACHABLE = "reachable"
NEWER_MARKER = "newer_marker_seen"
NO_NEWER_MARKER = "no_newer_marker_seen"
BLOCKED = "blocked_or_challenged"
FAILED = "failed"
MANUAL_ONLY = "manual_only"
CONFIG_REQUIRED = "configuration_required"

TAG_RE = re.compile(r"<[^>]+>")
ISO_DATE_RE = re.compile(r"\b(20\d{2})[-_/](\d{1,2})[-_/](\d{1,2})\b")
US_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b")
MONTH_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{1,2}),\s+(20\d{2})\b",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(20\d{2})\b")
CCR_CURRENT_RE = re.compile(
    r"effective\s+on\s+or\s+before\s+(?P<date>\d{1,2}/\d{1,2}/20\d{2})",
    re.IGNORECASE,
)
LEGISCAN_SESSION_RE = re.compile(
    r"Colorado Legislature\s*\|\s*(?P<year>20\d{2})\s*\|",
    re.IGNORECASE,
)
LEGISCAN_API_KEY_RE = re.compile(r"([?&]key=)[^&]+", re.IGNORECASE)
BLOCKED_TEXT_RE = re.compile(
    r"cloudflare|cf-mitigated|captcha|access denied|forbidden|unblock\.federalregister",
    re.IGNORECASE,
)

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

FetchSource = Callable[[dict[str, Any]], "LiveFetchResult"]


class LiveFetchResult(BaseModel):
    """Raw live fetch result for one registered source."""

    model_config = ConfigDict(extra="forbid")

    requested_url: str
    final_url: str
    status_code: int | None
    text: str = ""
    error: str | None = None
    fetched_at: datetime


class OfficialSourceCheck(BaseModel):
    """Normalized live check result for one source registry entry."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_name: str
    owner: str | None = None
    source_url: str
    api_url: str | None = None
    access_method: str
    target_layer: str | None = None
    local_marker: str | None = None
    observed_marker: str | None = None
    observed_at: datetime
    status: str
    http_status: int | None = None
    final_url: str | None = None
    evidence: str
    next_action: str


class OfficialSourceCheckReport(BaseModel):
    """Machine-readable summary for all official source checks."""

    model_config = ConfigDict(extra="forbid")

    report_id: str
    generated_at: datetime
    status: str
    sources_checked: int = Field(ge=0)
    reachable_sources: int = Field(ge=0)
    newer_marker_sources: int = Field(ge=0)
    blocked_sources: int = Field(ge=0)
    failed_sources: int = Field(ge=0)
    manual_only_sources: int = Field(ge=0)
    status_counts: dict[str, int]
    report_path: str
    rows_path: str
    items: list[OfficialSourceCheck]
    boundary: str


def build_official_source_check_report(
    root: Path,
    *,
    fetch_source: FetchSource | None = None,
) -> OfficialSourceCheckReport:
    """Build a live check report for every source in ``SOURCE_REGISTRY.json``."""

    resolved_root = root.resolve()
    registry = _read_list(resolved_root / CONTROL_PLANE_DIR / "SOURCE_REGISTRY.json")
    manifest = _read_dict(resolved_root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json")
    local_markers = _local_markers_by_source(manifest)
    fetcher = fetch_source or _fetch_registered_source
    checks = [
        _check_source(source, local_markers.get(str(source.get("source_id"))), fetcher)
        for source in registry
        if isinstance(source, dict) and source.get("source_id") and source.get("url")
    ]
    counts = Counter(check.status for check in checks)
    status = _overall_status(counts)
    return OfficialSourceCheckReport(
        report_id="OFFICIAL-SOURCE-CHECK-REPORT",
        generated_at=datetime.now(UTC),
        status=status,
        sources_checked=len(checks),
        reachable_sources=sum(
            counts.get(status_key, 0)
            for status_key in (REACHABLE, NEWER_MARKER, NO_NEWER_MARKER)
        ),
        newer_marker_sources=counts.get(NEWER_MARKER, 0),
        blocked_sources=counts.get(BLOCKED, 0),
        failed_sources=counts.get(FAILED, 0),
        manual_only_sources=counts.get(MANUAL_ONLY, 0),
        status_counts=dict(sorted(counts.items())),
        report_path=REPORT_PATH.as_posix(),
        rows_path=ROWS_PATH.as_posix(),
        items=checks,
        boundary=(
            "This report checks live official-source reachability and visible source markers. "
            "It does not download source files, mutate the corpus, certify legal correctness, "
            "or approve external reliance."
        ),
    )


def write_official_source_check_report(
    root: Path,
    *,
    fetch_source: FetchSource | None = None,
) -> OfficialSourceCheckReport:
    """Write official source check artifacts and return the report."""

    resolved_root = root.resolve()
    report = build_official_source_check_report(resolved_root, fetch_source=fetch_source)
    atomic_write_json(resolved_root / REPORT_PATH, report, resolved_root)
    atomic_write_jsonl(resolved_root / ROWS_PATH, report.items, resolved_root)
    docs_path = DOCS_REPORT_DIR / f"OFFICIAL_SOURCE_CHECK_REPORT_{report.generated_at.date()}.md"
    atomic_write_text(resolved_root / docs_path, _docs_report(report), resolved_root)
    return report


def _check_source(
    source: dict[str, Any],
    local_marker: str | None,
    fetch_source: FetchSource,
) -> OfficialSourceCheck:
    try:
        fetched = fetch_source(source)
    except Exception as exc:
        now = datetime.now(UTC)
        return _failed_check(source, local_marker, now, str(exc)[:500])
    return _check_from_fetch(source, local_marker, fetched)


def _check_from_fetch(
    source: dict[str, Any],
    local_marker: str | None,
    fetched: LiveFetchResult,
) -> OfficialSourceCheck:
    source_id = str(source.get("source_id"))
    marker = _source_marker(source_id, fetched.text)
    status = _status_from_fetch(fetched, marker, local_marker)
    evidence = _evidence_for_status(status, marker, fetched)
    return OfficialSourceCheck(
        source_id=source_id,
        source_name=str(source.get("source_name") or source_id),
        owner=_optional_str(source.get("owner")),
        source_url=str(source.get("url") or fetched.requested_url),
        api_url=_optional_str(source.get("api_url")),
        access_method=str(source.get("access_method") or "unknown"),
        target_layer=_optional_str(source.get("target_layer")),
        local_marker=local_marker,
        observed_marker=marker,
        observed_at=fetched.fetched_at,
        status=status,
        http_status=fetched.status_code,
        final_url=fetched.final_url,
        evidence=evidence,
        next_action=_next_action(status, source_id),
    )


def _failed_check(
    source: dict[str, Any],
    local_marker: str | None,
    observed_at: datetime,
    error: str,
) -> OfficialSourceCheck:
    return OfficialSourceCheck(
        source_id=str(source.get("source_id")),
        source_name=str(source.get("source_name") or source.get("source_id")),
        owner=_optional_str(source.get("owner")),
        source_url=str(source.get("url") or ""),
        api_url=_optional_str(source.get("api_url")),
        access_method=str(source.get("access_method") or "unknown"),
        target_layer=_optional_str(source.get("target_layer")),
        local_marker=local_marker,
        observed_marker=None,
        observed_at=observed_at,
        status=FAILED,
        http_status=None,
        final_url=None,
        evidence=f"Live check failed: {error}",
        next_action="Retry the live check or use a browser/manual source workflow.",
    )


def _fetch_registered_source(source: dict[str, Any]) -> LiveFetchResult:
    """Fetch one registered source URL with the shared HTTP client."""

    if str(source.get("source_id") or "") == "legiscan":
        return _fetch_legiscan_source(source)
    urls = _candidate_urls(source)
    client = GeodeHttpClient(
        config=GeodeHttpClientConfig(timeout_seconds=30.0, max_retries=2, base_delay=1.0)
    )
    last_result: LiveFetchResult | None = None
    try:
        for url in urls:
            fetched_at = datetime.now(UTC)
            try:
                response = client.get(url)
                result = LiveFetchResult(
                    requested_url=url,
                    final_url=response.url,
                    status_code=response.status_code,
                    text=response.text[:500_000],
                    fetched_at=fetched_at,
                )
            except Exception as exc:
                result = LiveFetchResult(
                    requested_url=url,
                    final_url=url,
                    status_code=getattr(exc, "status_code", None),
                    text=str(getattr(getattr(exc, "last_response", None), "text", ""))[:500_000],
                    error=str(exc)[:500],
                    fetched_at=fetched_at,
                )
            if not _retry_with_next_candidate(result):
                return result
            last_result = result
        if last_result is not None:
            return last_result
        raise ValueError("source has no candidate URL")
    finally:
        client.close()


def _candidate_urls(source: dict[str, Any]) -> list[str]:
    """Return source-specific URL candidates in preference order."""

    source_id = str(source.get("source_id") or "")
    urls = [str(source.get("url") or "")]
    if source_id == "ag_opinions":
        urls.append("https://coag.gov/attorney-general-opinions/")
    if source_id == "colorado_rulemaking_search":
        urls.append("https://oit-rules-search-ui.coawsprod.com/")
    return [url for index, url in enumerate(urls) if url and url not in urls[:index]]


def _fetch_legiscan_source(source: dict[str, Any]) -> LiveFetchResult:
    """Fetch LegiScan through its API-safe source path when configured."""

    api_url = str(source.get("api_url") or "").strip() or "https://api.legiscan.com/"
    fetched_at = datetime.now(UTC)
    api_key = os.getenv("LEGISCAN_API_KEY", "").strip()
    if not api_key:
        return LiveFetchResult(
            requested_url=api_url,
            final_url=api_url,
            status_code=None,
            text="LEGISCAN_API_KEY is not configured.",
            error="LEGISCAN_API_KEY is required for the API-safe LegiScan check.",
            fetched_at=fetched_at,
        )
    query_url = f"{api_url}?{urlencode({'key': api_key, 'op': 'getSessionList', 'state': 'CO'})}"
    safe_url = _redact_legiscan_key(query_url)
    client = GeodeHttpClient(
        config=GeodeHttpClientConfig(timeout_seconds=30.0, max_retries=2, base_delay=1.0)
    )
    try:
        response = client.get(query_url)
        return LiveFetchResult(
            requested_url=safe_url,
            final_url=_redact_legiscan_key(response.url),
            status_code=response.status_code,
            text=response.text[:500_000],
            fetched_at=fetched_at,
        )
    except Exception as exc:
        response = getattr(exc, "last_response", None)
        return LiveFetchResult(
            requested_url=safe_url,
            final_url=safe_url,
            status_code=getattr(exc, "status_code", None),
            text=str(getattr(response, "text", ""))[:500_000],
            error=str(exc)[:500],
            fetched_at=fetched_at,
        )
    finally:
        client.close()


def _retry_with_next_candidate(result: LiveFetchResult) -> bool:
    """Return whether another candidate URL should be tried."""

    if result.status_code in {404, 410}:
        return True
    return bool(result.error and result.status_code is None)


def _status_from_fetch(
    fetched: LiveFetchResult,
    marker: str | None,
    local_marker: str | None,
) -> str:
    if fetched.error and "LEGISCAN_API_KEY" in fetched.error:
        return CONFIG_REQUIRED
    if _is_blocked_fetch(fetched):
        return BLOCKED
    if fetched.error and fetched.status_code is None:
        return FAILED
    if fetched.status_code is not None and fetched.status_code >= 400:
        return FAILED
    if marker and _observed_is_newer(marker, local_marker):
        return NEWER_MARKER
    if marker:
        return NO_NEWER_MARKER
    return REACHABLE


def _is_blocked_fetch(fetched: LiveFetchResult) -> bool:
    if fetched.status_code in {401, 403, 429}:
        return True
    host = urlparse(fetched.final_url).netloc.casefold()
    if "unblock.federalregister.gov" in host:
        return True
    return bool(BLOCKED_TEXT_RE.search(f"{fetched.final_url}\n{fetched.text}\n{fetched.error or ''}"))


def _source_marker(source_id: str, text: str) -> str | None:
    if source_id == "ccr":
        match = CCR_CURRENT_RE.search(_plain_text(text))
        if match:
            return _date_from_us_text(match.group("date"))
    if source_id == "legiscan":
        api_marker = _legiscan_api_marker(text)
        if api_marker:
            return api_marker
        match = LEGISCAN_SESSION_RE.search(_plain_text(text))
        if match:
            return f"{match.group('year')}-01-01"
    if source_id in {"crs", "colorado_edocket"}:
        return None
    return _latest_date_marker(text) or _latest_year_marker(text)


def _legiscan_api_marker(text: str) -> str | None:
    """Return the newest Colorado session year visible in a LegiScan API response."""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    sessions = payload.get("sessions", payload.get("sessionlist", []))
    if not isinstance(sessions, list):
        return None
    years: list[int] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        for key in ("year_start", "year_end"):
            try:
                year = int(session.get(key) or 0)
            except (TypeError, ValueError):
                continue
            if 2000 <= year <= 2099:
                years.append(year)
    return f"{max(years)}-01-01" if years else None


def _latest_date_marker(value: str) -> str | None:
    dates = sorted(_date_markers(value))
    return dates[-1] if dates else None


def _date_markers(value: str) -> list[str]:
    text = _plain_text(value)
    markers: list[str] = []
    for match in ISO_DATE_RE.finditer(text):
        markers.append(
            f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        )
    for match in US_DATE_RE.finditer(text):
        markers.append(f"{match.group(3)}-{int(match.group(1)):02d}-{int(match.group(2)):02d}")
    for match in MONTH_DATE_RE.finditer(text):
        month = MONTHS[match.group(1).casefold()]
        markers.append(f"{match.group(3)}-{month:02d}-{int(match.group(2)):02d}")
    return markers


def _latest_year_marker(value: str) -> str | None:
    years = sorted(int(match.group(1)) for match in YEAR_RE.finditer(_plain_text(value)))
    return f"{years[-1]}-01-01" if years else None


def _date_from_us_text(value: str) -> str | None:
    match = US_DATE_RE.search(value)
    if not match:
        return None
    return f"{match.group(3)}-{int(match.group(1)):02d}-{int(match.group(2)):02d}"


def _observed_is_newer(observed_marker: str, local_marker: str | None) -> bool:
    if not local_marker:
        return True
    observed_date = _parse_marker_date(observed_marker)
    local_date = _parse_marker_date(local_marker)
    if observed_date and local_date:
        return observed_date > local_date
    return observed_marker.strip() != local_marker.strip()


def _parse_marker_date(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    if re.fullmatch(r"20\d{2}", cleaned):
        cleaned = f"{cleaned}-01-01"
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        return None


def _plain_text(value: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", value)).split())


def _evidence_for_status(status: str, marker: str | None, fetched: LiveFetchResult) -> str:
    if status == CONFIG_REQUIRED:
        return (
            "LegiScan API-safe source check is configured, but LEGISCAN_API_KEY is not "
            "available in this environment."
        )
    if status == BLOCKED:
        return (
            f"Live source responded with a block/challenge signal at {fetched.final_url} "
            f"(HTTP {fetched.status_code})."
        )
    if status == FAILED:
        return f"Live source check failed at {fetched.final_url}: {fetched.error or fetched.status_code}."
    if marker:
        return f"Live source reachable at {fetched.final_url}; visible marker: {marker}."
    return f"Live source reachable at {fetched.final_url}; no date marker was safely extracted."


def _next_action(status: str, source_id: str) -> str:
    if status == NEWER_MARKER:
        return "Review the source-specific guarded refresh before downloading or rewriting corpus data."
    if status == BLOCKED:
        return "Use a browser-safe or manual source workflow before deciding whether a refresh is needed."
    if status == FAILED:
        return "Retry the source check and inspect the source-specific connector."
    if status == CONFIG_REQUIRED:
        return "Set LEGISCAN_API_KEY, then rerun the official source checker."
    if status == MANUAL_ONLY:
        return "Use the documented manual source request workflow."
    if source_id in {"colorado_edocket", "colorado_rulemaking_search", "federal_osha"}:
        return "Keep this source on the live-check watch list and use a source-specific workflow when needed."
    return "No immediate download is indicated by this live check."


def _redact_legiscan_key(value: str) -> str:
    """Remove the LegiScan API key from URLs saved in reports."""

    return LEGISCAN_API_KEY_RE.sub(r"\1<redacted>", value)


def _overall_status(counts: Counter[str]) -> str:
    if counts.get(FAILED, 0):
        return WARN
    if (
        counts.get(BLOCKED, 0)
        or counts.get(NEWER_MARKER, 0)
        or counts.get(MANUAL_ONLY, 0)
        or counts.get(CONFIG_REQUIRED, 0)
    ):
        return WARN
    return PASS


def _local_markers_by_source(manifest: dict[str, Any]) -> dict[str, str]:
    markers: dict[str, str] = {}
    for layer in manifest.get("data_layers", []):
        if not isinstance(layer, dict):
            continue
        marker = str(
            layer.get("currency")
            or layer.get("last_checked")
            or layer.get("last_ingested")
            or ""
        ).strip()
        if not marker:
            continue
        for source_id in str(layer.get("source") or "").split(","):
            cleaned = source_id.strip()
            if cleaned and marker > markers.get(cleaned, ""):
                markers[cleaned] = marker
    return markers


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _read_dict(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return payload


def _read_list(path: Path) -> list[Any]:
    payload = load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Expected list JSON at {path}")
    return payload


def _docs_report(report: OfficialSourceCheckReport) -> str:
    lines = [
        "# Official Source Check Report",
        "",
        f"Generated: {report.generated_at.isoformat()}",
        "",
        "## Summary",
        "",
        f"- Status: {report.status}",
        f"- Sources checked: {report.sources_checked}",
        f"- Reachable sources: {report.reachable_sources}",
        f"- Newer marker sources: {report.newer_marker_sources}",
        f"- Blocked sources: {report.blocked_sources}",
        f"- Failed sources: {report.failed_sources}",
        f"- Manual-only sources: {report.manual_only_sources}",
        "",
        "## Source Results",
        "",
        "| Source | Local marker | Observed marker | Status | Next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report.items:
        lines.append(
            f"| {item.source_name} | {item.local_marker or ''} | "
            f"{item.observed_marker or ''} | {item.status} | {item.next_action} |"
        )
    lines.extend(["", "## Boundary", "", report.boundary, ""])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--write", action="store_true", help="Write report artifacts.")
    parser.add_argument("--json", action="store_true", help="Print JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the official source checker."""

    parser = build_parser()
    args = parser.parse_args(argv)
    report = (
        write_official_source_check_report(args.root)
        if args.write
        else build_official_source_check_report(args.root)
    )
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(
            "Official source check: "
            f"{report.status.upper()} "
            f"({report.sources_checked} checked, {report.blocked_sources} blocked, "
            f"{report.failed_sources} failed)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
