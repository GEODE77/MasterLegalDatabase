# Rulemaking / eDocket / Colorado Register Download Report

Generated: 2026-07-02

## What Was Run

Geode refreshed the Colorado Rulemaking layer from the official Colorado Secretary of State
Colorado Register and eDocket sources.

The run used the existing raw archive path:

- `_RAW_ARCHIVE/register`
- `_RAW_ARCHIVE/edocket`

This kept the new source evidence with the prior Register/eDocket archive instead of creating a
parallel source folder.

## Download Result

- Official 2026 Register publications discovered: 12
- Existing 2026 Register publications skipped: 11
- Newly downloaded Register publication: 1
- New Register publication date: 2026-06-25
- Download failures: 0

## Pipeline Result

- Rulemaking records before run: 7,933
- Rulemaking records after run: 7,955
- Net new Rulemaking records: 22
- Colorado Register source publications in archive: 438
- Publications with extracted notices: 438
- Extraction failures: 0
- Extraction gaps: 0
- Quarantine rows: 0
- eDocket references: 315
- eDocket details fetched or confirmed: 315
- eDocket linked documents downloaded or confirmed: 516
- Rulemaking-to-regulation crosswalk rows: 7,955

## Validation Result

- `python -m geode.validate --layer 04_Rulemaking` passed.
- Source-to-output audit checked 57,150 records with 0 low-accuracy records.
- Retrieval catalog now indexes 57,150 records across all layers.

## Readiness Impact

The Rulemaking layer is now locally fresh as of 2026-07-02.

The master readiness report still does not mark Geode externally reliance-ready because other
controls remain open:

- Named reviewer assignments are still missing.
- Other layers still need live official freshness refreshes.
- EO-2019-007 remains blocked because the official public download returns a Google Drive sign-in
  page instead of the order text.

## Main Artifacts

- `_RAW_ARCHIVE/register/download_manifest.jsonl`
- `04_Rulemaking/_dataset/rulemaking_summary.json`
- `04_Rulemaking/_dataset/rulemaking_notices.jsonl`
- `04_Rulemaking/_dataset/edocket_details.jsonl`
- `04_Rulemaking/_dataset/edocket_documents.jsonl`
- `04_Rulemaking/_index.jsonl`
- `_CROSSWALKS/rulemaking_to_regulation.jsonl`
- `_CONTROL_PLANE/FRESHNESS_VERIFICATION_QUEUE.json`
- `_CONTROL_PLANE/MASTER_READINESS_REPORT.json`
