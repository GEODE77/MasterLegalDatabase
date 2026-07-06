# Supplementary Sources Refresh Report

Generated: 2026-07-02

## What Was Run

Geode refreshed the Supplementary layer from official Colorado supplementary sources:

- Colorado Attorney General formal opinions
- Colorado Office of Policy, Research and Regulatory Reform reviews

The run used the existing raw archive paths:

- `_RAW_ARCHIVE/supplementary/ag_opinions`
- `_RAW_ARCHIVE/supplementary/coprrr`

## Download Result

- AG opinion links discovered: 6
- AG opinion PDFs downloaded or confirmed: 6
- AG opinion failures: 0
- COPRRR review links discovered: 17
- COPRRR PDFs downloaded or confirmed: 17
- COPRRR failures: 0

## Pipeline Result

- Supplementary records before run: 19
- Supplementary records after run: 23
- AG opinion records: 6
- COPRRR review records: 17
- Supplementary layer is fresh as of 2026-07-02.

## Fixes Made

- AG opinion parsing now supports both numeric dates and month-name dates in official PDFs.
- AG opinion index writing now preserves existing COPRRR rows instead of replacing the whole
  supplementary index.
- AG and COPRRR downloads now reject non-PDF responses before writing raw archive files.
- COPRRR runs now write a summary file for audit tracking.

## Validation Result

- `python -m geode.validate --layer 07_Supplementary` passed.
- Source-to-output audit checked 57,154 records with 0 low-accuracy records.
- Retrieval catalog now indexes 57,154 records across all layers.

## Readiness Impact

The Supplementary official refresh item is now complete for this run.

The master readiness report still does not mark Geode externally reliance-ready because other
controls remain open:

- Named reviewer assignments are still missing.
- Four other official freshness refresh items remain.
- EO-2019-007 remains blocked because the official public download returns a Google Drive sign-in
  page instead of the order text.

## Main Artifacts

- `07_Supplementary/_index.jsonl`
- `07_Supplementary/_meta/ag_opinions_summary.json`
- `07_Supplementary/_meta/coprrr_reviews_summary.json`
- `_CONTROL_PLANE/SOURCE_TO_OUTPUT_ACCURACY_AUDIT.json`
- `_CONTROL_PLANE/FRESHNESS_VERIFICATION_QUEUE.json`
- `_CONTROL_PLANE/MASTER_READINESS_REPORT.json`
