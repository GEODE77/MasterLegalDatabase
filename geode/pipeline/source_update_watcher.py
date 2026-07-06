"""Build a guarded source update watcher dashboard for Project Geode."""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import urljoin

from pydantic import BaseModel, ConfigDict, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.net.http_client import GeodeHttpClient, GeodeHttpClientConfig
from geode.utils.file_io import atomic_write_json, atomic_write_text, load_json

WATCHER_DASHBOARD_PATH = Path(CONTROL_PLANE_DIR) / "SOURCE_UPDATE_WATCHER_DASHBOARD.json"
DOWNLOAD_QUEUE_PATH = Path(CONTROL_PLANE_DIR) / "SOURCE_UPDATE_DOWNLOAD_QUEUE.json"
DOCS_DASHBOARD_PATH = Path("docs") / "audits" / "SOURCE_UPDATE_WATCHER_DASHBOARD_2026-07-06.md"

PASS = "pass"
WARN = "warn"
FAIL = "fail"

NO_CHANGE = "no_change_detected"
NEW_DATA = "new_data_available"
WATCH_READY = "watch_ready"
NEEDS_LIVE_CHECK = "needs_live_check"
LIVE_PROBE_FAILED = "live_probe_failed"
MANUAL_REVIEW = "manual_review_needed"

