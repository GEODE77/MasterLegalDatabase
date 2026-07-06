# CRS Official Refresh Report

Generated: 2026-07-02

## Scope

This refresh confirmed the current official Colorado Revised Statutes publication year and
rebuilt the Geode statute layer from the preserved official SGML archive.

## Official Source Confirmation

- Official CRS landing page: https://content.leg.colorado.gov/agencies/office-legislative-legal-services/colorado-revised-statutes
- Official 2025 CRS title download page: https://content.leg.colorado.gov/agencies/office-legislative-legal-services/2025-crs-titles-download
- Official CRS data page: https://content.leg.colorado.gov/agencies/office-legislative-legal-services/colorado-revised-statutes-data
- Confirmed publication year: 2025
- Archived SGML package used by Geode: `_RAW_ARCHIVE/crs/2025-10-01/CRSDATA20251001.zip`

The official title download page is labeled 2025 and states that the downloadable CRS titles
are current with changes made by the Seventy-fifth General Assembly at its First Extraordinary
Session in August 2025. The official CRS data page states that the statutory database is
available as SGML text files in a zip file.

## Results

- Archived CRS title files checked: 46
- CRS title files parsed: 46
- CRS sections written: 34,717
- Failed files: 0
- Skipped files: 0
- Publication year used: 2025
- CRS subject index remains available as an auxiliary sidecar and is not counted as statute records.

## Crosswalk Rebuild

- Regulation-to-statute rows read: 696
- Statute-to-regulation rows written: 619
- Crosswalk rows skipped as invalid or non-usable: 77

## Validation

- CRS dry run: passed
- CRS real rebuild: passed
- `python -m geode.validate --layer 01_Statutes_CRS`: passed
- Source-to-output audit: 57,154 records checked
- Source-to-output result: 53,034 high-accuracy records, 4,120 medium-accuracy records, 0 low-accuracy records
- Readiness impact: CRS no longer appears as a pending official-refresh item.

## Remaining Official Refresh Items

- Legislation
- Executive Orders

Executive Orders remain partly blocked because `EO-2019-007` still needs a valid official PDF.
That blocked download is now preserved in `_CONTROL_PLANE/BLOCKED_DOWNLOAD_QUEUE.json`.

## Boundary

This report confirms that Geode rebuilt CRS from the preserved official 2025 SGML archive and
confirmed the public official CRS publication year. It does not claim that a newer SGML package
was downloaded during this run, and it does not certify external legal reliance.
