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

from geode.connectors.archive_paths import (
    DOWNLOAD_MANIFEST_NAME,
    download_manifest_path,
    legiscan_bill_json_path,
    temp_path_for,
)
from geode.connectors.download_metadata import (
    COLORADO_JURISDICTION,
    missing_metadata_fields,
    source_format_from_extension,
)
from geode.utils.file_io import iter_jsonl
from geode.utils.hashing import sha256_file

LOGGER = logging.getLogger(__name__)

LEGISCAN_API_URL = "https://api.legiscan.com/"
DOWNLOAD_MANIFEST = DOWNLOAD_MANIFEST_NAME


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


class DownloadManifestEntry(BaseModel):
    """One raw LegiScan bill download manifest entry."""

    model_config = ConfigDict(extra="forbid")

    jurisdiction: str = COLORADO_JURISDICTION
    source_type: str = "bill"
    document_id: str = ""
    document_name: str | None = None
    bill_id: int
    bill_number: str | None = None
    session_year: int
    source_url: str
    source_format: str | None = None
    archive_path: str
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    downloaded_at: datetime
    status: str
    error: str | None = None
    missing_metadata: list[str] = Field(default_factory=list)


class SessionDownloadResult(BaseModel):
    """Internal summary from one LegiScan session download."""

    model_config = ConfigDict(extra="forbid")

    raw_bills: list[dict[str, Any]] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)
    attempted: int = Field(ge=0, default=0)
    skipped: int = Field(ge=0, default=0)
    failed: int = Field(ge=0, default=0)
    network_attempts: int = Field(ge=0, default=0)
    errors: list[str] = Field(default_factory=list)


class DownloadReport(BaseModel):
    """Summary from a LegiScan archive download."""

    model_config = ConfigDict(extra="forbid")

    sessions: int = Field(ge=0)
    bills: int = Field(ge=0)
    attempted: int = Field(ge=0, default=0)
    skipped: int = Field(ge=0, default=0)
    failed: int = Field(ge=0, default=0)
    archive_dir: str
    manifest_path: str
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
    max_downloads: int | None = None,
) -> list[dict[str, Any]]:
    """Download raw LegiScan bill JSON for a Colorado session year."""

    return _download_session_with_result(
        session_year,
        archive_dir,
        api_key=api_key,
        client=client,
        delay=delay,
        max_downloads=max_downloads,
    ).raw_bills


def _download_session_with_result(
    session_year: int,
    archive_dir: Path,
    api_key: str | None = None,
    client: Any | None = None,
    delay: float = 0.25,
    max_downloads: int | None = None,
    session: Session | None = None,
) -> SessionDownloadResult:
    """Download one LegiScan session with manifest-backed resume support."""

    _validate_max_downloads(max_downloads)
    session = session or _session_for_year(
        get_session_list(api_key=api_key, client=client),
        session_year,
    )
    archive_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = download_manifest_path(archive_dir)
    bills = get_session_bills(session.session_id, api_key=api_key, client=client)
    raw_bills: list[dict[str, Any]] = []
    paths: list[str] = []
    errors: list[str] = []
    skipped = 0
    failed = 0
    network_attempts = 0
    for index, bill in enumerate(bills):
        target = _bill_archive_path(archive_dir, session_year, bill.bill_id)
        if _is_downloaded(manifest_path, bill.bill_id, target):
            raw_bills.append(_read_raw_json(target))
            paths.append(target.as_posix())
            skipped += 1
            LOGGER.debug(
                "LegiScan bill download skipped session_year=%s bill_id=%s "
                "source_url=%s archive_path=%s",
                session_year,
                bill.bill_id,
                LEGISCAN_API_URL,
                target.as_posix(),
            )
            continue
        if max_downloads is not None and network_attempts >= max_downloads:
            LOGGER.info(
                "LegiScan session download paused max_downloads=%s session_year=%s "
                "archive_dir=%s",
                max_downloads,
                session_year,
                archive_dir.as_posix(),
            )
            break
        network_attempts += 1
        try:
            detail = get_bill_detail(bill.bill_id, api_key=api_key, client=client)
            raw_bills.append(detail.raw)
            _write_raw_json(target, detail.raw)
            paths.append(target.as_posix())
            _append_manifest(
                manifest_path,
                DownloadManifestEntry(
                    **_manifest_metadata(
                        detail.bill_id,
                        detail.number,
                        detail.title,
                        target,
                    ),
                    bill_id=detail.bill_id,
                    bill_number=detail.number,
                    session_year=session_year,
                    source_url=LEGISCAN_API_URL,
                    archive_path=target.as_posix(),
                    sha256=sha256_file(target),
                    size_bytes=target.stat().st_size,
                    downloaded_at=datetime.now(timezone.utc),
                    status="downloaded",
                ),
            )
            LOGGER.debug(
                "LegiScan bill download succeeded session_year=%s bill_id=%s "
                "source_url=%s archive_path=%s",
                session_year,
                detail.bill_id,
                LEGISCAN_API_URL,
                target.as_posix(),
            )
        except Exception as exc:
            failed += 1
            errors.append(f"{session_year}/{bill.bill_id}: {exc}")
            LOGGER.warning(
                "LegiScan bill download failed session_year=%s bill_id=%s "
                "source_url=%s archive_path=%s error=%s",
                session_year,
                bill.bill_id,
                LEGISCAN_API_URL,
                target.as_posix(),
                exc,
            )
            _append_manifest(
                manifest_path,
                DownloadManifestEntry(
                    **_manifest_metadata(
                        bill.bill_id,
                        bill.number,
                        bill.title,
                        target,
                    ),
                    bill_id=bill.bill_id,
                    bill_number=bill.number,
                    session_year=session_year,
                    source_url=LEGISCAN_API_URL,
                    archive_path=target.as_posix(),
                    sha256=None,
                    size_bytes=0,
                    downloaded_at=datetime.now(timezone.utc),
                    status="failed",
                    error=str(exc),
                ),
            )
        if (
            delay > 0
            and index < len(bills) - 1
            and (max_downloads is None or network_attempts < max_downloads)
        ):
            time.sleep(delay)
    return SessionDownloadResult(
        raw_bills=raw_bills,
        paths=paths,
        attempted=len(paths) + failed,
        skipped=skipped,
        failed=failed,
        network_attempts=network_attempts,
        errors=errors,
    )


