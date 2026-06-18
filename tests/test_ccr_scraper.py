"""CCR scraper connector tests with mocked HTTP responses."""

from __future__ import annotations

import logging
from pathlib import Path

from geode.connectors.ccr_scraper import (
    CCR_DEPARTMENT_LIST_URL,
    CCRRuleEntry,
    discover_all_rules,
    download_all_rules,
    download_rule,
    resolve_rule_info_page,
)
from geode.utils.file_io import iter_jsonl

AGENCY_URL = (
    "https://www.sos.state.co.us/CCR/NumericalCCRDocList.do?"
    "agencyID=7&agencyName=1001+Air+Quality+Control+Commission&deptID=16&"
    "deptName=1000+Department+of+Public+Health+and+Environment"
)


class FakeResponse:
    """Small fake HTTP response."""

    def __init__(self, text: str = "", content: bytes = b"", status_code: int = 200) -> None:
        """Create a fake response."""

        self.text = text
        self.content = content or text.encode("utf-8")
        self.status_code = status_code

    def raise_for_status(self) -> None:
        """Raise on HTTP errors."""

        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    """Map URLs to fake responses."""

    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        """Create a fake HTTP client."""

        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str) -> FakeResponse:
        """Return a fake response for a URL."""

        self.calls.append(url)
        return self.responses[url]


def _agency_html() -> str:
    """Return an agency page with five downloadable rules."""

    links = []
    for suffix in range(9, 14):
        ccr = f"5 CCR 1001-{suffix}"
        encoded = ccr.replace(" ", "%20")
        links.append(
            f'<a href="/CCR/GenerateRulePdf.do?rule={encoded}">{ccr} PDF</a>'
        )
        links.append(
            f'<a href="/CCR/GenerateRuleDoc.do?rule={encoded}">{ccr} DOCX</a>'
        )
    return "<html><body>" + "".join(links) + "</body></html>"


def _fake_client() -> FakeClient:
    """Return a fake client with browse and document responses."""

    department_html = (
        '<a href="/CCR/NumericalCCRDocList.do?agencyID=7&'
        'agencyName=1001+Air+Quality+Control+Commission&deptID=16&'
        'deptName=1000+Department+of+Public+Health+and+Environment">'
        "1001 Air Quality Control Commission</a>"
    )
    responses = {
        CCR_DEPARTMENT_LIST_URL: FakeResponse(text=department_html),
        AGENCY_URL: FakeResponse(text=_agency_html()),
    }
    for suffix in range(9, 14):
        ccr = f"5%20CCR%201001-{suffix}"
        responses[
            f"https://www.sos.state.co.us/CCR/GenerateRulePdf.do?rule={ccr}"
        ] = FakeResponse(content=f"%PDF-1.7\npdf-{suffix}".encode("utf-8"))
        responses[
            f"https://www.sos.state.co.us/CCR/GenerateRuleDoc.do?rule={ccr}"
        ] = FakeResponse(content=b"PK\x03\x04" + f"docx-{suffix}".encode("utf-8"))
    return FakeClient(responses)


def test_discover_all_rules_from_one_department() -> None:
    """Discovery catalogs five rules from a mocked agency page."""

    entries = discover_all_rules(client=_fake_client(), max_agencies=1)
    assert len(entries) == 5
    assert entries[0].ccr_number == "5 CCR 1001-9"
    assert entries[0].department == "1000 Department of Public Health and Environment"
    assert entries[0].docx_url is not None
    assert entries[0].pdf_url is not None


