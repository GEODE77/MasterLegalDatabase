"""Tests for executive-order source anchoring behavior."""

from __future__ import annotations

from geode.connectors.exec_orders_scraper import _signed_date_from_order_text


def test_signed_date_handles_ocr_spaced_month_and_year() -> None:
    """OCR spacing in signature dates should still produce an ISO date."""

    text = """
    D 2019 010
    EXECUTIVE ORDER
    GIVEN under my hand and the
    Executive Seal of the State of
    Colorado, this fifteenth day
    of  A ugust, 20 I 9.
    """

    assert _signed_date_from_order_text(text, "EO-2019-010") == "2019-08-15"
