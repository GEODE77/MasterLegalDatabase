# Recent Download Audit

Generated: 2026-07-06T19:10:41.231476+00:00
Overall status: **WARN**

This audit checks the data collected in the recent download window.

## Layer Readability

| Layer | Status | Manifest Records | Index Records | JSONL Rows | Missing Paths | Detail |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 01_Statutes_CRS | PASS | 34,717 | 34,717 | 198,488 | 0 | Layer output files are readable and index counts match the manifest. |
| 02_Regulations_CCR | PASS | 1,035 | 1,035 | 36,159 | 0 | Layer output files are readable and index counts match the manifest. |
| 03_Legislation | PASS | 12,453 | 12,453 | 135,777 | 0 | Layer output files are readable and index counts match the manifest. |
| 04_Rulemaking | PASS | 7,955 | 7,955 | 32,676 | 0 | Layer output files are readable and index counts match the manifest. |
| 06_Session_Laws | PASS | 437 | 437 | 1,311 | 0 | Layer output files are readable and index counts match the manifest. |
| 07_Supplementary | PASS | 23 | 23 | 69 | 0 | Layer output files are readable and index counts match the manifest. |
| 05_Executive_Orders | PASS | 534 | 534 | 1,068 | 0 | Layer output files are readable and index counts match the manifest. |

## Pipeline Signals

| Signal | Status | Detail |
| --- | --- | --- |
| legiscan_live_refresh | PASS | Completed with 714 bills downloaded and 0 failures. |
| legiscan_document_queue | WARN | 61883 downloaded, 0 pending downloads. 23965 permanent source-coverage gaps remain across sessions 2010-2026; 23924 are pre-2018 legacy links and 41 are modern-year items for targeted review. Top hosts: www.leg.state.co.us: 21702, leg.colorado.gov: 2256, s3-us-west-2.amazonaws.com: 7. See _CONTROL_PLANE/MODERN_LEGISCAN_REPAIR_QUEUE.json and _CONTROL_PLANE/SOURCE_LIMITATION_REGISTER.json. |
| blocked_download_queue | WARN | 1 known blocked future download remains: EO-2019-007. |
| schema_validator | PASS | python -m geode.validate --layer all passed. |
| corpus_usability | PASS | Corpus usability refresh checked 57,154 index records, 9,980 crosswalk rows, and JSONL addressability with 0 errors and 0 warnings. The command timed out while printing the full detailed JSON, not while finding data errors. |
| secret_scan | PASS | No likely secrets found in staged or changed files. |

## Closeout Checks

| Check | Status | Detail |
| --- | --- | --- |
| no_secrets | PASS | No likely API keys or tokens found in staged or changed text files. |
| no_pending_downloads | WARN | C:\Users\jpfeifer\OneDrive - CoorsTek\Documents\Geode\_CONTROL_PLANE\BLOCKED_DOWNLOAD_QUEUE.json: 1 known blocked download item remains. C:\Users\jpfeifer\OneDrive - CoorsTek\Documents\Geode\_CONTROL_PLANE\FRESHNESS_VERIFICATION_QUEUE.json: 1 known future freshness item remains. |
| dashboard_updated | PASS | Next download dashboard is dated today and has a next recommendation. |

## Boundary

This audit checks local readability, parsed output files, manifest/index counts, source-path presence, and recorded pipeline completion signals for recent source downloads. It does not certify legal correctness or replace human source review.
