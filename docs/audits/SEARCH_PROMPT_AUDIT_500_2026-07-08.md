# Geode Search Prompt Audit - 500 Prompt Set

Date: 2026-07-08

## Result

Ran all 500 prompts from `Easy Search Prompts - 1-150` and `Difficult to Extreme Search Prompts - 151-500` through Geode search.

Final outcome:

- 500 prompts tested.
- 0 prompts returned empty results.
- 0 prompts had missing citation, excerpt, source URL, or match-reason data.
- 485 prompts passed the strict automated top-result check.
- 15 prompts were flagged for manual review by the strict checker.
- 15 of 15 manual-review prompts produced reasonable source-backed starting points after inspection.
- 1 real issue found in the final review group was repaired after the run: payroll/hourly-worker manufacturing searches now route to Colorado wage-order sources.

## Repairs Completed

The audit found and repaired these search weaknesses:

- Added and indexed selected federal OSHA records for lockout/tagout, PPE, respiratory protection, confined spaces, forklifts, hot work, and injury/illness records.
- Fixed hidden-word matching so `tipped` no longer triggers `PPE`.
- Improved punctuation handling so searches like `minimum wage?`, `Colorado's minimum wage`, and `lockout/tagout` match correctly.
- Improved routing for:
  - minimum wage
  - nonexempt employees
  - wage payment and wage theft
  - payroll and hourly employees
  - final paychecks
  - equal pay
  - independent contractors
  - workers' compensation
  - workplace injury reporting
  - universal waste
  - hazardous waste generators
  - boiler and pressure vessel requirements
  - safety data sheets and hazard communication
  - dust-producing industrial and manufacturing processes
  - broad industrial compliance, audit, and executive-briefing prompts
- Added guardrails so broad industrial searches are less likely to be overtaken by unrelated health-program, utility, oil-and-gas, workers' compensation, or narrow federal OSHA records.
- Updated the query page coverage notice so OSHA-related searches explain that Geode is using selected federal OSHA source records.
- Updated Geode control-plane counts for the expanded federal OSHA supplementary source.

## Final Manual Review Notes

The strict checker still flagged 15 broad prompts because they mentioned multiple possible domains and the checker expected one domain while Geode returned another valid domain.

Examples:

- Broad industrial facility prompts returned water, air, or waste rule families.
- Spill and release prompts returned air, water, and hazardous-waste reporting sources.
- Ceramics expansion stress tests returned air permitting first, with hazardous-waste rules immediately behind it.
- Contractor-safety prompts returned federal OSHA sources.
- Wage-and-hour manufacturing prompts returned Colorado wage-order sources after repair.

These were reviewed as acceptable because the returned citations were source-backed, understandable, and relevant starting points for the question.

## Verification

Commands passed:

- `pytest tests\test_web_index.py -q`
- `python -m geode.validate --layer all`
- `node_modules\.bin\tsc.CMD --noEmit`
- `node_modules\.bin\eslint.CMD src\components\query\QuerySurface.tsx`

Search database rebuilds were completed during the repair work, with prior local databases snapshotted under `_SNAPSHOTS`.
