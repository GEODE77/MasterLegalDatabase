"""Tests for Colorado session-law acquisition."""

from __future__ import annotations

import json
from pathlib import Path

from geode.connectors.session_laws import parse_session_law_page, write_session_laws_dataset
from geode.schemas.models import SessionLaw


SESSION_LAWS_HTML = """
<h2>Session Laws from the 2026 Regular Session</h2>
<table>
  <tbody>
    <tr class='mb-0' role="row">
      <td data-label="Measure">
        <span><a href="/bills/HB26-1177">HB26-1177<br>End Nursing Provider Payments</a></span>
      </td>
      <td data-label="Effective Date"><span>02/27/2026</span></td>
      <td data-label="Page #"><span>1</span></td>
      <td data-label="Chapter #"><span>1</span></td>
      <td data-label="Chapter Text">
        <span><a href="/laws/session-laws/HB26-1177/1/download">PDF</a></span>
      </td>
    </tr>
  </tbody>
</table>
"""


def test_parse_session_law_page_extracts_official_table_row() -> None:
    """The parser extracts chapter, bill, title, date, and PDF URL."""

    rows = parse_session_law_page(SESSION_LAWS_HTML, "https://leg.colorado.gov/laws/session-laws")

    assert len(rows) == 1
    assert rows[0].entity_id == "SL-2026-1"
    assert rows[0].bill_id == "HB26-1177"
    assert rows[0].chapter == "1"
    assert str(rows[0].source_url).endswith("/laws/session-laws/HB26-1177/1/download")


def test_session_law_allows_future_effective_date() -> None:
    """A future effective date can be valid enacted-law data."""

    law = SessionLaw(
        id="SL-2026-2",
        session_year="2026",
        chapter="2",
        bill_id="SB26-010",
        title="Agricultural Property Tax Definitions",
        effective_date="2027-01-01",
        statutes_affected=[],
        summary="SB26-010: Agricultural Property Tax Definitions",
        subject_tags=[],
        source_url="https://leg.colorado.gov/laws/session-laws/SB26-010/2/download",
        confidence={"overall": 0.82},
    )

    assert law.effective_date.isoformat() == "2027-01-01"


def test_write_session_laws_dataset_uses_page_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The writer creates layer outputs and manifest updates from official page HTML."""

    _write_manifest(tmp_path)

    class Response:
        text = SESSION_LAWS_HTML
        content = SESSION_LAWS_HTML.encode()

        def raise_for_status(self) -> None:
            return None

    def fake_get(*args, **kwargs):  # noqa: ANN002, ANN003
        return Response()

    monkeypatch.setattr("geode.connectors.session_laws.requests.get", fake_get)

    summary = write_session_laws_dataset(tmp_path, max_pages=1)

    assert summary.record_count == 1
    assert (tmp_path / "06_Session_Laws" / "_index.jsonl").exists()
    manifest = json.loads((tmp_path / "_CONTROL_PLANE" / "MASTER_MANIFEST.json").read_text())
    layer = next(item for item in manifest["data_layers"] if item["id"] == "06_Session_Laws")
    assert layer["status"] == "ready"
    assert layer["record_count"] == 1


def _write_manifest(root: Path) -> None:
    """Write a manifest with a session-law layer."""

    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True, exist_ok=True)
    payload = {
        "data_layers": [
            {
                "id": "06_Session_Laws",
                "record_count": 0,
                "status": "empty",
            }
        ]
    }
    (control / "MASTER_MANIFEST.json").write_text(json.dumps(payload), encoding="utf-8")
