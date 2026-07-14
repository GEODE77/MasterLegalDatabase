# Source Update Watcher Dashboard

Generated: 2026-07-14T16:06:09.605181+00:00

## Summary

- Status: warn
- Sources watched: 10
- New data items: 0
- Manual review items: 6
- Queued download or review items: 6

## Watch List

| Source | Layers | Local marker | Observed marker | Status | Download status | Next step |
| --- | --- | --- | --- | --- | --- | --- |
| Colorado Revised Statutes | 01_Statutes_CRS, 06_Session_Laws | 2025 |  | manual_review_needed | manual_or_guarded_intake_required | Manual source review is needed before any download or replacement intake. |
| Code of Colorado Regulations | 02_Regulations_CCR | 2026-07-08 | 2026-06-29 | manual_review_needed | manual_or_guarded_intake_required | Manual source review is needed before any download or replacement intake. |
| LegiScan Colorado | 03_Legislation | 2026-07-06 |  | manual_review_needed | manual_or_guarded_intake_required | Manual source review is needed before any download or replacement intake. |
| Colorado Register | 04_Rulemaking | 2026-07-08 | 2026-07-10 | manual_review_needed | manual_or_guarded_intake_required | Manual source review is needed before any download or replacement intake. |
| Colorado Secretary of State eDocket | none |  |  | needs_live_check | watch_only | Live source check is needed before deciding whether to download. |
| Colorado Rulemaking Search Portal | none |  |  | needs_live_check | watch_only | Live source check is needed before deciding whether to download. |
| Colorado Governor Executive Orders | 05_Executive_Orders | 2026-07-07 | 2026-06-16 | manual_review_needed | manual_or_guarded_intake_required | Manual source review is needed before any download or replacement intake. |
| COPRRR Sunrise and Sunset Reviews | 07_Supplementary | 2026-07-08 | 2025-10-15 | manual_review_needed | manual_or_guarded_intake_required | Manual source review is needed before any download or replacement intake. |
| Colorado Attorney General Opinions | 07_Supplementary | 2026-07-08 | 2026-01-01 | no_change_detected | no_download_needed | No new source marker is newer than Geode's recorded refresh marker. |
| Federal OSHA Standards | 07_Supplementary | 2026-07-08 |  | needs_live_check | watch_only | Live source check is needed before deciding whether to download. |

## Guarded Queue

| Queue ID | Source | Action | Command |
| --- | --- | --- | --- |
| SOURCE-UPDATE-CRS | crs | manual_source_review | Manual source review required. |
| SOURCE-UPDATE-CCR | ccr | manual_source_review | Manual source review required. |
| SOURCE-UPDATE-LEGISCAN | legiscan | manual_source_review | python -m geode.connectors.legiscan_pipeline --output-root . --download --session-year 2026 |
| SOURCE-UPDATE-COLORADO_REGISTER | colorado_register | manual_source_review | python -m geode.connectors.register_pipeline --output-root . --download |
| SOURCE-UPDATE-EXECUTIVE_ORDERS | executive_orders | manual_source_review | Use the existing executive order connector or manual_source_intake for blocked official files, then rerun the executive order rebuild. |
| SOURCE-UPDATE-COPRRR | coprrr | manual_source_review | Manual source review required. |

## Recommended Plan

Use guarded automatic downloads for API-backed or stable listing sources, and keep manual intake for sources that require email, archives, or official replacement files. Every run should update this dashboard before downloading.

## Boundary

This dashboard identifies source freshness signals and guarded next steps. It does not authorize legal reliance, unofficial source substitution, or unsupervised broad corpus refreshes.
