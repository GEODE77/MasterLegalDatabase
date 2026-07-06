# Executive Orders Refresh Report - 2026-07-02

## Result

The Executive Orders source refresh was rerun against the official Colorado Governor
Executive Orders pages on 2026-07-02.

Geode discovered 535 executive-order source entries.

- 534 entries already had valid archived source artifacts and were skipped.
- 0 new valid artifacts were downloaded.
- 1 entry failed because the official public download returned a Google Drive sign-in
  or preview page instead of a usable executive-order PDF.

The blocked item is:

- EO-2019-007

## Pipeline Impact

The structured Executive Orders layer was rebuilt from the valid archived PDFs.

- Records written: 534
- Layer validation: passed
- Retrieval catalog count for Executive Orders: 534
- Source-to-output audit result for Executive Orders: 534 checked, 534 high accuracy,
  0 medium accuracy, 0 low accuracy

EO-2019-007 remains excluded from structured output because the archived artifact is not
valid source evidence.

## Safeguard Added

The Executive Orders downloader now rejects official responses that contain Google Drive
sign-in, preview, or account-gate content. It also refuses to treat an existing archived
artifact as valid resume evidence when that artifact is one of those blocked pages.

This prevents a failed public download from being counted as a successful source artifact.

## Current Boundary

This refresh improves source honesty, but it does not close Executive Orders completely.
The remaining work queue still includes EO-2019-007.

Recommended next action: request a valid official copy of EO-2019-007 from the Governor's
Office or State Archives, add it as raw source evidence, and rerun the Executive Orders
source-anchoring workflow.
