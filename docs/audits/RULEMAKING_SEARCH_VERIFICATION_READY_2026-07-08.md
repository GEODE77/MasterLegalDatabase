# Rulemaking Search Verification Readiness

Date: 2026-07-08

## Summary

Geode now has a testing workflow for comparing local CCR and rulemaking records against an official Colorado Rulemaking Search snapshot.

## Current Run

- Official snapshot loaded: False
- Geode CCR rules considered: 1035
- Geode rulemaking notices considered: 7955
- Official records loaded: 0
- Comparison records written: 1040
- Awaiting official snapshot: 1040
- Official matches found: 0
- Missing Geode rules: 0
- Needs review: 0

## Files

- Template: `04_Rulemaking/_verification/rulemaking_search_snapshot_template.csv`
- Normalized official snapshot: `04_Rulemaking/_verification/colorado_rulemaking_search_snapshot_normalized.jsonl`
- Comparison output: `04_Rulemaking/_verification/rulemaking_search_comparison.jsonl`
- Summary: `04_Rulemaking/_verification/rulemaking_search_verification_summary.json`
- Control-plane summary: `_CONTROL_PLANE/COLORADO_RULEMAKING_SEARCH_VERIFICATION.json`

## Boundary

This workflow compares Geode CCR and rulemaking records against a saved Colorado Rulemaking Search snapshot. It does not call the live website during search and does not treat uncertain matches as confirmed.

## Next Steps

- Export or capture a Rulemaking Search snapshot using the template columns.
- Run this command again with --official-snapshot pointing to the CSV, JSON, or JSONL file.
- Review the comparison output before using the status labels in release testing.