def test_discover_all_rules_resolves_live_style_rule_info_links(caplog) -> None:
    """Discovery resolves current SOS agency-page rule-info links to downloads."""

    caplog.set_level(logging.INFO)
    rule_info_url = (
        "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2341"
        "&seriesNum=5%20CCR%201001-9"
    )
    department_html = (
        f'<a href="{AGENCY_URL.replace("https://www.sos.state.co.us", "")}">'
        "1001 Air Quality Control Commission</a>"
    )
    agency_html = (
        '<a href="/CCR/DisplayRule.do?action=ruleinfo&ruleId=2341'
        '&seriesNum=5%20CCR%201001-9">5 CCR 1001-9</a>'
    )
    rule_info_html = (
        '<a href="javascript:void(0)">06/15/2025 (PDF)</a>'
        '<a href="javascript:void(0)">06/15/2025 (DOCX)</a>'
        "OpenRuleWindow('12486', '5 CCR 1001-9')"
        "OpenRuleWordVersion('12486', '5 CCR 1001-9')"
    )
    client = FakeClient(
        {
            CCR_DEPARTMENT_LIST_URL: FakeResponse(text=department_html),
            AGENCY_URL: FakeResponse(text=agency_html),
            rule_info_url: FakeResponse(text=rule_info_html),
        }
    )

    entries = discover_all_rules(client=client, max_agencies=1)

    assert len(entries) == 1
    assert entries[0].ccr_number == "5 CCR 1001-9"
    assert "ruleVersionId=12486" in str(entries[0].docx_url)
    assert "type=word" in entries[0].preferred_url
    log_messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "raw_rule_candidates=1" in log_messages
    assert "downloadable_rule_candidates=1" in log_messages


def test_resolve_rule_info_page_prefers_docx() -> None:
    """Rule-info pages resolve DOCX and PDF links without CCR text in anchors."""

    source_url = "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2337"
    html = (
        '<a href="/CCR/GenerateRulePdf.do?ruleId=2337">PDF</a>'
        '<a href="/CCR/GenerateRuleDoc.do?ruleId=2337">DOCX</a>'
    )
    client = FakeClient({source_url: FakeResponse(text=html)})
    entry = resolve_rule_info_page(
        {
            "ccr_number": "5 CCR 1001-5",
            "canonical_id": "5_CCR_1001-5",
            "department": "Department of Public Health and Environment",
            "department_code": "1000",
            "agency": "Air Quality Control Commission",
            "source_page_url": source_url,
        },
        client=client,
    )
    assert entry.docx_url is not None
    assert entry.pdf_url is not None
    assert "GenerateRulePdf.do" in entry.preferred_url


def test_resolve_rule_info_page_uses_pdf_fallback() -> None:
    """Rule-info pages remain downloadable when only a PDF link is present."""

    source_url = "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=3217"
    html = '<a href="/CCR/GenerateRulePdf.do?ruleId=3217">PDF</a>'
    client = FakeClient({source_url: FakeResponse(text=html)})
    entry = resolve_rule_info_page(
        {
            "ccr_number": "7 CCR 1103-1",
            "department": "Department of Labor and Employment",
            "agency": "Division of Labor Standards and Statistics",
            "source_page_url": source_url,
        },
        client=client,
    )
    assert entry.docx_url is None
    assert entry.pdf_url is not None
    assert "GenerateRulePdf.do" in entry.preferred_url


def test_resolve_rule_info_page_parses_live_javascript_downloads() -> None:
    """Live SOS rule pages expose downloads through OpenRule JavaScript calls."""

    source_url = "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=3154"
    html = (
        '<a href="javascript:void(0)">06/15/2025 (PDF)</a>'
        '<a href="javascript:void(0)">06/15/2025 (DOCX)</a>'
        "OpenRuleWindow('11979', '5 CCR 1002-43' )"
        "OpenRuleWordVersion('11979', '5 CCR 1002-43' )"
    )
    client = FakeClient({source_url: FakeResponse(text=html)})
    entry = resolve_rule_info_page(
        {
            "ccr_number": "5 CCR 1002-43",
            "department": "Department of Public Health and Environment",
            "agency": "Water Quality Control Commission",
            "source_page_url": source_url,
        },
        client=client,
    )
    assert entry.pdf_url is not None
    assert entry.docx_url is not None
    assert "ruleVersionId=11979" in str(entry.pdf_url)
    assert "fileName=5%20CCR%201002-43" in str(entry.docx_url)
    assert "type=pdf" in entry.preferred_url


