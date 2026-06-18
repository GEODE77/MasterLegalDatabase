"""LegiScan client and transformer tests."""

from __future__ import annotations

import json
from pathlib import Path

from geode.connectors.legiscan_client import (
    download_all_sessions,
    get_bill_detail,
    get_session_bills,
    get_session_list,
)
from geode.connectors.legiscan_transformer import transform_bill
from geode.schemas.validators import validate_record
from geode.utils.file_io import iter_jsonl, load_json


class FakeResponse:
    """Fake JSON response."""

    def __init__(self, payload: dict) -> None:
        """Create a fake response."""

        self.payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict:
        """Return fake JSON payload."""

        return self.payload

    def raise_for_status(self) -> None:
        """No-op for successful fake responses."""


class FakeClient:
    """Fake LegiScan API client keyed by operation."""

    def __init__(self, bill_fixture: dict, fail_get_bill_attempts: int = 0) -> None:
        """Create fake client with one bill fixture."""

        self.bill_fixture = bill_fixture
        self.fail_get_bill_attempts = fail_get_bill_attempts
        self.calls: list[str] = []

    def get(self, url: str, params: dict) -> FakeResponse:
        """Return operation-specific fake responses."""

        self.calls.append(str(params["op"]))
        operation = params["op"]
        if operation == "getSessionList":
            return FakeResponse(
                {
                    "sessions": [
                        {
                            "session_id": 2023,
                            "state_id": 6,
                            "year_start": 2023,
                            "year_end": 2023,
                            "session_name": "2023 Regular Session",
                        }
                    ]
                }
            )
        if operation == "getMasterList":
            return FakeResponse(
                {
                    "masterlist": {
                        "session": {"session_id": 2023},
                        "0": {
                            "bill_id": 12345,
                            "number": "SB 16",
                            "title": "Air Quality Control Amendments",
                        },
                    }
                }
            )
        if self.fail_get_bill_attempts:
            self.fail_get_bill_attempts -= 1
            raise RuntimeError("temporary getBill failure")
        return FakeResponse(self.bill_fixture)


def test_legiscan_client_uses_injected_client(
    legiscan_fixture_path: Path,
) -> None:
    """Client functions work with mocked API responses and no env key."""

    fixture = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    client = FakeClient(fixture)
    sessions = get_session_list(api_key="test", client=client)
    bills = get_session_bills(sessions[0].session_id, api_key="test", client=client)
    detail = get_bill_detail(bills[0].bill_id, api_key="test", client=client)
    assert sessions[0].year_start == 2023
    assert bills[0].number == "SB 16"
    assert detail.raw["number"] == "SB 16"
    assert client.calls == ["getSessionList", "getMasterList", "getBill"]


def test_transform_bill_fixture_validates(
    legiscan_fixture_path: Path,
    project_root: Path,
) -> None:
    """Transformer maps sample LegiScan JSON into a valid Geode bill record."""

    raw_bill = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    ontology = load_json(project_root / "_CONTROL_PLANE" / "ONTOLOGY.json")
    record = transform_bill(raw_bill, ontology)
    valid, errors = validate_record(record)
    assert valid, errors
    assert record["id"] == "SB23-016"
    assert record["statutes_amended"] == ["CRS-25-7-109"]
    assert "air_quality" in record["subject_tags"]


def test_legiscan_download_all_sessions_resumes_without_duplicate_get_bill(
    legiscan_fixture_path: Path,
    tmp_path: Path,
) -> None:
    """Manifest-backed LegiScan reruns skip already archived bill JSON."""

    fixture = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    client = FakeClient(fixture)

    first = download_all_sessions(tmp_path, api_key="test", client=client, delay=0)
    get_bill_calls = client.calls.count("getBill")
    second = download_all_sessions(tmp_path, api_key="test", client=client, delay=0)

    assert first.bills == 1
    assert first.skipped == 0
    assert second.bills == 1
    assert second.skipped == 1
    assert client.calls.count("getBill") == get_bill_calls
    assert client.calls.count("getSessionList") == 2
    assert len(list(iter_jsonl(tmp_path / "download_manifest.jsonl"))) == 1


def test_legiscan_max_downloads_caps_get_bill_calls(
    legiscan_fixture_path: Path,
    tmp_path: Path,
) -> None:
    """LegiScan capped runs avoid bill-detail calls until allowed."""

    fixture = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    client = FakeClient(fixture)

    capped = download_all_sessions(
        tmp_path,
        api_key="test",
        client=client,
        delay=0,
        max_downloads=0,
    )
    get_bill_after_cap = client.calls.count("getBill")
    resumed = download_all_sessions(
        tmp_path,
        api_key="test",
        client=client,
        delay=0,
        max_downloads=1,
    )

    assert capped.attempted == 0
    assert capped.bills == 0
    assert get_bill_after_cap == 0
    assert client.calls.count("getBill") == 1
    assert resumed.attempted == 1
    assert resumed.bills == 1


def test_legiscan_failed_bill_is_recorded_and_retried(
    legiscan_fixture_path: Path,
    tmp_path: Path,
) -> None:
    """Failed LegiScan bill attempts are retained and retried on the next run."""

    fixture = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    client = FakeClient(fixture, fail_get_bill_attempts=1)

    first = download_all_sessions(tmp_path, api_key="test", client=client, delay=0)
    second = download_all_sessions(tmp_path, api_key="test", client=client, delay=0)
    rows = list(iter_jsonl(tmp_path / "download_manifest.jsonl"))

    assert first.bills == 0
    assert first.failed == 1
    assert "temporary getBill failure" in first.errors[0]
    assert second.bills == 1
    assert second.failed == 0
    assert [row["status"] for row in rows] == ["failed", "downloaded"]
    assert rows[0]["jurisdiction"] == "Colorado"
    assert rows[0]["source_type"] == "bill"
    assert rows[0]["document_id"] == "12345"
    assert rows[0]["document_name"] == "Air Quality Control Amendments"
    assert rows[0]["source_format"] == "json"
    assert rows[0]["missing_metadata"] == []
    assert rows[1]["jurisdiction"] == "Colorado"
    assert rows[1]["source_type"] == "bill"
    assert rows[1]["document_id"] == "12345"
    assert rows[1]["source_format"] == "json"
