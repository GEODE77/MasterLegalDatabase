"""LegiScan client and transformer tests."""

from __future__ import annotations

import json
from pathlib import Path

from geode.connectors.legiscan_client import (
    get_bill_detail,
    get_session_bills,
    get_session_list,
)
from geode.connectors.legiscan_transformer import transform_bill
from geode.schemas.validators import validate_record
from geode.utils.file_io import load_json


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

    def __init__(self, bill_fixture: dict) -> None:
        """Create fake client with one bill fixture."""

        self.bill_fixture = bill_fixture
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
