# Geode PR Publish Checklist

## What Changed

- [ ] The PR explains the main change in plain language.
- [ ] The PR includes only the files intended for this change.
- [ ] Any unrelated local changes were left out.

## Data Files Touched

- [ ] Data files touched by this PR are listed here:

<!-- Example: _CONTROL_PLANE/MASTER_MANIFEST.json, 05_Executive_Orders/_index.jsonl -->

- [ ] New data files, changed data files, and removed data files are clearly separated when useful.
- [ ] Large generated files are called out if they may affect GitHub review or repository size.

## Raw Archive Boundary

- [ ] `_RAW_ARCHIVE/` was not modified.
- [ ] If official source files were added through an approved intake workflow, that is explained here:

<!-- Leave blank if not applicable. -->

## Checks Run

- [ ] The checks run for this PR are listed here:

<!-- Example: pytest tests/test_web_index.py -q -->

- [ ] Any skipped checks are explained.
- [ ] Any failing checks are explained with the reason they are acceptable or still need work.

## Human Review Needed

- [ ] Items needing human review are listed here:

<!-- Example: confirm source quality for new rulemaking records. -->

- [ ] Any legal accuracy, source limitation, or external reliance concern is clearly noted.
- [ ] The PR does not claim legal advice or final legal approval.
