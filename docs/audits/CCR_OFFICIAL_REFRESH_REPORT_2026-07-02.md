# CCR Official Refresh Report

Generated: 2026-07-02

## Scope

This refresh checked the current Code of Colorado Regulations source inventory from the
Colorado Secretary of State and rebuilt the local CCR outputs used by Geode.

## Results

- Official CCR rule series discovered: 1,035
- Official CCR rule series resolved: 1,035
- Source inventory assets tracked: 2,070
- Existing source files confirmed: 1,035
- New source files downloaded: 0
- Failed items: 0
- Blocked items: 0
- Normalized CCR records written: 1,035
- Industry-tagged CCR records: 272
- Untagged CCR records: 763

## Quality Checks

- Traversal status: uncapped discovery completed
- Field status: critical fields populated
- CCR layer validation: passed
- Source-to-output audit: 57,154 total records checked across Geode
- Accuracy result: 53,034 high-accuracy records, 4,120 medium-accuracy records, 0 low-accuracy records
- Focused tests: 41 passed

## Pipeline Correction

The CCR bulk workflow now updates the main Geode manifest after a completed non-dry-run CCR
refresh. This prevents the system from showing CCR as stale after the official refresh has
already completed.

The CCR downloader also preserves raw-source integrity. If a previously manifested CCR source
file exists and the Secretary of State later serves different bytes for that same target, Geode
stores the changed source under a timestamped filename rather than overwriting the earlier
raw evidence.

## Current Readiness Impact

CCR is now treated as refreshed for this run. The source quality readiness layer reports three
remaining official freshness items after this update.

Remaining official-refresh areas:

- Colorado Revised Statutes
- Legislation
- Executive Orders

Executive Orders still have a known source-repair issue for EO-2019-007 because the official
public download returns a Google sign-in page instead of a usable PDF.

## Boundary

This report confirms that the local CCR refresh and validation completed. It does not certify
legal correctness, external reliance readiness, or future live freshness.
