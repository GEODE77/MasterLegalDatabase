# Source Limitation Repair Plan

Generated: 2026-07-06

This plan explains the two remaining warning sources after the recent download audit.

## EO-2019-007

Status: official copy required.

The Governor's official 2019 executive order page lists `D 2019-007`, dated `2019-05-31`, titled `Tribal Access to Certain Child Welfare and Criminal History Databases`. The linked Google Drive file still returns a sign-in page locally, so Geode must not use it as a raw source artifact.

Repair path:

1. Request a valid official copy from the Colorado Governor's Office or Colorado State Archives.
2. Archive the received file through manual source intake.
3. Rebuild the executive order layer.
4. Rerun the recent download audit and source-to-output audit.

Manual intake command shape:

```powershell
python -m geode.pipeline.manual_source_intake `
  --root . `
  --apply `
  --record-id EO-2019-007 `
  --layer-id 05_Executive_Orders `
  --source-file <official_pdf_path> `
  --official-source-name "Colorado Governor's Office or State Archives" `
  --official-source-url https://www.colorado.gov/governor/2019-executive-orders `
  --acquisition-method state_archives_request `
  --received-from <source_contact> `
  --reviewer-name <reviewer_name> `
  --custody-note <custody_note> `
  --json
```

## LegiScan Legacy Document Gaps

Status: source-coverage limitation, not active retry work.

The LegiScan document queue has:

- 85,848 total document records
- 61,883 downloaded
- 23,965 permanent source failures
- 0 pending downloads
- 0 pending retries

The permanent failures are concentrated in old bill-text links, mostly `2010-2017`. The top hosts are:

- `www.leg.state.co.us`: 21,702
- `leg.colorado.gov`: 2,256
- `s3-us-west-2.amazonaws.com`: 7

Of the 23,965 permanent failures, 23,924 are pre-2018 legacy links and 41 are modern-year items. The modern-year group now has its own focused queue:

- `_CONTROL_PLANE/MODERN_LEGISCAN_REPAIR_QUEUE.json`
- `docs/audits/MODERN_LEGISCAN_REPAIR_QUEUE_2026-07-06.md`

Repair path:

1. Treat this as a historical source-coverage project, not a failed current download.
2. Work the 41-item modern repair queue first using `python -m geode.pipeline.legiscan_repair_intake` after each official replacement file is verified.
3. Build a host-specific recovery workflow for the large legacy archive group.
4. Keep the main download audit at warning level until the coverage gap is either repaired or formally accepted by the project owner.

## Boundary

These warnings should not block normal pipeline closeout, because there is no active retry queue. They should remain visible until the official EO copy is received and the historical LegiScan source-coverage repair is either completed or formally accepted.
