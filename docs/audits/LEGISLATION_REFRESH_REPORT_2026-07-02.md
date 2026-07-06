# Legislation Refresh Report

Generated: 2026-07-02

## Scope

This pass attempted the next official-refresh area: Legislation. The live LegiScan refresh
could not be completed in this session because `LEGISCAN_API_KEY` is not configured.

The blocked live refresh has been queued for later completion, and the existing archived
LegiScan data was rebuilt into the Geode legislation layer.

## Blocked Live Refresh

- Blocked item: `LEGISCAN-LIVE-REFRESH`
- Queue path: `_CONTROL_PLANE/BLOCKED_DOWNLOAD_QUEUE.json`
- Reason: Live LegiScan bill refresh requires `LEGISCAN_API_KEY`, and that environment
  variable is not configured in this session.
- Next action: Configure `LEGISCAN_API_KEY`, then run the LegiScan current-session or
  all-session refresh and rebuild the legislation layer.

## Archive Rebuild Results

- Raw archived LegiScan bill JSON files: 12,453
- Normalized legislation records: 12,453
- Failed raw files: 0
- Skipped files: 0
- Bill-to-statute crosswalk rows: 7
- Year files rebuilt: 2010 through 2026

## Document Queue Results

- Document metadata records: 85,848
- Downloaded document artifacts: 61,883
- Permanent legacy-source failures: 23,965
- Pending retry items: 0
- Pending undiscovered items: 0

The permanent failures are legacy Colorado archive document links that return archive wrapper
HTML instead of the original document. They are classified as permanent source failures rather
than retryable download work.

## Validation

- `python -m geode.validate --layer 03_Legislation`: passed
- Source-to-output audit: 57,154 records checked
- Source-to-output result: 53,034 high-accuracy records, 4,120 medium-accuracy records, 0 low-accuracy records
- Focused tests: 31 passed

## Readiness Impact

The local legislation layer is rebuilt and validated from the existing raw archive, but the
official live LegiScan refresh remains open until the API key is configured. The master
freshness queue therefore still includes Legislation as an official-refresh item.

## Boundary

This report confirms local archive consistency for legislation. It does not claim a completed
live official LegiScan refresh.