def test_download_rule_prefers_pdf_and_resumes(tmp_path: Path) -> None:
    """Downloads prefer PDF, log SHA-256, and skip when manifest hash matches."""

    client = _fake_client()
    entry = discover_all_rules(client=client, max_agencies=1)[0]
    path = download_rule(entry, tmp_path, client=client)
    assert path.suffix == ".pdf"
    assert path.read_bytes() == b"%PDF-1.7\npdf-9"
    rows = list(iter_jsonl(tmp_path / "download_manifest.jsonl"))
    assert rows[0]["jurisdiction"] == "Colorado"
    assert rows[0]["source_type"] == "regulation_rule"
    assert rows[0]["document_id"] == "5_CCR_1001-9"
    assert rows[0]["document_name"] == "5 CCR 1001-9"
    assert rows[0]["department"] == "1000 Department of Public Health and Environment"
    assert rows[0]["agency"] == "1001 Air Quality Control Commission"
    assert rows[0]["source_format"] == "pdf"
    assert rows[0]["status"] == "downloaded"
    assert rows[0]["sha256"]
    assert rows[0]["missing_metadata"] == ["effective_date", "publication_date"]

    before = client.calls.count(str(entry.pdf_url))
    assert download_rule(entry, tmp_path, client=client) == path
    after = client.calls.count(str(entry.pdf_url))
    assert after == before


def test_download_rule_manifest_urls_are_not_html_encoded(tmp_path: Path) -> None:
    """Manifest source URLs store canonical query separators."""

    source_page_url = (
        "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo"
        "&amp;amp;ruleId=2341&amp;seriesNum=5%20CCR%201001-9"
    )
    pdf_url = (
        "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=12486"
        "&amp;amp;fileName=5%20CCR%201001-9&amp;type=pdf"
    )
    entry = CCRRuleEntry(
        ccr_number="5 CCR 1001-9",
        department="1000 Department of Public Health and Environment",
        agency="1001 Air Quality Control Commission",
        source_page_url=source_page_url,
        pdf_url=pdf_url,
    )
    client = FakeClient({str(entry.pdf_url): FakeResponse(content=b"%PDF-1.7\npdf")})

    download_rule(entry, tmp_path, client=client)
    raw_manifest = (tmp_path / "download_manifest.jsonl").read_text(encoding="utf-8")
    row = list(iter_jsonl(tmp_path / "download_manifest.jsonl"))[0]

    assert "&amp;" not in raw_manifest
    assert row["source_url"] == (
        "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=12486"
        "&fileName=5%20CCR%201001-9&type=pdf"
    )
    assert row["source_page_url"] == (
        "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo"
        "&ruleId=2341&seriesNum=5%20CCR%201001-9"
    )


def test_download_all_rules_downloads_five_samples(tmp_path: Path) -> None:
    """Batch download discovers and downloads five mocked CCR samples."""

    report = download_all_rules(tmp_path, delay=0, client=_fake_client())
    assert report.discovered == 5
    assert report.downloaded == 5
    assert report.failed == 0
    assert len(list(iter_jsonl(tmp_path / "download_manifest.jsonl"))) == 5


def test_download_all_rules_redownloads_unmanifested_partial_file(tmp_path: Path) -> None:
    """Existing files without matching manifest rows are not treated as complete."""

    client = _fake_client()
    entry = discover_all_rules(client=client, max_agencies=1)[0]
    target = tmp_path / f"{entry.canonical_id}.pdf"
    target.write_bytes(b"partial")

    report = download_all_rules(tmp_path, delay=0, client=client)

    assert report.downloaded == 5
    assert report.skipped == 0
    assert target.read_bytes() == b"%PDF-1.7\npdf-9"
