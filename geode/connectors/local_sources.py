"""Bounded downloader for county and district pilot sources."""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from pydantic import BaseModel, Field, HttpUrl

from geode.constants import AUTHORIZED_SOURCE_HOSTS
from geode.net.http_client import (
    GeodeHttpClient,
    GeodeHttpClientConfig,
    GeodeHttpError,
    GeodeHttpResponse,
    build_session,
)
from geode.utils.file_io import (
    _replace_with_retry,
    atomic_write_jsonl,
    iter_jsonl,
    load_json,
)

LOGGER = logging.getLogger(__name__)
REGISTRY_PATH = Path("_CONTROL_PLANE") / "LOCAL_SOURCE_REGISTRY.json"
CATEGORY_PAGE_TERMS = (
    "ordinance", "code", "zoning", "land", "planning", "subdivision", "development",
    "building", "health", "environment", "burn", "road", "transport", "animal",
    "nuisance", "emergency", "fire", "resolution", "regulation", "policy", "manual",
)


class LocalDownloadRecord(BaseModel):
    """Audit record for one local source retrieval attempt."""

    source_id: str
    authority_id: str
    authority_level: str
    source_url: HttpUrl
    requested_url: HttpUrl
    raw_path: str
    status: str
    http_status: int | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    retrieved_at: datetime
    linked_urls: list[str] = Field(default_factory=list)
    failure_class: str | None = None
    message: str = ""


class LocalDownloadSummary(BaseModel):
    """Summary of one bounded local pilot run."""

    connector: str = "local_sources"
    started_at: datetime
    completed_at: datetime
    dry_run: bool
    attempted: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    records_path: str
    coverage_boundary: str


def download_pilot_sources(
    root: Path,
    *,
    authority_level: str | None = None,
    source_ids: set[str] | None = None,
    dry_run: bool = False,
    max_links_per_source: int = 25,
    max_pages_per_source: int = 10,
    timeout_seconds: float = 30.0,
    unattempted_registered: bool = False,
    max_retries: int = 3,
    retry_delay_seconds: float = 1.0,
    retry_failed: bool = False,
) -> LocalDownloadSummary:
    """Download the bounded county and district pilot source set.

    Landing pages are archived first. Directly linked legal documents are
    archived only when they use an approved source host and a legal-document
    extension. No source is converted or overwritten by this connector.
    """

    resolved_root = root.resolve()
    registry = load_json(resolved_root / REGISTRY_PATH)
    pilot = registry.get("pilot", {})
    entries = [*pilot.get("counties", []), *pilot.get("county_sources", []), *pilot.get("districts", [])]
    manifest_path = resolved_root / "_CONTROL_PLANE" / "LOCAL_DOWNLOAD_MANIFEST.jsonl"
    if retry_failed or unattempted_registered:
        manifest_rows = list(iter_jsonl(manifest_path)) if manifest_path.exists() else []
        if retry_failed:
            failed_ids = {
                str(row.get("source_id"))
                for row in manifest_rows
                if row.get("requested_url") == row.get("source_url")
                and row.get("status") == "failed"
            }
            entries = [
                entry for entry in [*pilot.get("counties", []), *pilot.get("county_sources", [])]
                if str(entry.get("source_id")) in failed_ids
            ]
        if unattempted_registered:
            attempted_ids = {str(row.get("source_id")) for row in manifest_rows}
            entries = [
                entry for entry in pilot.get("county_sources", [])
                if str(entry.get("source_id")) not in attempted_ids
            ]
    if authority_level:
        entries = [item for item in entries if item.get("authority_level") == authority_level]
    if source_ids:
        entries = [item for item in entries if item.get("source_id") in source_ids]
    archive_root = resolved_root / "_RAW_ARCHIVE" / "local"
    archive_root.mkdir(parents=True, exist_ok=True)
    record_path = resolved_root / "_CONTROL_PLANE" / "LOCAL_DOWNLOAD_MANIFEST.jsonl"
    prior_by_url: dict[tuple[str, str], LocalDownloadRecord] = {}
    if unattempted_registered and record_path.exists():
        for row in iter_jsonl(record_path):
            if row.get("source_url") and row.get("requested_url"):
                prior_by_url[(str(row["source_url"]), str(row["requested_url"]))] = LocalDownloadRecord.model_validate(row)
    started = datetime.now(timezone.utc)
    records: list[LocalDownloadRecord] = []
    client = GeodeHttpClient(
        session=build_session(impersonate=True),
        config=GeodeHttpClientConfig(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            base_delay=retry_delay_seconds,
            max_retry_delay_seconds=max(retry_delay_seconds, 10.0),
        ),
    )
    try:
        for entry in entries:
            source_url = str(entry["url"])
            prior = prior_by_url.get((source_url, source_url))
            if unattempted_registered and prior is not None:
                entry_records = [_reuse_record(entry, prior)]
            else:
                entry_records = _download_entry(
                    entry,
                    archive_root,
                    client=client,
                    dry_run=dry_run,
                    max_links=max_links_per_source,
                    max_pages=max_pages_per_source,
                    timeout_seconds=timeout_seconds,
                )
            records.extend(entry_records)
    finally:
        client.close()
    if not dry_run and records:
        existing = list(iter_jsonl(record_path)) if record_path.exists() else []
        atomic_write_jsonl(record_path, [*existing, *records], resolved_root)
    completed = datetime.now(timezone.utc)
    return LocalDownloadSummary(
        started_at=started,
        completed_at=completed,
        dry_run=dry_run,
        attempted=len(records),
        downloaded=sum(record.status == "downloaded" for record in records),
        skipped=sum(record.status == "skipped" for record in records),
        failed=sum(record.status == "failed" for record in records),
        records_path=record_path.as_posix(),
        coverage_boundary=str(registry.get("coverage_boundary", "")),
    )


