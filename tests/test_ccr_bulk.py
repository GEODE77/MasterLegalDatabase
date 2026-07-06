"""Tests for the phased CCR bulk acquisition workflow."""

from __future__ import annotations

import json
from pathlib import Path

from geode.connectors.ccr_bulk import (
    CCRBulkConfig,
    CCRBulkQueueEvent,
    _fallback_entry,
    _should_attempt_inventory_retrieval,
    build_parser,
    config_from_args,
    run_ccr_bulk,
)
from geode.connectors.ccr_scraper import CCR_DEPARTMENT_LIST_URL, CCRRuleEntry
from geode.utils.file_io import iter_jsonl

AGENCY_URL = (
    "https://www.sos.state.co.us/CCR/NumericalCCRDocList.do?"
    "agencyID=7&agencyName=1001+Air+Quality+Control+Commission&deptID=16&"
    "deptName=1000+Department+of+Public+Health+and+Environment"
)
PDF_9 = "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?rule=5%20CCR%201001-9"
PDF_10 = "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?rule=5%20CCR%201001-10"
DOCX_9 = "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?rule=5%20CCR%201001-9&type=word"


class FakeResponse:
    """Small fake HTTP response."""

    def __init__(
        self,
        text: str = "",
        content: bytes = b"",
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Create a fake response."""

        self.text = text
        self.content = content or text.encode("utf-8")
        self.status_code = status_code
        self.headers = headers or {}


class FakeClient:
    """Map URLs to fake responses."""

    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        """Create a fake client."""

        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str) -> FakeResponse:
        """Return a fake response."""

        self.calls.append(url)
        return self.responses[url]


def _fake_client(include_discovery: bool = True) -> FakeClient:
    """Return a fake CCR browse/download client."""

    responses = {
        PDF_9: FakeResponse(content=b"%PDF-1.7\npdf-9"),
        PDF_10: FakeResponse(content=b"%PDF-1.7\npdf-10"),
    }
    if include_discovery:
        department_html = (
            '<a href="/CCR/NumericalCCRDocList.do?agencyID=7&'
            'agencyName=1001+Air+Quality+Control+Commission&deptID=16&'
            'deptName=1000+Department+of+Public+Health+and+Environment">'
            "1001 Air Quality Control Commission</a>"
        )
        agency_html = (
            '<a href="/CCR/GenerateRulePdf.do?rule=5%20CCR%201001-9">'
            "5 CCR 1001-9 PDF</a>"
            '<a href="/CCR/GenerateRulePdf.do?rule=5%20CCR%201001-10">'
            "5 CCR 1001-10 PDF</a>"
        )
        responses[CCR_DEPARTMENT_LIST_URL] = FakeResponse(text=department_html)
        responses[AGENCY_URL] = FakeResponse(text=agency_html)
    return FakeClient(responses)


def test_ccr_bulk_discovery_only_writes_resolved_queue(tmp_path: Path) -> None:
    """Discovery-only runs build a queue without downloading document content."""

    summary = run_ccr_bulk(
        CCRBulkConfig(
            output_root=tmp_path,
            max_items=2,
            resume=False,
            discovery_only=True,
            discovery_delay=0,
            discovery_delay_jitter_seconds=0,
            client=_fake_client(),
        )
    )
    queue_rows = list(iter_jsonl(Path(summary.queue_path)))

    assert summary.status == "completed"
    assert summary.queue_items_total == 2
    assert summary.indexed == 2
    assert summary.resolved == 2
    assert summary.attempted == 0
    assert [row["status"] for row in queue_rows] == [
        "discovered",
        "discovered",
        "resolved",
        "resolved",
    ]
    assert {row["browse_source_url"] for row in queue_rows} == {AGENCY_URL}
    inventory_rows = list(iter_jsonl(Path(summary.inventory_manifest_path)))
    assert Path(summary.inventory_manifest_path).exists()
    assert summary.inventory_rows_total == 2
    assert summary.inventory_download_targets == 2
    assert inventory_rows[0]["manifest_row_id"] == "5_CCR_1001-9:current:pdf"
    assert inventory_rows[0]["department_id"] == "16"
    assert inventory_rows[0]["agency_id"] == "7"
    assert inventory_rows[0]["browse_source_url"] == AGENCY_URL
    assert inventory_rows[0]["download_url"] == PDF_9
    assert inventory_rows[0]["asset_scope"] == "current"
    assert inventory_rows[0]["asset_format"] == "pdf"
    assert inventory_rows[0]["is_preferred_asset"] is True
    quality = json.loads(Path(summary.inventory_quality_path).read_text(encoding="utf-8"))
    assert quality["traversal_validation_status"] == "capped_run"
    assert quality["field_population_status"] == "rule_id_gaps_detected"
    assert quality["run_capped_by_max_items"] is True
    assert quality["field_coverage"]["department_id"]["populated"] == 2
    assert quality["field_coverage"]["agency_id"]["populated"] == 2
    assert quality["field_coverage"]["asset_format"]["populated"] == 2
    assert quality["field_coverage"]["download_url"]["populated"] == 2
    assert quality["field_coverage"]["rule_id"]["missing"] == 2
    assert summary.traversal_validation_status == "capped_run"
    assert summary.field_population_status == "rule_id_gaps_detected"
    assert Path(summary.dataset_jsonl_path or "").exists()
    assert Path(summary.tagged_jsonl_path or "").exists()
    assert Path(summary.tagged_csv_path or "").exists()
    assert Path(summary.tag_summary_path or "").exists()
    assert summary.tagged_records_total == 2
    assert summary.tagged_total == 2
    assert Path(summary.normalized_index_path or "").exists()
    assert Path(summary.normalized_meta_path or "").exists()
    assert len(list(iter_jsonl(Path(summary.normalized_index_path or "")))) == 2
    assert not Path(summary.manifest_path).exists()


def test_ccr_bulk_resume_retrieves_existing_resolved_queue(tmp_path: Path) -> None:
    """Resume mode can retrieve a previously resolved queue item."""

    first = run_ccr_bulk(
        CCRBulkConfig(
            output_root=tmp_path,
            max_items=1,
            resume=False,
            discovery_only=True,
            discovery_delay=0,
            discovery_delay_jitter_seconds=0,
            client=_fake_client(),
        )
    )
    second = run_ccr_bulk(
        CCRBulkConfig(
            output_root=tmp_path,
            max_items=1,
            resume=True,
            discovery_only=False,
            download_delay=0,
            download_delay_jitter_seconds=0,
            client=_fake_client(include_discovery=False),
        )
    )
    queue_rows = list(iter_jsonl(Path(second.queue_path)))
    summary_payload = json.loads(Path(second.summary_path).read_text(encoding="utf-8"))

    assert first.queue_items_total == 1
    assert second.downloaded == 1
    assert queue_rows[-1]["status"] == "downloaded"
    assert list(iter_jsonl(Path(second.manifest_path)))[0]["document_id"] == "5_CCR_1001-9"
    inventory_rows = list(iter_jsonl(Path(second.inventory_manifest_path)))
    assert inventory_rows[0]["queue_status"] == "downloaded"
    assert summary_payload["downloaded"] == 1
    assert summary_payload["inventory_download_targets"] == 1
    assert summary_payload["inventory_quality_path"] == second.inventory_quality_path
    assert summary_payload["normalized_records_total"] == 1
    assert len(list(iter_jsonl(Path(second.normalized_meta_path or "")))) == 1


def test_ccr_bulk_updates_master_manifest_after_completed_refresh(tmp_path: Path) -> None:
    """Completed CCR refreshes update the main layer status."""

    control = tmp_path / "_CONTROL_PLANE"
    control.mkdir()
    manifest_path = control / "MASTER_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {
                "data_layers": [
                    {
                        "id": "02_Regulations_CCR",
                        "record_count": 0,
                        "last_checked": "2026-06-23",
                        "last_ingested": "2026-06-23",
                        "status": "fixture_ready",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    summary = run_ccr_bulk(
        CCRBulkConfig(
            output_root=tmp_path,
            resume=False,
            discovery_delay=0,
            discovery_delay_jitter_seconds=0,
            download_delay=0,
            download_delay_jitter_seconds=0,
            client=_fake_client(),
        )
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    layer = payload["data_layers"][0]

    assert layer["record_count"] == 2
    assert layer["last_checked"] == summary.completed_at.date().isoformat()
    assert layer["last_ingested"] == summary.completed_at.date().isoformat()
    assert layer["status"] == "ready"


def test_ccr_bulk_inventory_quality_flags_uncapped_discovery(
    tmp_path: Path,
) -> None:
    """Inventory QA identifies uncapped completed discovery runs."""

    summary = run_ccr_bulk(
        CCRBulkConfig(
            output_root=tmp_path,
            resume=False,
            discovery_only=True,
            discovery_delay=0,
            discovery_delay_jitter_seconds=0,
            client=_fake_client(),
        )
    )
    quality = json.loads(Path(summary.inventory_quality_path).read_text(encoding="utf-8"))

    assert summary.queue_items_total == 2
    assert quality["uncapped_discovery_requested"] is True
    assert quality["uncapped_discovery_completed"] is True
    assert quality["traversal_validation_status"] == "uncapped_discovery_completed"
    assert quality["unique_department_ids_total"] == 1
    assert quality["unique_agency_ids_total"] == 1
    assert quality["unique_rule_series_total"] == 2
    assert quality["download_targets_total"] == 2


def test_ccr_bulk_resume_counts_terminal_items_toward_limit(tmp_path: Path) -> None:
    """Resume does not discover extra work when terminal queued items meet the cap."""

    first = run_ccr_bulk(
        CCRBulkConfig(
            output_root=tmp_path,
            max_items=1,
            resume=False,
            discovery_delay=0,
            discovery_delay_jitter_seconds=0,
            download_delay=0,
            download_delay_jitter_seconds=0,
            client=_fake_client(),
        )
    )
    second_client = _fake_client()
    second = run_ccr_bulk(
        CCRBulkConfig(
            output_root=tmp_path,
            max_items=1,
            resume=True,
            discovery_delay=0,
            discovery_delay_jitter_seconds=0,
            download_delay=0,
            download_delay_jitter_seconds=0,
            client=second_client,
        )
    )

    assert first.queue_items_total == 1
    assert first.downloaded == 1
    assert second.queue_items_total == 1
    assert second.downloaded == 0
    assert second.skipped_existing == 0
    assert CCR_DEPARTMENT_LIST_URL not in second_client.calls


def test_failed_content_retrieval_without_archive_is_retryable(tmp_path: Path) -> None:
    """A missing archive after content failure is eligible for resume repair."""

    event = CCRBulkQueueEvent(
        sequence=1,
        timestamp="2026-06-23T00:00:00Z",
        item_id="5_CCR_1001-9",
        status="failed_permanent",
        phase="content_retrieval",
        ccr_number="5 CCR 1001-9",
        department="Department",
        agency="Agency",
        source_page_url=AGENCY_URL,
        archive_path=(tmp_path / "missing.pdf").as_posix(),
    )

    assert _should_attempt_inventory_retrieval(event)


def test_blocked_content_retrieval_is_not_resume_retried(tmp_path: Path) -> None:
    """Blocked outcomes remain terminal instead of being blindly retried."""

    event = CCRBulkQueueEvent(
        sequence=1,
        timestamp="2026-06-23T00:00:00Z",
        item_id="5_CCR_1001-9",
        status="blocked",
        phase="content_retrieval",
        ccr_number="5 CCR 1001-9",
        department="Department",
        agency="Agency",
        source_page_url=AGENCY_URL,
        archive_path=(tmp_path / "missing.pdf").as_posix(),
    )

    assert not _should_attempt_inventory_retrieval(event)


def test_pdf_entry_can_fallback_to_docx() -> None:
    """PDF-preferred entries expose a DOC/DOCX fallback when available."""

    entry = CCRRuleEntry(
        ccr_number="5 CCR 1001-9",
        department="Department",
        agency="Agency",
        source_page_url=AGENCY_URL,
        pdf_url=PDF_9,
        docx_url=DOCX_9,
    )

    fallback = _fallback_entry(entry)

    assert fallback is not None
    assert fallback.pdf_url is None
    assert str(fallback.docx_url) == DOCX_9
    assert fallback.preferred_url == DOCX_9


def test_ccr_bulk_cli_config_exposes_scaling_controls(tmp_path: Path) -> None:
    """The CCR bulk CLI exposes item caps, resume, throttle, and retry controls."""

    parser = build_parser()
    args = parser.parse_args(
        [
            "--output-root",
            str(tmp_path),
            "--max-items",
            "100",
            "--no-resume",
            "--discovery-only",
            "--discovery-delay",
            "0.2",
            "--download-delay",
            "0.5",
            "--http-max-retries",
            "3",
            "--http-retry-jitter-ratio",
            "0",
            "--no-industry-tags",
        ]
    )

    config = config_from_args(args)

    assert config.output_root == tmp_path
    assert config.max_items == 100
    assert config.resume is False
    assert config.discovery_only is True
    assert config.discovery_delay == 0.2
    assert config.download_delay == 0.5
    assert config.max_retries == 3
    assert config.retry_jitter_ratio == 0.0
    assert config.write_industry_tags is False
