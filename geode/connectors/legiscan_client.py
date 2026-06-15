"""LegiScan API client for Colorado bill data."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

LOGGER = logging.getLogger(__name__)

LEGISCAN_API_URL = "https://api.legiscan.com/"


class LegiScanError(RuntimeError):
    """Raised for LegiScan API or configuration failures."""


class Session(BaseModel):
    """LegiScan legislative session summary."""

    model_config = ConfigDict(extra="allow")

    session_id: int
    state_id: int | None = None
    year_start: int | None = None
    year_end: int | None = None
    session_name: str | None = None
    special: bool | None = None


class BillSummary(BaseModel):
    """LegiScan bill summary from a master list."""

    model_config = ConfigDict(extra="allow")

    bill_id: int
    number: str
    title: str | None = None
    status: str | int | None = None
    status_date: str | None = None


class BillDetail(BaseModel):
    """LegiScan bill detail wrapper."""

    model_config = ConfigDict(extra="allow")

    bill_id: int
    number: str
    title: str | None = None
    raw: dict[str, Any]


class DownloadReport(BaseModel):
    """Summary from a LegiScan archive download."""

    model_config = ConfigDict(extra="forbid")

    sessions: int = Field(ge=0)
    bills: int = Field(ge=0)
    archive_dir: str
    paths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def get_session_list(
    api_key: str | None = None,
    client: Any | None = None,
) -> list[Session]:
    """Return Colorado LegiScan sessions."""

    payload = _call_api("getSessionList", {"state": "CO"}, api_key, client)
    sessions = payload.get("sessions", payload.get("sessionlist", []))
    return [Session.model_validate(session) for session in sessions]


def get_session_bills(
    session_id: int,
    api_key: str | None = None,
    client: Any | None = None,
) -> list[BillSummary]:
    """Return bill summaries for one LegiScan session."""

    payload = _call_api("getMasterList", {"id": session_id}, api_key, client)
    masterlist = payload.get("masterlist", {})
    if isinstance(masterlist, dict):
        rows = [value for key, value in masterlist.items() if key != "session"]
    else:
        rows = masterlist
    return [BillSummary.model_validate(row) for row in rows if isinstance(row, dict)]


def get_bill_detail(
    bill_id: int,
    api_key: str | None = None,
    client: Any | None = None,
) -> BillDetail:
    """Return full LegiScan bill detail."""

    payload = _call_api("getBill", {"id": bill_id}, api_key, client)
    raw_bill = payload.get("bill", payload)
    if not isinstance(raw_bill, dict):
        raise LegiScanError("LegiScan getBill response did not contain a bill object")
    return BillDetail(
        bill_id=int(raw_bill["bill_id"]),
        number=str(raw_bill["number"]),
        title=raw_bill.get("title"),
        raw=raw_bill,
    )


def download_session(
    session_year: int,
    archive_dir: Path,
    api_key: str | None = None,
    client: Any | None = None,
    delay: float = 0.25,
) -> list[dict[str, Any]]:
    """Download raw LegiScan bill JSON for a Colorado session year."""

    sessions = get_session_list(api_key=api_key, client=client)
    session = _session_for_year(sessions, session_year)
    archive_dir.mkdir(parents=True, exist_ok=True)
    bills = get_session_bills(session.session_id, api_key=api_key, client=client)
    raw_bills: list[dict[str, Any]] = []
    for index, bill in enumerate(bills):
        detail = get_bill_detail(bill.bill_id, api_key=api_key, client=client)
        raw_bills.append(detail.raw)
        target = archive_dir / str(session_year) / f"{detail.bill_id}.json"
        _write_raw_json(target, detail.raw)
        LOGGER.info("Archived LegiScan bill %s to %s", detail.bill_id, target)
        if delay > 0 and index < len(bills) - 1:
            time.sleep(delay)
    return raw_bills


def download_all_sessions(
    archive_dir: Path,
    api_key: str | None = None,
    client: Any | None = None,
    delay: float = 0.25,
) -> DownloadReport:
    """Download raw JSON for all Colorado LegiScan sessions."""

    sessions = get_session_list(api_key=api_key, client=client)
    paths: list[str] = []
    errors: list[str] = []
    bill_count = 0
    for session in sessions:
        year = session.year_start or session.year_end
        if year is None:
            continue
        try:
            raw_bills = download_session(year, archive_dir, api_key, client, delay)
        except Exception as exc:
            errors.append(f"{year}: {exc}")
            continue
        bill_count += len(raw_bills)
        paths.extend(str(path) for path in sorted((archive_dir / str(year)).glob("*.json")))
    return DownloadReport(
        sessions=len(sessions),
        bills=bill_count,
        archive_dir=archive_dir.as_posix(),
        paths=paths,
        errors=errors,
    )


def _call_api(
    operation: str,
    params: dict[str, Any],
    api_key: str | None,
    client: Any | None,
) -> dict[str, Any]:
    """Call the LegiScan API with a configured or injected HTTP client."""

    key = api_key or os.getenv("LEGISCAN_API_KEY")
    if not key:
        raise LegiScanError("LEGISCAN_API_KEY is required for live LegiScan calls")
    query = {"key": key, "op": operation, **params}
    response = _get(LEGISCAN_API_URL, query, client)
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
    payload = response.json() if hasattr(response, "json") else json.loads(response.text)
    if not isinstance(payload, dict):
        raise LegiScanError("LegiScan API returned a non-object response")
    if payload.get("status") == "ERROR":
        raise LegiScanError(str(payload.get("alert", "LegiScan API error")))
    return payload


def _get(url: str, params: dict[str, Any], client: Any | None) -> Any:
    """Issue a GET request using an injected or temporary client."""

    if client is not None:
        return client.get(url, params=params)
    with httpx.Client(timeout=30.0, follow_redirects=True) as http_client:
        return http_client.get(url, params=params)


def _session_for_year(sessions: list[Session], session_year: int) -> Session:
    """Find a LegiScan session matching a year."""

    for session in sessions:
        if session.year_start == session_year or session.year_end == session_year:
            return session
    raise LegiScanError(f"no Colorado LegiScan session found for {session_year}")


def _write_raw_json(path: Path, payload: dict[str, Any]) -> None:
    """Write raw LegiScan JSON atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