def _download_entry(
    entry: dict[str, object],
    archive_root: Path,
    *,
    client: GeodeHttpClient,
    dry_run: bool,
    max_links: int,
    max_pages: int,
    timeout_seconds: float,
) -> list[LocalDownloadRecord]:
    """Download one registered local source and approved linked documents."""

    source_id = str(entry["source_id"])
    authority_id = str(entry["authority_id"])
    level = str(entry["authority_level"])
    source_url = str(entry["url"])
    _require_approved_url(source_url)
    now = datetime.now(timezone.utc)
    base_dir = archive_root / level / _safe(source_id)
    base_dir.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return [LocalDownloadRecord(
            source_id=source_id, authority_id=authority_id, authority_level=level,
            source_url=source_url, requested_url=source_url,
            raw_path=(base_dir / "landing_page.html").as_posix(), status="skipped",
            retrieved_at=now, message="dry_run: source was inventoried but not fetched",
        )]
    try:
        response = _fetch(client, source_url, timeout_seconds=timeout_seconds)
        content_type = _header(response.headers, "Content-Type")
        landing_path = base_dir / ("landing_page" + _extension(content_type, source_url))
        landing_path = _write_immutable(landing_path, response.content)
        records = [_record(source_id, authority_id, level, source_url, source_url, landing_path, response.status_code, response.content, now)]
        if "html" in content_type.lower():
            document_links = _linked_documents(source_url, response.text, max_links)
            page_links = _linked_pages(source_url, response.text, max_pages) if max_links > 0 else []
            seen_documents: set[str] = set()
            for link in document_links:
                seen_documents.add(link)
                try:
                    linked = _fetch(client, link, referer=source_url, timeout_seconds=timeout_seconds)
                    linked_name = Path(urlparse(link).path).name or "linked_source"
                    linked_path = base_dir / _safe_filename(linked_name)
                    linked_path = _write_immutable(linked_path, linked.content)
                    records.append(_record(source_id, authority_id, level, source_url, link, linked_path, linked.status_code, linked.content, now))
                except (GeodeHttpError, requests.RequestException, ValueError) as exc:
                    records.append(_failed_record(source_id, authority_id, level, source_url, link, base_dir, now, str(exc)))
            for page_link in page_links:
                try:
                    page_response = _fetch(client, page_link, referer=source_url, timeout_seconds=timeout_seconds)
                    page_path = base_dir / _page_filename(page_link)
                    page_path = _write_immutable(page_path, page_response.content)
                    records.append(
                        _record(
                            source_id,
                            authority_id,
                            level,
                            source_url,
                            page_link,
                            page_path,
                            page_response.status_code,
                            page_response.content,
                            now,
                        )
                    )
                    if "html" not in _header(page_response.headers, "Content-Type").lower():
                        continue
                    for link in _linked_documents(page_link, page_response.text, max_links):
                        if link in seen_documents:
                            continue
                        seen_documents.add(link)
                        try:
                            linked = _fetch(client, link, referer=page_link, timeout_seconds=timeout_seconds)
                            linked_name = Path(urlparse(link).path).name or "linked_source"
                            linked_path = base_dir / _safe_filename(linked_name)
                            linked_path = _write_immutable(linked_path, linked.content)
                            records.append(
                                _record(
                                    source_id,
                                    authority_id,
                                    level,
                                    source_url,
                                    link,
                                    linked_path,
                                    linked.status_code,
                                    linked.content,
                                    now,
                                )
                            )
                        except (GeodeHttpError, requests.RequestException, ValueError) as exc:
                            records.append(
                                _failed_record(source_id, authority_id, level, source_url, link, base_dir, now, str(exc))
                            )
                except (GeodeHttpError, requests.RequestException, ValueError) as exc:
                    records.append(
                        _failed_record(source_id, authority_id, level, source_url, page_link, base_dir, now, str(exc))
                    )
        return records
    except (GeodeHttpError, requests.RequestException, ValueError) as exc:
        return [_failed_record(source_id, authority_id, level, source_url, source_url, base_dir, now, str(exc))]