def download_all_sessions(
    archive_dir: Path,
    api_key: str | None = None,
    client: Any | None = None,
    delay: float = 0.25,
    max_downloads: int | None = None,
) -> DownloadReport:
    """Download raw JSON for all Colorado LegiScan sessions."""

    _validate_max_downloads(max_downloads)
    sessions = get_session_list(api_key=api_key, client=client)
    paths: list[str] = []
    errors: list[str] = []
    bill_count = 0
    attempted = 0
    skipped = 0
    failed = 0
    network_attempts = 0
    LOGGER.info(
        "LegiScan bulk download sessions=%s archive_dir=%s",
        len(sessions),
        archive_dir.as_posix(),
    )
    for session in sessions:
        year = session.year_start or session.year_end
        if year is None:
            continue
        remaining_downloads = (
            None if max_downloads is None else max(max_downloads - network_attempts, 0)
        )
        try:
            result = _download_session_with_result(
                year,
                archive_dir,
                api_key,
                client,
                delay,
                max_downloads=remaining_downloads,
                session=session,
            )
        except Exception as exc:
            errors.append(f"{year}: {exc}")
            LOGGER.warning(
                "LegiScan session download failed session_year=%s source_url=%s "
                "archive_dir=%s error=%s",
                year,
                LEGISCAN_API_URL,
                archive_dir.as_posix(),
                exc,
            )
            continue
        attempted += result.attempted
        bill_count += len(result.raw_bills)
        skipped += result.skipped
        failed += result.failed
        network_attempts += result.network_attempts
        errors.extend(result.errors)
        paths.extend(result.paths)
        if max_downloads is not None and network_attempts >= max_downloads:
            LOGGER.info(
                "LegiScan bulk download paused max_downloads=%s archive_dir=%s",
                max_downloads,
                archive_dir.as_posix(),
            )
            break
    report = DownloadReport(
        sessions=len(sessions),
        bills=bill_count,
        attempted=attempted,
        skipped=skipped,
        failed=failed,
        archive_dir=archive_dir.as_posix(),
        manifest_path=download_manifest_path(archive_dir).as_posix(),
        paths=paths,
        errors=errors,
    )
    succeeded = max(report.bills - report.skipped, 0)
    log_summary = LOGGER.warning if report.failed or report.errors else LOGGER.info
    log_summary(
        "LegiScan bulk download summary attempted=%s succeeded=%s failed=%s "
        "skipped=%s archive_dir=%s manifest=%s",
        report.attempted,
        succeeded,
        report.failed,
        report.skipped,
        archive_dir.as_posix(),
        report.manifest_path,
    )
    return report


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


def _validate_max_downloads(max_downloads: int | None) -> None:
    """Validate an optional per-run network-attempt cap."""

    if max_downloads is not None and max_downloads < 0:
        raise ValueError("max_downloads cannot be negative")


def _write_raw_json(path: Path, payload: dict[str, Any]) -> None:
    """Write raw LegiScan JSON atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = temp_path_for(path)
    try:
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _read_raw_json(path: Path) -> dict[str, Any]:
    """Read one archived raw LegiScan bill JSON object."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LegiScanError(f"archived bill JSON must be an object: {path}")
    return payload


def _bill_archive_path(archive_dir: Path, session_year: int, bill_id: int) -> Path:
    """Return the raw archive path for one LegiScan bill."""

    return legiscan_bill_json_path(archive_dir, session_year, bill_id)


def _manifest_metadata(
    bill_id: int,
    bill_number: str | None,
    title: str | None,
    target: Path,
) -> dict[str, object]:
    """Return normalized LegiScan raw-download metadata for a manifest row."""

    document_name = title or bill_number
    metadata = {
        "document_id": str(bill_id),
        "document_name": document_name,
        "source_format": source_format_from_extension(target.suffix, default="json"),
    }
    return {
        **metadata,
        "missing_metadata": missing_metadata_fields(metadata),
    }


def _manifest_entry_for(
    manifest_path: Path,
    bill_id: int,
) -> DownloadManifestEntry | None:
    """Return the latest successful manifest entry for one LegiScan bill."""

    if not manifest_path.exists():
        return None
    latest: DownloadManifestEntry | None = None
    for payload in iter_jsonl(manifest_path):
        manifest_entry = DownloadManifestEntry.model_validate(payload)
        if manifest_entry.bill_id == bill_id and manifest_entry.status == "downloaded":
            latest = manifest_entry
    return latest


def _is_downloaded(manifest_path: Path, bill_id: int, target: Path) -> bool:
    """Return whether a LegiScan bill has a matching archived file and manifest row."""

    prior = _manifest_entry_for(manifest_path, bill_id)
    return bool(prior and target.exists() and prior.sha256 == sha256_file(target))


def _append_manifest(path: Path, entry: DownloadManifestEntry) -> None:
    """Append one LegiScan download manifest row atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    existing.append(entry.model_dump_json())
    tmp_path = temp_path_for(path)
    try:
        tmp_path.write_text("\n".join(existing) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
