# Source Update Watcher Dashboard

Generated: 2026-07-06T19:37:47.584699+00:00

## Summary

- Status: warn
- Sources watched: 8
- New data items: 0
- Manual review items: 2
- Queued download or review items: 2

## Watch List

| Source | Layers | Status | Download status | Next step |
| --- | --- | --- | --- | --- |
| Colorado Revised Statutes | 01_Statutes_CRS, 06_Session_Laws | manual_review_needed | manual_or_guarded_intake_required | Manual source review is needed before any download or replacement intake. |
| Code of Colorado Regulations | 02_Regulations_CCR | needs_live_check | watch_only | Live source check is needed before deciding whether to download. |
| LegiScan Colorado | 03_Legislation | watch_ready | watch_only | Watcher is configured; run the LegiScan API pull during the next refresh window. |
| Colorado Register | 04_Rulemaking | watch_ready | watch_only | Live source check is needed before deciding whether to download. |
| Colorado Secretary of State eDocket | none | needs_live_check | watch_only | Live source check is needed before deciding whether to download. |
| Colorado Governor Executive Orders | 05_Executive_Orders | manual_review_needed | manual_or_guarded_intake_required | Manual source review is needed before any download or replacement intake. |
| COPRRR Sunrise and Sunset Reviews | 07_Supplementary | needs_live_check | watch_only | Live source check is needed before deciding whether to download. |
| Colorado Attorney General Opinions | 07_Supplementary | needs_live_check | watch_only | Live source check is needed before deciding whether to download. |

## Guarded Queue

| Queue ID | Source | Action | Command |
| --- | --- | --- | --- |
| SOURCE-UPDATE-CRS | crs | manual_source_review | Manual source review required. |
| SOURCE-UPDATE-EXECUTIVE_ORDERS | executive_orders | manual_source_review | Use the existing executive order connector or manual_source_intake for blocked official files, then rerun the executive order rebuild. |

## Recommended Plan

Use guarded automatic downloads for API-backed or stable listing sources, and keep manual intake for sources that require email, archives, or official replacement files. Every run should update this dashboard before downloading.

## Boundary

This dashboard identifies source freshness signals and guarded next steps. It does not authorize legal reliance, unofficial source substitution, or unsupervised broad corpus refreshes.
