# Project Geode — Tracked Defects

## DEF-001: Industry tagger false-positives on CAS Registry Numbers

**Discovered:** 2026-06-17 during pilot pull of rule 2427 (6 CCR 1010-6, Schools)
**Severity:** Low (cosmetic log noise; does not corrupt output)
**Module:** `geode/scoring/industry_tagger.py`

### Description

The CRS citation regex matches `NN-NN-N` strings without verifying that
the first segment falls within the valid Colorado Revised Statutes title
range (1-44). Documents containing CAS Registry Numbers
(Chemical Abstracts Service identifiers for chemical compounds)
generate hundreds of false-positive `Unmatched CRS title reference`
log entries.

### Evidence

Rule 2427 (Schools, with chemical safety provisions) produced approximately
270 unmatched references, all valid CAS numbers (50-00-0 Formaldehyde,
71-43-2 Benzene, 67-56-1 Methanol, etc.).

### Proposed Fix

Anchor the CRS citation regex on valid title numbers:
`\b([1-9]|[1-3][0-9]|4[0-4])-\d+-\d+\b`

This requires the first segment to be 1-44 (the range of Colorado Revised
Statutes titles), excluding CAS numbers which typically begin with values
outside that range or contain different segment patterns.

### Status

Tracked. Fix scheduled after pilot completes.