def _fetch(
    client: GeodeHttpClient,
    url: str,
    *,
    referer: str | None = None,
    timeout_seconds: float,
) -> GeodeHttpResponse:
    """Fetch one official page using the shared browser-aware retry client."""

    return client.get(
        url,
        referer=referer,
        timeout_seconds=timeout_seconds,
        require_content=True,
    )


def _header(headers: object, name: str) -> str:
    """Read a response header without depending on header-name capitalization."""

    if not hasattr(headers, "items"):
        return ""
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            return str(value)
    return ""


def _linked_documents(base_url: str, html: str, max_links: int) -> list[str]:
    """Return same-host document links from an official landing page."""

    if max_links <= 0:
        return []
    links: list[str] = []
    for href in re.findall(r"href=[\"']([^\"']+)[\"']", html, flags=re.IGNORECASE):
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        host = parsed.netloc.lower()
        if parsed.scheme != "https" or (
            host not in AUTHORIZED_SOURCE_HOSTS and not host.endswith(".colorado.gov")
        ):
            continue
        suffix = Path(parsed.path).suffix.casefold()
        if suffix not in {".pdf", ".doc", ".docx", ".html", ".htm", ".txt", ".csv", ".xlsx"}:
            continue
        if absolute not in links:
            links.append(absolute)
        if len(links) >= max_links:
            break
    return links


def _linked_pages(base_url: str, html: str, max_pages: int) -> list[str]:
    """Return bounded same-host category pages likely to contain legal documents."""

    if max_pages <= 0:
        return []
    base_host = urlparse(base_url).netloc.lower()
    pages: list[str] = []
    for href in re.findall(r"href=[\"']([^\"']+)[\"']", html, flags=re.IGNORECASE):
        absolute = urljoin(base_url, href).split("#", 1)[0]
        parsed = urlparse(absolute)
        host = parsed.netloc.lower()
        path = parsed.path.casefold()
        suffix = Path(parsed.path).suffix.casefold()
        if parsed.scheme != "https" or host != base_host:
            continue
        if suffix not in {"", ".html", ".htm", ".php", ".aspx"}:
            continue
        if not any(term in path for term in CATEGORY_PAGE_TERMS):
            continue
        if absolute not in pages and absolute != base_url:
            pages.append(absolute)
        if len(pages) >= max_pages:
            break
    return pages


def _page_filename(url: str) -> str:
    """Create a stable raw filename for an HTML discovery page."""

    path_name = Path(urlparse(url).path).name
    stem = _safe(Path(path_name).stem if path_name else "source_page")
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"source_page_{stem[:50]}_{digest}.html"


def _record(source_id: str, authority_id: str, level: str, source_url: str, requested_url: str, path: Path, status: int, content: bytes, now: datetime) -> LocalDownloadRecord:
    """Build a successful download record."""

    return LocalDownloadRecord(source_id=source_id, authority_id=authority_id, authority_level=level, source_url=source_url, requested_url=requested_url, raw_path=path.as_posix(), status="downloaded", http_status=status, sha256=hashlib.sha256(content).hexdigest(), retrieved_at=now)


