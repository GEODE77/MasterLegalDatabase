"""Remaining connector and orchestrator tests."""

from __future__ import annotations

from pathlib import Path

from geode.connectors.crs_parser import parse_crs_sgml, write_crs_sgml_title
from geode.connectors.exec_orders_scraper import (
    discover_executive_orders,
    download_executive_order,
    extract_order_metadata,
)
from geode.connectors.orchestrator import run_full_download
from geode.connectors.register_scraper import (
    discover_publications,
    download_publication,
    extract_rulemaking_notices,
)
from geode.schemas.validators import validate_record


class FakeResponse:
    """Fake HTTP response."""

    def __init__(self, text: str = "", content: bytes = b"", status_code: int = 200) -> None:
        """Create fake response."""

        self.text = text
        self.content = content or text.encode("utf-8")
        self.status_code = status_code

    def raise_for_status(self) -> None:
        """Raise on fake HTTP errors."""

        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    """URL mapping fake client."""

    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        """Create fake client."""

        self.responses = responses

    def get(self, url: str) -> FakeResponse:
        """Return mapped response."""

        return self.responses[url]


def test_register_scraper_processes_sample(tmp_path: Path) -> None:
    """Register connector discovers, downloads, and extracts notices."""

    index_url = "https://www.sos.state.co.us/pubs/CCR/register.html"
    pub_url = "https://www.sos.state.co.us/pubs/CCR/register_2024-01-10.html"
    html = f'<a href="{pub_url}">Colorado Register 2024-01-10</a>'
    notice_text = (
        "NOTICE: adopted | CCR: 5 CCR 1001-9 | Agency: CDPHE_DEPT | "
        "Publication: 2024-01-10 | Hearing: 2023-12-01 | "
        "Effective: 2024-01-15 | Summary: Amendments to air quality permits."
    )
    client = FakeClient(
        {
            index_url: FakeResponse(text=html),
            pub_url: FakeResponse(text=notice_text),
        }
    )
    publications = discover_publications(client=client, index_url=index_url)
    assert len(publications) == 1
    download = download_publication(publications[0], tmp_path, client=client)
    assert Path(download.archive_path).exists()
    notices = extract_rulemaking_notices(notice_text, pub_url)
    valid, errors = validate_record(notices[0])
    assert valid, errors
    assert notices[0]["hearing_date"] == "2023-12-01"


def test_crs_sgml_parser_outputs_markdown_and_metadata(project_root: Path) -> None:
    """CRS SGML parser writes title Markdown and JSONL metadata."""

    sgml_path = project_root / "_RAW_ARCHIVE" / "crs" / "title25.sgml"
    sgml_path.write_text(
        """
        <TITLE number="25" name="Public Health and Environment">
          <ARTICLE number="7" name="Air Quality">
            <PART number="1" name="General">
              <SECTION number="109" heading="Commission">
                The commission has authority under 25-7-109, C.R.S.
              </SECTION>
            </PART>
          </ARTICLE>
        </TITLE>
        """,
        encoding="utf-8",
    )
    document = parse_crs_sgml(sgml_path, "25", 2025)
    assert document.sections[0].id == "CRS-25-7-109"
    outputs = write_crs_sgml_title(project_root, sgml_path, "25", 2025)
    assert project_root / "01_Statutes_CRS" / "crs_title_25.md" in outputs


def test_exec_order_scraper_processes_sample(tmp_path: Path) -> None:
    """Executive order connector discovers, downloads, and extracts metadata."""

    index_url = "https://www.colorado.gov/governor/executive-orders"
    pdf_url = "https://www.colorado.gov/governor/eo/D2024001.pdf"
    html = f'<a href="{pdf_url}">D 2024 001 Emergency Order 2024-01-10</a>'
    client = FakeClient({index_url: FakeResponse(text=html), pdf_url: FakeResponse(content=b"pdf")})
    entries = discover_executive_orders(client=client, index_url=index_url)
    assert entries[0].entity_id == "EO-2024-001"
    download = download_executive_order(entries[0], tmp_path, client=client)
    assert Path(download.archive_path).exists()
    text = (
        "D 2024 001\nTitle: Emergency Order\nGovernor: Jared Polis\n"
        "Signed: 2024-01-10\nSummary: Directs emergency action under 24-33.5-704."
    )
    record = extract_order_metadata(text, index_url)
    valid, errors = validate_record(record)
    assert valid, errors


def test_orchestrator_runs_injected_connectors(project_root: Path) -> None:
    """Orchestrator runs individual injected connectors and handles failures."""

    def ok(raw_dir: Path, config: dict) -> None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "done.txt").write_text("ok", encoding="utf-8")

    def fail(raw_dir: Path, config: dict) -> None:
        raise RuntimeError("boom")

    report = run_full_download(
        {
            "root": project_root,
            "connectors": ["register", "exec_orders"],
            "connector_functions": {"register": ok, "exec_orders": fail},
        }
    )
    assert report.failed == 1
    assert (project_root / "_RAW_ARCHIVE" / "register" / "done.txt").exists()
    assert report.results[1].status == "failed"
