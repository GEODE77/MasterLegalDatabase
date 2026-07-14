"""Tests for the Geode API access layer."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from geode.api.admin import create_key_record, deactivate_key_record, list_key_records
from geode.api.admin import rotate_key_record
from geode.api.auth import ApiAuthError, ApiPrincipal, authenticate_api_key, create_api_key_hash
from geode.api.exports import create_export
from geode.api.logging import log_usage, usage_log_path
from geode.api.rate_limit import ApiRateLimitError, check_rate_limit
from geode.api.store import GeodeDataStore
from geode.utils.file_io import atomic_write_json


def test_authenticates_hashed_api_key(project_root: Path) -> None:
    """A raw key authenticates against its stored hash."""

    key_file = _write_key_file(project_root, "local test key")

    principal = authenticate_api_key("local test key", key_file, "manifest:read")

    assert principal.key_id == "test-key"
    assert principal.has_scope("manifest:read")


def test_rejects_missing_scope(project_root: Path) -> None:
    """A valid key cannot use a missing permission."""

    key_file = _write_key_file(project_root, "local test key", scopes=["manifest:read"])

    with pytest.raises(ApiAuthError) as exc_info:
        authenticate_api_key("local test key", key_file, "exports:create")

    assert exc_info.value.status_code == 403


def test_reads_one_statute_section(project_root: Path) -> None:
    """The statute lookup returns the indexed row and only the requested section."""

    _write_statute_fixture(project_root)
    store = GeodeDataStore(project_root)

    response = store.get_statute("CRS-1-1-101")

    assert response["id"] == "CRS-1-1-101"
    assert "Short title." in response["content"]
    assert "Applicability." not in response["content"]


def test_reads_one_normalized_regulation(project_root: Path) -> None:
    """The regulation lookup returns normalized JSON content."""

    _write_regulation_fixture(project_root)
    store = GeodeDataStore(project_root)

    response = store.get_regulation("1_CCR_101-1")

    assert response["id"] == "1_CCR_101-1"
    assert response["content"]["ccr_citation"] == "1 CCR 101-1"
    assert response["content_kind"] == "json"


def test_searches_layer_indexes(project_root: Path) -> None:
    """Search scans lightweight indexes instead of the full corpus."""

    _write_statute_fixture(project_root)
    store = GeodeDataStore(project_root)

    response = store.search("short title", layers=["01_Statutes_CRS"])

    assert response["count"] == 1
    assert response["results"][0]["id"] == "CRS-1-1-101"


def test_creates_export_without_raw_archive(project_root: Path) -> None:
    """Bulk export includes validated files and excludes raw archive files."""

    _write_statute_fixture(project_root)
    (project_root / "_CROSSWALKS" / "statute_to_regulation.jsonl").write_text(
        '{"source_id":"CRS-1-1-101","target_id":"1_CCR_101-1"}\n',
        encoding="utf-8",
    )
    (project_root / "_RAW_ARCHIVE" / "crs" / "source.txt").write_text("raw", encoding="utf-8")
    principal = _bulk_principal(project_root)

    result = create_export(project_root, principal, layers=["01_Statutes_CRS"])

    with zipfile.ZipFile(result.path) as archive:
        names = set(archive.namelist())
    assert "01_Statutes_CRS/_index.jsonl" in names
    assert "01_Statutes_CRS/crs_title_01.md" in names
    assert "_CROSSWALKS/statute_to_regulation.jsonl" in names
    assert not any(name.startswith("_RAW_ARCHIVE/") for name in names)


def test_logs_usage(project_root: Path) -> None:
    """Usage logging appends a JSONL audit row."""

    principal = _bulk_principal(project_root)

    log_usage(project_root, principal, "GET", "/v1/manifest", 200)

    rows = [json.loads(line) for line in usage_log_path(project_root).read_text().splitlines()]
    assert rows[0]["key_id"] == "test-key"
    assert rows[0]["route"] == "/v1/manifest"


def test_admin_creates_key_and_stores_only_hash(project_root: Path) -> None:
    """Admin key creation returns the raw key once and saves only its hash."""

    result = create_key_record(
        project_root,
        key_id="partner-key",
        label="Partner key",
        raw_key="local partner key",
    )

    saved_text = result.key_file.read_text(encoding="utf-8")
    principal = authenticate_api_key("local partner key", result.key_file, "manifest:read")
    assert principal.key_id == "partner-key"
    assert result.raw_key == "local partner key"
    assert "local partner key" not in saved_text
    assert "sha256:" in saved_text


def test_admin_lists_keys_without_secret_hash(project_root: Path) -> None:
    """Admin listing returns review-safe key details."""

    created_at = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    create_key_record(
        project_root,
        key_id="partner-key",
        label="Partner key",
        raw_key="local partner key",
        created_by="jp",
        now=created_at,
    )

    records = list_key_records(project_root)

    assert records[0]["key_id"] == "partner-key"
    assert records[0]["label"] == "Partner key"
    assert records[0]["active"] is True
    assert records[0]["scopes"] == [
        "manifest:read",
        "statutes:read",
        "regulations:read",
        "search:read",
    ]
    assert records[0]["created_by"] == "jp"
    assert records[0]["created_at"] == "2026-07-14T12:00:00+00:00"
    assert "key_hash" not in records[0]


def test_admin_deactivates_key(project_root: Path) -> None:
    """Admin deactivation shuts off access without deleting the key record."""

    result = create_key_record(
        project_root,
        key_id="partner-key",
        label="Partner key",
        raw_key="local partner key",
    )

    record = deactivate_key_record(project_root, "partner-key", reason="No longer needed")

    assert record.active is False
    assert record.deactivation_reason == "No longer needed"
    with pytest.raises(ApiAuthError) as exc_info:
        authenticate_api_key("local partner key", result.key_file, "manifest:read")
    assert exc_info.value.status_code == 403
    assert list_key_records(project_root)[0]["active"] is False


def test_admin_writes_non_secret_admin_log(project_root: Path) -> None:
    """Key admin actions are logged without raw key values."""

    result = create_key_record(
        project_root,
        key_id="partner-key",
        label="Partner key",
        raw_key="local partner key",
        created_by="jp",
    )

    log_path = project_root / "_CONTROL_PLANE" / "API_KEY_ADMIN_LOG.jsonl"
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["action"] == "create_key"
    assert rows[0]["key_id"] == "partner-key"
    assert rows[0]["actor"] == "jp"
    assert result.raw_key not in log_path.read_text(encoding="utf-8")


def test_admin_rejects_unknown_scope(project_root: Path) -> None:
    """Admin key creation refuses permissions outside the known API surface."""

    with pytest.raises(ValueError, match="unknown API scope"):
        create_key_record(
            project_root,
            key_id="partner-key",
            label="Partner key",
            scopes=["unknown:scope"],
        )


def test_admin_rotates_key(project_root: Path) -> None:
    """Key rotation replaces the secret while keeping the same key ID."""

    result = create_key_record(
        project_root,
        key_id="partner-key",
        label="Partner key",
        raw_key="old partner key",
    )

    rotated = rotate_key_record(
        project_root,
        "partner-key",
        raw_key="new partner key",
        reason="Scheduled rotation",
    )

    with pytest.raises(ApiAuthError):
        authenticate_api_key(result.raw_key, result.key_file, "manifest:read")
    principal = authenticate_api_key(rotated.raw_key, rotated.key_file, "manifest:read")
    assert principal.key_id == "partner-key"
    assert rotated.record.rotation_count == 1


def test_rate_limit_blocks_after_allowed_requests(project_root: Path) -> None:
    """A key with a minute limit is blocked after its allowance is used."""

    key_file = _write_key_file(project_root, "local test key", rate_limit_per_minute=1)
    principal = authenticate_api_key("local test key", key_file, "manifest:read")
    now = datetime(2026, 7, 14, 12, 0, 5, tzinfo=timezone.utc)

    check_rate_limit(project_root, principal, now=now)

    with pytest.raises(ApiRateLimitError) as exc_info:
        check_rate_limit(project_root, principal, now=now)
    assert exc_info.value.status_code == 429


def _write_key_file(
    project_root: Path,
    raw_key: str,
    scopes: list[str] | None = None,
    bulk_export_allowed: bool = True,
    rate_limit_per_minute: int | None = 60,
) -> Path:
    """Write a small API key file for tests."""

    key_file = project_root / "_CONTROL_PLANE" / "API_KEYS.json"
    payload = {
        "version": 1,
        "keys": [
            {
                "key_id": "test-key",
                "label": "Test key",
                "key_hash": create_api_key_hash(raw_key),
                "active": True,
                "scopes": scopes
                or [
                    "manifest:read",
                    "statutes:read",
                    "regulations:read",
                    "search:read",
                    "exports:create",
                    "exports:download",
                ],
                "bulk_export_allowed": bulk_export_allowed,
                "rate_limit_per_minute": rate_limit_per_minute,
                "expires_at": None,
            }
        ],
    }
    atomic_write_json(key_file, payload, project_root)
    return key_file


def _bulk_principal(project_root: Path) -> ApiPrincipal:
    """Return a principal with export access."""

    key_file = _write_key_file(project_root, "local test key")
    return authenticate_api_key("local test key", key_file, "exports:create")


def _write_statute_fixture(project_root: Path) -> None:
    """Write a tiny statute layer fixture."""

    layer = project_root / "01_Statutes_CRS"
    layer.mkdir(parents=True, exist_ok=True)
    (layer / "crs_title_01.md").write_text(
        "\n".join(
            [
                "# Title 1 - ELECTIONS",
                "",
                "#### 1-1-101. Short title.",
                "",
                "This section has the short title.",
                "",
                "#### 1-1-102. Applicability.",
                "",
                "This section should not be returned.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (layer / "_index.jsonl").write_text(
        json.dumps(
            {
                "id": "CRS-1-1-101",
                "layer": "01_Statutes_CRS",
                "entity_type": "statute_section",
                "title": "CRS-1-1-101: Short title.",
                "citation": "CRS-1-1-101",
                "path": "01_Statutes_CRS/crs_title_01.md",
                "tags": ["statute", "title_1"],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_regulation_fixture(project_root: Path) -> None:
    """Write a tiny regulation layer fixture."""

    layer = project_root / "02_Regulations_CCR"
    record_dir = layer / "_normalized" / "records"
    record_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        record_dir / "1_CCR_101-1.json",
        {"id": "1_CCR_101-1", "ccr_citation": "1 CCR 101-1"},
        project_root,
    )
    (layer / "_index.jsonl").write_text(
        json.dumps(
            {
                "id": "1_CCR_101-1",
                "layer": "02_Regulations_CCR",
                "entity_type": "regulation_rule",
                "title": "1 CCR 101-1",
                "citation": "1 CCR 101-1",
                "path": "02_Regulations_CCR/_normalized/records/1_CCR_101-1.json",
                "tags": ["ccr"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