def _reuse_record(entry: dict[str, object], prior: LocalDownloadRecord) -> LocalDownloadRecord:
    """Record a category alias without downloading an identical URL again."""

    return LocalDownloadRecord(
        source_id=str(entry["source_id"]),
        authority_id=str(entry["authority_id"]),
        authority_level=str(entry["authority_level"]),
        source_url=str(entry["url"]),
        requested_url=str(entry["url"]),
        raw_path=prior.raw_path,
        status=prior.status,
        http_status=prior.http_status,
        sha256=prior.sha256,
        retrieved_at=prior.retrieved_at,
        linked_urls=prior.linked_urls,
        message=f"Reused prior manifest outcome from source_id={prior.source_id}; identical official URL.",
    )


def _failed_record(source_id: str, authority_id: str, level: str, source_url: str, requested_url: str, base_dir: Path, now: datetime, message: str) -> LocalDownloadRecord:
    """Build a failed download record without hiding the source gap."""

    return LocalDownloadRecord(source_id=source_id, authority_id=authority_id, authority_level=level, source_url=source_url, requested_url=requested_url, raw_path=(base_dir / "FAILED").as_posix(), status="failed", retrieved_at=now, failure_class=_failure_class(message), message=message)


def _failure_class(message: str) -> str:
    """Classify a failure for recovery routing without claiming the law is absent."""

    lowered = message.casefold()
    if "403" in lowered or "forbidden" in lowered or "blocked" in lowered:
        return "access_denied"
    if "404" in lowered or "not found" in lowered:
        return "missing_or_moved_source"
    if "name resolution" in lowered or "dns" in lowered:
        return "dns_or_domain_failure"
    if "proxy" in lowered or "timeout" in lowered or "connection" in lowered:
        return "network_or_transport_failure"
    return "other_failure"


def _write_immutable(target: Path, content: bytes) -> Path:
    """Write a raw source once, versioning changed content without replacement."""

    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() == hashlib.sha256(content).hexdigest():
            return target
        digest = hashlib.sha256(content).hexdigest()[:12]
        target = target.with_name(f"{target.stem}_{digest}{target.suffix}")
        if target.exists():
            return target
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(content)
    _replace_with_retry(temporary, target)
    return target


def _require_approved_url(url: str) -> None:
    """Require HTTPS and an approved official source host."""

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if parsed.scheme != "https" or (
        host not in AUTHORIZED_SOURCE_HOSTS and not host.endswith(".colorado.gov")
    ):
        raise ValueError(f"unapproved local source URL: {url}")


def _extension(content_type: str, url: str) -> str:
    """Choose a stable extension for a landing page."""

    suffix = Path(urlparse(url).path).suffix.casefold()
    if suffix in {".pdf", ".doc", ".docx", ".txt", ".csv", ".xlsx"}:
        return suffix
    return ".html" if "html" in content_type.lower() else ".bin"


def _safe(value: str) -> str:
    """Return a filesystem-safe source name."""

    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "source"


def _safe_filename(value: str) -> str:
    """Keep a recognized document extension while sanitizing a filename."""

    suffix = Path(value).suffix.casefold()
    stem = value[: -len(suffix)] if suffix else value
    safe_stem = _safe(stem)
    # Windows has a practical path-length limit. Preserve the extension while
    # keeping the URL and content hash in the audit record as the authoritative
    # identity for any shortened filename.
    return safe_stem[:80] + suffix


def main() -> int:
    """Run the local pilot connector from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--authority-level", choices=["county", "district"])
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--unattempted-registered", action="store_true")
    parser.add_argument("--max-links", type=int, default=25)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", type=float, default=1.0)
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    summary = download_pilot_sources(
        args.root,
        authority_level=args.authority_level,
        source_ids=set(args.source_id),
        dry_run=args.dry_run,
        unattempted_registered=args.unattempted_registered,
        max_links_per_source=args.max_links,
        max_pages_per_source=args.max_pages,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        retry_delay_seconds=args.retry_delay_seconds,
        retry_failed=args.retry_failed,
    )
    print(summary.model_dump_json(indent=2))
    return 0 if summary.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
