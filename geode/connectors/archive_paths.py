"""Canonical raw-archive path helpers for source connectors."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

DOWNLOAD_MANIFEST_NAME = "download_manifest.jsonl"
FAILURE_MANIFEST_NAME = "download_failures.jsonl"

RAW_CONNECTOR_DIRS = {
    "ccr": "ccr",
    "legiscan": "legiscan",
    "colorado_register": "register",
    "register": "register",
    "edocket": "edocket",
    "executive_orders": "exec_orders",
    "exec_orders": "exec_orders",
    "coprrr": "supplementary/coprrr",
    "ag_opinions": "supplementary/ag_opinions",
}


def raw_connector_dir(raw_root: Path, connector: str) -> Path:
    """Return the canonical raw archive directory for a connector name."""

    return raw_root / RAW_CONNECTOR_DIRS.get(connector, connector)


def download_manifest_path(archive_dir: Path) -> Path:
    """Return the canonical download manifest path for one archive directory."""

    return archive_dir / DOWNLOAD_MANIFEST_NAME


def failure_manifest_path(archive_dir: Path) -> Path:
    """Return the canonical failed-download manifest path for one archive directory."""

    return archive_dir / FAILURE_MANIFEST_NAME


def temp_path_for(target: Path) -> Path:
    """Return the adjacent temporary path used before atomic replacement."""

    return target.with_name(f"{target.name}.tmp")


def ccr_rule_document_path(
    archive_dir: Path,
    canonical_id: str,
    preferred_extension: str,
) -> Path:
    """Return the raw archive path for one CCR rule document."""

    stem = safe_archive_stem(canonical_id)
    suffix = _normalized_extension(preferred_extension)
    return archive_dir / f"{stem}{suffix}"


def register_publication_path(
    archive_dir: Path,
    publication_date: str,
    source_url: str,
) -> Path:
    """Return the raw archive path for one Colorado Register publication."""

    stem = safe_archive_stem(publication_date)
    suffix = url_suffix(source_url, ".html")
    if suffix == ".do":
        suffix = ".html"
    return archive_dir / f"register_{stem}{suffix}"


def executive_order_pdf_path(archive_dir: Path, entity_id: str) -> Path:
    """Return the raw archive path for one executive order PDF."""

    return archive_dir / f"{safe_archive_stem(entity_id)}.pdf"


def legiscan_bill_json_path(archive_dir: Path, session_year: int, bill_id: int) -> Path:
    """Return the raw archive path for one LegiScan bill JSON object."""

    return archive_dir / str(session_year) / f"{bill_id}.json"


def url_suffix(source_url: str, default: str) -> str:
    """Return a URL path suffix, ignoring query strings and fragments."""

    suffix = Path(urlparse(source_url).path).suffix
    return _normalized_extension(suffix or default)


def safe_archive_stem(value: str) -> str:
    """Return a filesystem-safe archive filename stem."""

    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "source"


def _normalized_extension(extension: str) -> str:
    """Normalize a filesystem extension to a lower-case dotted suffix."""

    suffix = extension.strip().lower()
    if not suffix:
        return ""
    return suffix if suffix.startswith(".") else f".{suffix}"
