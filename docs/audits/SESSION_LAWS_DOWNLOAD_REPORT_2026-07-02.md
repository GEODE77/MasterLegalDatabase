# Session Laws Download Report

Generated: 2026-07-02

## What Was Run

Geode refreshed the Colorado Session Laws layer from the official Colorado General Assembly
Session Laws source and preserved the full chapter PDFs as raw source evidence.

The run used the existing raw archive path:

- `_RAW_ARCHIVE/crs/session_laws`

## Download Result

- Session-law rows discovered: 437
- Chapter PDFs downloaded or confirmed: 437
- Failed PDF downloads: 0
- Session year represented by the official source table: 2026

## Pipeline Result

- Session-law records structured: 437
- Session-law index rows written: 437
- Session-law records now point to chapter PDF source evidence instead of only table-page evidence.
- The Session Laws layer is fresh as of 2026-07-02.

## Validation Result

- `python -m geode.validate --layer 06_Session_Laws` passed.
- Source-to-output audit checked 57,150 records with 0 low-accuracy records.
- Retrieval catalog still indexes 57,150 records across all layers.

## Readiness Impact

The session-law full-text source-depth item is now closed by PDF archive.

The master readiness report still does not mark Geode externally reliance-ready because other
controls remain open:

- Named reviewer assignments are still missing.
- Five other official freshness refresh items remain.
- EO-2019-007 remains blocked because the official public download returns a Google Drive sign-in
  page instead of the order text.

## Main Artifacts

- `_RAW_ARCHIVE/crs/session_laws/2026/`
- `06_Session_Laws/_meta/session_laws_summary.json`
- `06_Session_Laws/_meta/session_laws_meta.jsonl`
- `06_Session_Laws/_index.jsonl`
- `_CONTROL_PLANE/SOURCE_TO_OUTPUT_ACCURACY_AUDIT.json`
- `_CONTROL_PLANE/FRESHNESS_VERIFICATION_QUEUE.json`
- `_CONTROL_PLANE/MASTER_READINESS_REPORT.json`
