"""Shared constants for Project Geode."""

from __future__ import annotations

CRS_LAYER = "01_Statutes_CRS"
CONTROL_PLANE_DIR = "_CONTROL_PLANE"
RAW_ARCHIVE_DIR = "_RAW_ARCHIVE"
SNAPSHOTS_DIR = "_SNAPSHOTS"
QUARANTINE_DIR = "_QUARANTINE"

ALL_LAYERS = (
    "01_Statutes_CRS",
    "02_Regulations_CCR",
    "03_Legislation",
    "04_Rulemaking",
    "05_Executive_Orders",
    "06_Session_Laws",
    "07_Supplementary",
)

AUTHORIZED_SOURCE_HOSTS = frozenset(
    {
        "advance.lexis.com",
        "ag.colorado.gov",
        "cdec.colorado.gov",
        "cdhs.colorado.gov",
        "cdle.colorado.gov",
        "cdoc.colorado.gov",
        "cdola.colorado.gov",
        "coag.gov",
        "codot.gov",
        "content.leg.colorado.gov",
        "coprrr.colorado.gov",
        "cdphe.colorado.gov",
        "dmva.colorado.gov",
        "dnr.colorado.gov",
        "dora.colorado.gov",
        "dpa.colorado.gov",
        "drive.google.com",
        "ecfr.gov",
        "hcpf.colorado.gov",
        "highered.colorado.gov",
        "api.legiscan.com",
        "legiscan.com",
        "leg.colorado.gov",
        "olls.info",
        "oit-rules-search-ui.coawsprod.com",
        "publicsafety.colorado.gov",
        "rulemaking.colorado.gov",
        "scholar.law.colorado.edu",
        "sos.state.co.us",
        "spl.cde.state.co.us",
        "tax.colorado.gov",
        "treasury.colorado.gov",
        "uapi.colorado.gov",
        "www.colorado.gov",
        "www.cde.state.co.us",
        "www.coag.gov",
        "www.codot.gov",
        "www.courts.state.co.us",
        "www.ecfr.gov",
        "www.sos.state.co.us",
        "www.lexisnexis.com",
        "uscode.house.gov",
    }
)
