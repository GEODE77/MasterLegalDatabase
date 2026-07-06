"""Tests for Colorado Register table extraction helpers."""

from __future__ import annotations

from geode.connectors.register_table_parser import extract_register_table_notices


def test_extract_register_table_notices_preserves_row_provenance() -> None:
    """Register table rows produce conservative notice candidates."""

    html = """
    <html><body>
      <h2 class="pagehead">Notice of Proposed Rulemaking</h2>
      <table>
        <tr>
          <td>Department of Public Health and Environment</td>
          <td>Air Quality Control Commission</td>
          <td>5 CCR 1001-9</td>
          <td>Emission reporting updates</td>
          <td><a href="/CCR/eDocketDetails.do?trackingNum=2026-00421">eDocket</a></td>
          <td>08/01/2026</td>
        </tr>
      </table>
    </body></html>
    """

    rows = extract_register_table_notices(html)

    assert len(rows) == 1
    assert rows[0].row_number == 1
    assert rows[0].notice_type == "proposed"
    assert rows[0].notice_type_source == "register_section_heading"
    assert rows[0].ccr_rule_affected == "5_CCR_1001-9"
    assert rows[0].edocket_tracking_number == "2026-00421"
    assert rows[0].hearing_date == "2026-08-01"
    assert rows[0].section_heading == "Notice of Proposed Rulemaking"
