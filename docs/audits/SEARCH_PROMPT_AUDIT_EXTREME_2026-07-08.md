# Geode Extreme Search Pressure Test

Date: 2026-07-08

## Result

Ran all 100 extreme Colorado-specific search prompts through Geode search.

Final outcome:

- 100 prompts tested.
- 0 prompts returned empty results.
- 0 prompts had missing citation, excerpt, source URL, or match-reason data.
- 96 prompts passed the strict automated domain-coverage check.
- 4 prompts were flagged for manual review by the checker.
- 4 of 4 manual-review prompts produced reasonable source-backed results after inspection.

## What Was Repaired

The pressure test found that broad executive-style questions often returned good sources but were too concentrated in one domain, usually air or waste.

Repairs completed:

- Added domain-diversified ranking for broad operating questions.
- Broad manufacturing and industrial questions now intentionally surface air, water, waste, labor, and safety sources when the prompt asks for those areas.
- Specific OSHA-style searches still stay focused and do not get diluted by broad industrial diversification.
- Added better plain-language detection for:
  - employees and terminating employees
  - staffing and staff
  - heat and hotter operating conditions
  - complaints
  - inspections
  - spills and releases
  - contractor work
- Strengthened Colorado labor-family routing so ordinary staffing, shift, payroll, and termination questions surface labor records instead of unrelated worker-compensation material.
- Added a regression test to confirm broad manufacturing searches return a multi-domain source spread.

## Final Manual Review Notes

The four remaining review flags were checker overreach:

- A wastewater-only prompt was expected by the checker to include waste, but the result set correctly stayed focused on water-discharge authorities.
- A wage-and-hour prompt was expected by the checker to include safety, but the prompt did not ask for safety duties.
- An inspection prompt involving wastewater, spill, training, and wage complaint was expected by the checker to include air, but no air fact was present.
- An equipment-malfunction prompt involving excess emissions, wastewater, exposure, overtime, and contractor work was expected by the checker to include waste, but no waste fact was present.

These were reviewed as acceptable.

## Verification

Commands passed:

- `pytest tests\test_web_index.py -q`
- `python -m geode.validate --layer all`
- `node_modules\.bin\tsc.CMD --noEmit`
- `node_modules\.bin\eslint.CMD src\components\query\QuerySurface.tsx`

## Improvement Recommendation

The search layer now performs well for CEO-level broad review prompts. The next improvement should be a visible "domain coverage" panel in the UI that explicitly shows which legal families were surfaced and which were not found in the available sources.