LIVE_PROBE_SOURCE_IDS = frozenset(
    {"ccr", "colorado_register", "executive_orders", "coprrr", "ag_opinions"}
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
ANCHOR_RE = re.compile(
    r"<a\b[^>]*href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<body>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
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
EXECUTIVE_ORDER_YEAR_RE = re.compile(r"/governor/(20\d{2})-executive-orders\b")
AG_YEAR_PAGE_RE = re.compile(
    r"https://coag\.gov/(?:attorney-general-opinions/)?"
    r"(?:20\d{2}|201\d)-formal-ag-opinions(?:-2)?/"
)

FetchText = Callable[[str], str]


class ObservedSourceState(BaseModel):
    """Externally observed source marker for one source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    marker: str = Field(min_length=1)
    observed_at: datetime
    evidence_url: str
    evidence_note: str


class SourceUpdateWatchItem(BaseModel):
    """Watcher result for one official source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_name: str
    layer_ids: list[str]
    source_url: str
    access_method: str
    update_frequency: str | None = None
    watch_mode: str
    geode_last_checked: str | None = None
    geode_last_ingested: str | None = None
    local_marker: str | None = None
    latest_observed_marker: str | None = None
    observed_at: str | None = None
    change_status: str
    download_status: str
    guarded_download_command: str | None = None
    evidence: str
    next_step: str


class SourceUpdateQueueItem(BaseModel):
    """Guarded download queue item created by the watcher."""

    model_config = ConfigDict(extra="forbid")

    queue_id: str
    source_id: str
    layer_ids: list[str]
    action_type: str
    status: str
    reason: str
    guarded_command: str | None = None
    required_safety_checks: list[str] = Field(min_length=1)


class SourceUpdateWatcherDashboard(BaseModel):
    """Machine-readable source update watcher dashboard."""

    model_config = ConfigDict(extra="forbid")

    dashboard_id: str
    generated_at: datetime
    status: str
    purpose: str
    watch_items_total: int = Field(ge=0)
    new_data_items: int = Field(ge=0)
    manual_review_items: int = Field(ge=0)
    ready_watchers: int = Field(ge=0)
    status_counts: dict[str, int]
    items: list[SourceUpdateWatchItem]
    download_queue: list[SourceUpdateQueueItem]
    recommended_automation_plan: str
    boundary: str


def run_live_source_probes(
    registry: Sequence[Any],
    skip_source_ids: Sequence[str],
    *,
    fetch_text: FetchText | None = None,
) -> tuple[list[ObservedSourceState], dict[str, str]]:
    """Probe official source listing pages for latest visible source markers."""

    skipped = set(skip_source_ids)
    fetcher = fetch_text or _default_fetch_text
    states: list[ObservedSourceState] = []
    errors: dict[str, str] = {}
    for source in registry:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("source_id") or "")
        if source_id not in LIVE_PROBE_SOURCE_IDS or source_id in skipped:
            continue
        try:
            states.append(_probe_source(source_id, str(source.get("url") or ""), fetcher))
        except Exception as exc:
            errors[source_id] = str(exc)[:500]
    return states, errors


def _probe_source(source_id: str, source_url: str, fetch_text: FetchText) -> ObservedSourceState:
    """Return one observed marker from an official source page."""

    if source_id == "ccr":
        return _probe_ccr(source_url, fetch_text)
    if source_id == "colorado_register":
        return _probe_colorado_register(source_url, fetch_text)
    if source_id == "executive_orders":
        return _probe_executive_orders(source_url, fetch_text)
    if source_id == "coprrr":
        return _probe_coprrr(source_url, fetch_text)
    if source_id == "ag_opinions":
        return _probe_ag_opinions(source_url, fetch_text)
    raise ValueError(f"no live probe configured for {source_id}")


def _probe_ccr(source_url: str, fetch_text: FetchText) -> ObservedSourceState:
    """Probe the CCR landing page for the current-through date."""

    page_html = fetch_text(source_url)
    current_match = CCR_CURRENT_RE.search(_html_text(page_html))
    marker = _date_from_us_text(current_match.group("date")) if current_match else None
    marker = marker or _latest_date_marker(page_html)
    if marker is None:
        raise ValueError("CCR page did not expose a current-through date.")
    return _observed_state(
        "ccr",
        marker,
        source_url,
        f"CCR page reports administrative rules current through {marker}.",
    )


def _probe_colorado_register(source_url: str, fetch_text: FetchText) -> ObservedSourceState:
    """Probe the Colorado Register listing for the latest issue date."""

    page_html = fetch_text(source_url)
    marker = _latest_date_marker(page_html)
    if marker is None:
        raise ValueError("Colorado Register page did not expose any issue dates.")
    return _observed_state(
        "colorado_register",
        marker,
        source_url,
        f"Colorado Register listing exposes latest issue date {marker}.",
    )


def _probe_executive_orders(source_url: str, fetch_text: FetchText) -> ObservedSourceState:
    """Probe Governor executive order pages for the latest visible order marker."""

    index_html = fetch_text(source_url)
    year_urls = _executive_order_year_urls(index_html, source_url)
    page_parts = [index_html]
    for year_url in year_urls[-2:]:
        try:
            page_parts.append(fetch_text(year_url))
        except Exception:
            continue
    combined = "\n".join(page_parts)
    marker = _latest_date_marker(combined) or _latest_year_marker(combined)
    if marker is None:
        raise ValueError("Executive order pages did not expose a usable date or year marker.")
    return _observed_state(
        "executive_orders",
        marker,
        source_url,
        f"Governor executive order pages expose latest marker {marker}.",
    )


def _probe_coprrr(source_url: str, fetch_text: FetchText) -> ObservedSourceState:
    """Probe COPRRR review pages for the latest released review date."""

    page_html = fetch_text(source_url)
    marker = _latest_date_marker(page_html) or _latest_year_marker(page_html)
    if marker is None:
        raise ValueError("COPRRR page did not expose a usable release date or year marker.")
    return _observed_state(
        "coprrr",
        marker,
        source_url,
        f"COPRRR listing exposes latest review marker {marker}.",
    )


def _probe_ag_opinions(source_url: str, fetch_text: FetchText) -> ObservedSourceState:
    """Probe AG opinion pages for the latest visible opinion marker."""

    urls = [source_url]
    if source_url.rstrip("/") != "https://coag.gov/attorney-general-opinions":
        urls.append("https://coag.gov/attorney-general-opinions/")
    errors: list[str] = []
    for url in urls:
        try:
            main_html = fetch_text(url)
            year_urls = _ag_year_page_urls(main_html, url)
            page_parts = [main_html]
            for year_url in year_urls[-2:]:
                try:
                    page_parts.append(fetch_text(year_url))
                except Exception:
                    continue
            combined = "\n".join(page_parts)
            marker = _latest_date_marker(combined) or _latest_year_marker(combined)
            if marker:
                return _observed_state(
                    "ag_opinions",
                    marker,
                    url,
                    f"Attorney General opinions pages expose latest marker {marker}.",
                )
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise ValueError("AG opinions probe failed. " + " ".join(errors))


def _observed_state(
    source_id: str,
    marker: str,
    evidence_url: str,
    evidence_note: str,
) -> ObservedSourceState:
    """Build a normalized observed source state."""

    return ObservedSourceState(
        source_id=source_id,
        marker=marker,
        observed_at=datetime.now(UTC),
        evidence_url=evidence_url,
        evidence_note=evidence_note,
    )


def _default_fetch_text(url: str) -> str:
    """Fetch a live source page as text."""

    client = GeodeHttpClient(
        config=GeodeHttpClientConfig(timeout_seconds=30.0, max_retries=2, base_delay=1.0)
    )
    try:
        return client.get(url).text
    finally:
        client.close()


def build_source_update_watcher_dashboard(
    root: Path,
    observed_states: Sequence[ObservedSourceState] | None = None,
    *,
    live_probes: bool = False,
    fetch_text: FetchText | None = None,
) -> SourceUpdateWatcherDashboard:
    """Build the source update watcher dashboard from local and observed source evidence."""

    resolved_root = root.resolve()
    registry = _read_list(resolved_root / CONTROL_PLANE_DIR / "SOURCE_REGISTRY.json")
    manifest = _read_dict(resolved_root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json")
    freshness = _read_dict(resolved_root / CONTROL_PLANE_DIR / "FRESHNESS_VERIFICATION_QUEUE.json")
    observed_by_source = {state.source_id: state for state in observed_states or []}
    probe_errors: dict[str, str] = {}
    if live_probes:
        live_states, probe_errors = run_live_source_probes(
            registry,
            observed_by_source.keys(),
            fetch_text=fetch_text,
        )
        observed_by_source.update({state.source_id: state for state in live_states})
    layers_by_source = _layers_by_source(manifest)
    pending_freshness = _pending_freshness_by_source(freshness, manifest)
    items = [
        _build_watch_item(
            source=source,
            layers=layers_by_source.get(str(source.get("source_id")), []),
            observed=observed_by_source.get(str(source.get("source_id"))),
            probe_error=probe_errors.get(str(source.get("source_id"))),
            pending_action=pending_freshness.get(str(source.get("source_id"))),
        )
        for source in registry
        if isinstance(source, dict) and source.get("source_id")
    ]
    queue = [_queue_item(item) for item in items if _should_queue(item)]
    status_counts = Counter(item.change_status for item in items)
    status = _overall_status(items)
    return SourceUpdateWatcherDashboard(
        dashboard_id="SOURCE-UPDATE-WATCHER-DASHBOARD",
        generated_at=datetime.now(UTC),
        status=status,
        purpose=(
            "Identify likely new official source material before any future download, "
            "then route safe downloads through the existing guarded pipeline."
        ),
        watch_items_total=len(items),
        new_data_items=sum(1 for item in items if item.change_status == NEW_DATA),
        manual_review_items=sum(1 for item in items if item.change_status == MANUAL_REVIEW),
        ready_watchers=sum(1 for item in items if item.change_status == WATCH_READY),
        status_counts=dict(sorted(status_counts.items())),
        items=items,
        download_queue=queue,
        recommended_automation_plan=(
            "Use guarded automatic downloads for API-backed or stable listing sources, "
            "and keep manual intake for sources that require email, archives, or official "
            "replacement files. Every run should update this dashboard before downloading."
        ),
        boundary=(
            "This dashboard identifies source freshness signals and guarded next steps. "
            "It does not authorize legal reliance, unofficial source substitution, or "
            "unsupervised broad corpus refreshes."
        ),
    )


def write_source_update_watcher_dashboard(
    root: Path,
    observed_states: Sequence[ObservedSourceState] | None = None,
    *,
    live_probes: bool = False,
    fetch_text: FetchText | None = None,
) -> SourceUpdateWatcherDashboard:
    """Write source update watcher dashboard artifacts."""

    resolved_root = root.resolve()
    dashboard = build_source_update_watcher_dashboard(
        resolved_root,
        observed_states,
        live_probes=live_probes,
        fetch_text=fetch_text,
    )
    atomic_write_json(resolved_root / WATCHER_DASHBOARD_PATH, dashboard, resolved_root)
    atomic_write_json(
        resolved_root / DOWNLOAD_QUEUE_PATH,
        {
            "generated_at": dashboard.generated_at.isoformat(),
            "status": dashboard.status,
            "item_count": len(dashboard.download_queue),
            "items": [item.model_dump(mode="json") for item in dashboard.download_queue],
            "boundary": dashboard.boundary,
        },
        resolved_root,
    )
    atomic_write_text(resolved_root / DOCS_DASHBOARD_PATH, _docs_report(dashboard), resolved_root)
    return dashboard


def _build_watch_item(
    *,
    source: dict[str, Any],
    layers: list[dict[str, Any]],
    observed: ObservedSourceState | None,
    probe_error: str | None,
    pending_action: str | None,
) -> SourceUpdateWatchItem:
    source_id = str(source["source_id"])
    source_url = str(source.get("url") or "")
    access_method = str(source.get("access_method") or "unknown")
    geode_last_checked = _latest_layer_value(layers, "last_checked")
    geode_last_ingested = _latest_layer_value(layers, "last_ingested")
    local_marker = _local_marker(source_id, layers)
    change_status = _change_status(
        source_id,
        access_method,
        local_marker,
        observed,
        probe_error,
        pending_action,
    )
    download_status = _download_status(access_method, change_status)
    command = _guarded_command(source_id, layers, change_status, download_status)
    return SourceUpdateWatchItem(
        source_id=source_id,
        source_name=str(source.get("source_name") or source_id),
        layer_ids=[str(layer.get("id")) for layer in layers if layer.get("id")],
        source_url=source_url,
        access_method=access_method,
        update_frequency=source.get("update_frequency"),
        watch_mode=_watch_mode(source_id, access_method),
        geode_last_checked=geode_last_checked,
        geode_last_ingested=geode_last_ingested,
        local_marker=local_marker,
        latest_observed_marker=observed.marker if observed else None,
        observed_at=observed.observed_at.isoformat() if observed else None,
        change_status=change_status,
        download_status=download_status,
        guarded_download_command=command,
        evidence=_evidence(source_url, observed, probe_error, pending_action),
        next_step=_next_step(source_id, change_status, download_status),
    )


def _change_status(
    source_id: str,
    access_method: str,
    local_marker: str | None,
    observed: ObservedSourceState | None,
    probe_error: str | None,
    pending_action: str | None,
) -> str:
    if pending_action:
        return MANUAL_REVIEW
    if access_method == "email_request":
        return MANUAL_REVIEW
    if probe_error:
        return LIVE_PROBE_FAILED
    if observed is None:
        return WATCH_READY if source_id in {"legiscan", "colorado_register"} else NEEDS_LIVE_CHECK
    if _observed_is_newer(observed.marker, local_marker):
        return NEW_DATA
    return NO_CHANGE


def _observed_is_newer(observed_marker: str, local_marker: str | None) -> bool:
    if local_marker is None:
        return True
    observed_date = _parse_date(observed_marker)
    local_date = _parse_date(local_marker)
    if observed_date and local_date:
        return observed_date > local_date
    return observed_marker.strip() != local_marker.strip()


def _latest_date_marker(value: str) -> str | None:
    """Return the latest ISO date visible in text or HTML."""

    dates = sorted(_date_markers(value))
    return dates[-1] if dates else None


def _date_markers(value: str) -> list[str]:
    """Return all visible ISO dates from text or HTML."""

    text = _html_text(value)
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


def _date_from_us_text(value: str) -> str | None:
    """Return an ISO date from MM/DD/YYYY text."""

    match = US_DATE_RE.search(value)
    if not match:
        return None
    return f"{match.group(3)}-{int(match.group(1)):02d}-{int(match.group(2)):02d}"


def _latest_year_marker(value: str) -> str | None:
    """Return a conservative ISO marker for the latest year visible in text."""

    years = sorted(int(match.group(1)) for match in YEAR_RE.finditer(_html_text(value)))
    if not years:
        return None
    return f"{years[-1]}-01-01"


def _executive_order_year_urls(value: str, source_url: str) -> list[str]:
    """Return Governor executive-order year page URLs from an index page."""

    urls = []
    for href, _body in _anchors(value):
        absolute = urljoin(source_url, href)
        if EXECUTIVE_ORDER_YEAR_RE.search(absolute):
            urls.append(absolute)
    return sorted(set(urls))


def _ag_year_page_urls(value: str, source_url: str) -> list[str]:
    """Return official AG opinion year page URLs from a main page."""

    urls = []
    for href, _body in _anchors(value):
        absolute = urljoin(source_url, href)
        if AG_YEAR_PAGE_RE.search(absolute):
            urls.append(absolute)
    normalized = html.unescape(value).replace("\\/", "/")
    for match in AG_YEAR_PAGE_RE.finditer(normalized):
        urls.append(match.group(0))
    return sorted(set(urls))


def _anchors(value: str) -> list[tuple[str, str]]:
    """Return href and body pairs from anchor tags."""

    return [
        (html.unescape(match.group("href")), match.group("body"))
        for match in ANCHOR_RE.finditer(value)
    ]


def _html_text(value: str) -> str:
    """Return readable text from an HTML fragment."""

    return " ".join(html.unescape(TAG_RE.sub(" ", value)).split())


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    if re.fullmatch(r"20\d{2}", cleaned):
        return date(int(cleaned), 1, 1)
    for token in cleaned.replace("/", "-").split():
        try:
            return date.fromisoformat(token)
        except ValueError:
            continue
    return None


def _download_status(access_method: str, change_status: str) -> str:
    if change_status == NEW_DATA and access_method in {"api", "scrape"}:
        return "guarded_download_ready"
    if change_status in {MANUAL_REVIEW, NEW_DATA}:
        return "manual_or_guarded_intake_required"
    if change_status == NO_CHANGE:
        return "no_download_needed"
    if change_status == LIVE_PROBE_FAILED:
        return "probe_failed"
    return "watch_only"


def _guarded_command(
    source_id: str,
    layers: list[dict[str, Any]],
    change_status: str,
    download_status: str,
) -> str | None:
    if download_status == "no_download_needed":
        return None
    if source_id == "legiscan":
        current_year = datetime.now(UTC).year
        return (
            "python -m geode.connectors.legiscan_pipeline --output-root . "
            f"--download --session-year {current_year}"
        )
    if source_id == "colorado_register":
        return "python -m geode.connectors.register_pipeline --output-root . --download"
    if source_id == "executive_orders":
        return (
            "Use the existing executive order connector or manual_source_intake for "
            "blocked official files, then rerun the executive order rebuild."
        )
    if change_status == NEW_DATA and layers:
        return "Run the source-specific guarded connector, then rerun validation and closeout."
    return None


def _queue_item(item: SourceUpdateWatchItem) -> SourceUpdateQueueItem:
    action_type = (
        "guarded_download"
        if item.download_status == "guarded_download_ready"
        else "manual_source_review"
    )
    return SourceUpdateQueueItem(
        queue_id=f"SOURCE-UPDATE-{item.source_id.upper()}",
        source_id=item.source_id,
        layer_ids=item.layer_ids,
        action_type=action_type,
        status="queued",
        reason=item.next_step,
        guarded_command=item.guarded_download_command,
        required_safety_checks=[
            "Confirm the source URL is official or authorized.",
            "Run the secret safety check before committing.",
            "Run the relevant layer validation after download.",
            "Run the download closeout checklist before push.",
        ],
    )


def _should_queue(item: SourceUpdateWatchItem) -> bool:
    return item.change_status in {NEW_DATA, MANUAL_REVIEW}


def _watch_mode(source_id: str, access_method: str) -> str:
    if source_id == "legiscan":
        return "api_pull"
    if access_method == "email_request":
        return "manual_request"
    if access_method == "scrape":
        return "official_listing_watch"
    return "source_registry_watch"


def _next_step(source_id: str, change_status: str, download_status: str) -> str:
    if change_status == NEW_DATA:
        return "New official source material appears available; run the guarded command."
    if change_status == MANUAL_REVIEW:
        return "Manual source review is needed before any download or replacement intake."
    if change_status == NO_CHANGE:
        return "No new source marker is newer than Geode's recorded refresh marker."
    if change_status == LIVE_PROBE_FAILED:
        return "Live probe failed; retry the source check before deciding whether to download."
    if source_id == "legiscan":
        return "Watcher is configured; run the LegiScan API pull during the next refresh window."
    if download_status == "watch_only":
        return "Live source check is needed before deciding whether to download."
    return "Keep this source on the update watch list."


def _evidence(
    source_url: str,
    observed: ObservedSourceState | None,
    probe_error: str | None,
    pending_action: str | None,
) -> str:
    if pending_action:
        return pending_action
    if observed:
        return f"{observed.evidence_note} ({observed.evidence_url})"
    if probe_error:
        return f"Live source probe failed for {source_url}: {probe_error}"
    return f"Source is registered for watching at {source_url}."


def _local_marker(source_id: str, layers: list[dict[str, Any]]) -> str | None:
    if source_id == "crs":
        currency = _latest_layer_value(layers, "currency")
        if currency:
            return currency
    return _latest_layer_value(layers, "last_checked") or _latest_layer_value(layers, "last_ingested")


def _latest_layer_value(layers: list[dict[str, Any]], field: str) -> str | None:
    values = [str(layer.get(field)) for layer in layers if layer.get(field)]
    if not values:
        return None
    return sorted(values)[-1]


def _layers_by_source(manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_source: dict[str, list[dict[str, Any]]] = {}
    for layer in manifest.get("data_layers", []):
        if not isinstance(layer, dict):
            continue
        for source_id in str(layer.get("source", "")).split(","):
            cleaned = source_id.strip()
            if cleaned:
                by_source.setdefault(cleaned, []).append(layer)
    return by_source


def _pending_freshness_by_source(
    freshness: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, str]:
    layer_to_source: dict[str, str] = {}
    for layer in manifest.get("data_layers", []):
        if isinstance(layer, dict) and layer.get("id") and layer.get("source"):
            layer_to_source[str(layer["id"])] = str(layer["source"]).split(",")[0].strip()
    pending: dict[str, str] = {}
    for item in freshness.get("items", []):
        if not isinstance(item, dict) or not item.get("network_refresh_required"):
            continue
        source_id = layer_to_source.get(str(item.get("layer_id")))
        if source_id:
            pending[source_id] = str(item.get("official_refresh_action") or "Refresh required.")
    return pending


def _overall_status(items: Sequence[SourceUpdateWatchItem]) -> str:
    if any(item.change_status == NEW_DATA for item in items):
        return WARN
    if any(item.change_status == MANUAL_REVIEW for item in items):
        return WARN
    if any(item.change_status == LIVE_PROBE_FAILED for item in items):
        return WARN
    return PASS


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


def _load_observed_states(path: Path | None) -> list[ObservedSourceState]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("--observed-states must point to a JSON list")
    return [ObservedSourceState.model_validate(item) for item in payload]


def _docs_report(dashboard: SourceUpdateWatcherDashboard) -> str:
    lines = [
        "# Source Update Watcher Dashboard",
        "",
        f"Generated: {dashboard.generated_at.isoformat()}",
        "",
        "## Summary",
        "",
        f"- Status: {dashboard.status}",
        f"- Sources watched: {dashboard.watch_items_total}",
        f"- New data items: {dashboard.new_data_items}",
        f"- Manual review items: {dashboard.manual_review_items}",
        f"- Queued download or review items: {len(dashboard.download_queue)}",
        "",
        "## Watch List",
        "",
        "| Source | Layers | Local marker | Observed marker | Status | Download status | Next step |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in dashboard.items:
        layers = ", ".join(item.layer_ids) if item.layer_ids else "none"
        lines.append(
            f"| {item.source_name} | {layers} | {item.local_marker or ''} | "
            f"{item.latest_observed_marker or ''} | {item.change_status} | "
            f"{item.download_status} | {item.next_step} |"
        )
    lines.extend(
        [
            "",
            "## Guarded Queue",
            "",
            "| Queue ID | Source | Action | Command |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in dashboard.download_queue:
        command = item.guarded_command or "Manual source review required."
        lines.append(f"| {item.queue_id} | {item.source_id} | {item.action_type} | {command} |")
    lines.extend(
        [
            "",
            "## Recommended Plan",
            "",
            dashboard.recommended_automation_plan,
            "",
            "## Boundary",
            "",
            dashboard.boundary,
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--write", action="store_true", help="Write dashboard artifacts.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument(
        "--live-probes",
        action="store_true",
        help="Fetch official source pages and derive latest visible source markers.",
    )
    parser.add_argument(
        "--observed-states",
        type=Path,
        help="Optional JSON list of externally observed source markers.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the source update watcher dashboard builder."""

    parser = build_parser()
    args = parser.parse_args(argv)
    observed_states = _load_observed_states(args.observed_states)
    dashboard = (
        write_source_update_watcher_dashboard(
            args.root,
            observed_states,
            live_probes=args.live_probes,
        )
        if args.write
        else build_source_update_watcher_dashboard(
            args.root,
            observed_states,
            live_probes=args.live_probes,
        )
    )
    if args.json:
        print(dashboard.model_dump_json(indent=2))
    else:
        print(
            "Source update watcher: "
            f"{dashboard.status.upper()} "
            f"({dashboard.new_data_items} new, {dashboard.manual_review_items} review)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
