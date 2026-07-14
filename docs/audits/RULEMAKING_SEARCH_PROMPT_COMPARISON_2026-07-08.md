# Geode vs Colorado Rulemaking Search Prompt Comparison

Date: 2026-07-08

## Summary

- Prompts tested: 50
- Geode empty results: 0
- Official empty results: 5
- Direct citation overlap: 42
- Geode broader than official search: 7
- Needs review: 1

## Boundary

This compares Geode's broad legal corpus search to Colorado's official Rulemaking Search, which is a narrower CCR/current-rule search. A lack of official overlap is not automatically a Geode failure.

## Overall Finding

Geode returned results for every prompt. Some prompts need review because the official search surfaced different CCR citations than Geode's top results.

## Prompt Results

### 1. direct_overlap

A Colorado manufacturing facility is considering a process change that will not increase square footage but may affect air emissions, employee exposure, wastewater chemistry, hazardous waste classification, and production schedules. Identify the Colorado legal authorities and missing facts needed to evaluate applicability.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-3, 7 CCR 1107-1, 29 CFR Part 1904
- Official top citations: 6 CCR 1007-3 Part 100, 6 CCR 1007-3 Part 8, 5 CCR 1001-9, 6 CCR 1007-3 Part 264, 5 CCR 1001-26
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-3, 5 CCR 1001-2, 5 CCR 1001-34, 5 CCR 1001-30
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 2. direct_overlap

A Colorado ceramics plant wants to run a pilot production line for six months using new raw materials, temporary equipment, contractors, and modified waste handling. What Colorado permits, exemptions, reporting duties, and recordkeeping obligations should be reviewed?

- Geode top citations: 5 CCR 1001-30, 5 CCR 1002-86, 6 CCR 1007-3, 7 CCR 1103-15, 8 CCR 1507-25
- Official top citations: 6 CCR 1007-3 Part 265, 5 CCR 1001-10, 6 CCR 1007-3 Part 100, 6 CCR 1007-3 Part 8, 5 CCR 1001-30
- Shared citations: 5 CCR 1001-30, 6 CCR 1007-3, 6 CCR 1007-2
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 3. direct_overlap

A Colorado industrial facility believes a project is exempt because it is temporary. Identify Colorado legal authorities that determine when temporary operations still trigger air, water, waste, stormwater, labor, safety, or reporting obligations.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-4, 7 CCR 1103-15, 8 CCR 1507-3
- Official top citations: 6 CCR 1007-3 Part 8, 5 CCR 1001-5, 5 CCR 1002-31, 5 CCR 1003-2, 5 CCR 1001-35
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 5 CCR 1001-10
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 4. direct_overlap

A Colorado plant is replacing older equipment with newer equipment that is more efficient but increases throughput. What Colorado rules determine whether the replacement is a like-kind substitution, a modification, or a permit-triggering operational change?

- Geode top citations: 5 CCR 1001-1, 5 CCR 1002-101, 6 CCR 1007-1, 5 CCR 1001-10, 5 CCR 1001-11
- Official top citations: 6 CCR 1007-3 Part 8, 7 CCR 1101-14, 5 CCR 1001-35, 5 CCR 1001-5, 4 CCR 723-3
- Shared citations: 5 CCR 1001-13
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 5. direct_overlap

A Colorado manufacturing company wants to know whether “no increase in emissions” can be assumed when production volume increases but control equipment is upgraded. What Colorado air permitting, recordkeeping, monitoring, and proof obligations should be reviewed?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-72, 6 CCR 1007-3, 7 CCR 1103-20, 5 CCR 1001-9
- Official top citations: 5 CCR 1001-5, 2 CCR 404-1, 5 CCR 1001-10, 5 CCR 1001-8, 5 CCR 1001-3
- Shared citations: 5 CCR 1001-5, 5 CCR 1001-9, 5 CCR 1001-3
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 6. direct_overlap

A Colorado facility is changing from batch production to continuous production. Identify the Colorado environmental, wage-hour, safety, training, permit, inspection, and records issues this operational change could trigger.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-3, 7 CCR 1103-15, 8 CCR 1507-25
- Official top citations: 5 CCR 1001-5, 5 CCR 1001-9, 1 CCR 212-3, 5 CCR 1001-8, 6 CCR 1007-2 Part 1
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 7. direct_overlap

A Colorado manufacturer has a permitted wastewater discharge but is changing cleaning chemicals, production inputs, and discharge timing. What Colorado water quality, pretreatment, permit modification, sampling, reporting, and recordkeeping authorities are relevant?

- Geode top citations: 5 CCR 1001-29, 5 CCR 1002-61, 6 CCR 1007-1, 7 CCR 1103-7, 6 CCR 1007-2
- Official top citations: 5 CCR 1002-11, 5 CCR 1002-61, 5 CCR 1003-2, 5 CCR 1002-86, 5 CCR 1002-84
- Shared citations: 5 CCR 1001-29, 5 CCR 1002-61, 6 CCR 1007-2, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 8. direct_overlap

A Colorado site stores raw materials outdoors only during summer expansion work. Determine whether Colorado stormwater, spill prevention, hazardous material, waste storage, local land-use, and inspection requirements may apply.

- Geode top citations: 5 CCR 1002-61, 6 CCR 1007-1, 8 CCR 1507-1, 5 CCR 1002-63, 6 CCR 1007-2
- Official top citations: 6 CCR 1007-3 Part 100, 6 CCR 1007-3 Part 8, 2 CCR 404-1, 5 CCR 1001-35, 6 CCR 1007-2 Part 1
- Shared citations: 5 CCR 1002-61, 6 CCR 1007-2, 6 CCR 1007-3, 5 CCR 1002-38
- Geode domains: Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 9. direct_overlap

A Colorado industrial operation wants to reuse process residuals internally rather than dispose of them. What Colorado solid waste, hazardous waste, recycling, beneficial reuse, storage, documentation, and enforcement authorities should be reviewed?

- Geode top citations: 5 CCR 1001-26, 5 CCR 1002-64, 6 CCR 1007-4, 6 CCR 1007-3, 6 CCR 1007-1
- Official top citations: 6 CCR 1007-2 Part 1, 6 CCR 1007-1 Part 20, 6 CCR 1007-3 Part 8, 6 CCR 1007-4, 6 CCR 1007-3 Part 262
- Shared citations: 6 CCR 1007-4, 6 CCR 1007-3, 6 CCR 1007-1, 6 CCR 1007-2
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 10. direct_overlap

A Colorado manufacturing facility has multiple low-volume waste streams that may be individually minor but cumulatively significant. What Colorado rules govern aggregation, generator status, waste characterization, accumulation limits, manifests, and inspection records?

- Geode top citations: 5 CCR 1001-30, 5 CCR 1002-11, 6 CCR 1007-3, 8 CCR 1507-12, 6 CCR 1007-1
- Official top citations: 6 CCR 1007-3 Part 264, 6 CCR 1007-3 Part 8, 5 CCR 1002-61, 6 CCR 1007-3 Part 262, 6 CCR 1007-3 Part 100
- Shared citations: 5 CCR 1001-30, 6 CCR 1007-3, 6 CCR 1007-2
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 11. geode_broader_than_official

A Colorado plant manager says “we do not discharge wastewater; it all goes to floor drains.” Identify the Colorado authorities and factual questions needed to determine whether process wastewater, sewer discharge, pretreatment, spill, or permit obligations apply.

- Geode top citations: 5 CCR 1001-4, 5 CCR 1002-61, 6 CCR 1007-3, 6 CCR 1007-4, 5 CCR 1002-63
- Official top citations: none
- Shared citations: none
- Geode domains: Air, Water, Waste
- Recommendation: Keep Geode behavior; note that the official tool is narrower and CCR-focused. Issue: Geode returned source-backed results while the official CCR search returned none.

### 12. direct_overlap

A Colorado facility has dust collectors, baghouses, grinders, kilns, and raw material transfer points. What Colorado legal authorities govern particulate emissions, fugitive dust, opacity, permit limits, monitoring, maintenance, malfunction reporting, and inspection records?

- Geode top citations: 5 CCR 1001-5, 29 CFR 1910.1053, 5 CCR 1001-1, 5 CCR 1001-10, 5 CCR 1001-11
- Official top citations: 6 CCR 1007-3 Part 265, 1 CCR 212-3, 5 CCR 1001-5, 6 CCR 1007-2 Part 1, 5 CCR 1001-3
- Shared citations: 5 CCR 1001-5, 5 CCR 1001-10, 5 CCR 1001-11
- Geode domains: Air, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 13. direct_overlap

A Colorado production facility is evaluating whether to route a new exhaust stream into existing air pollution control equipment. What Colorado rules determine whether permit revision, engineering review, monitoring, or compliance demonstration is required?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-72, 6 CCR 1007-3, 5 CCR 1001-9, 5 CCR 1001-10
- Official top citations: 5 CCR 1001-9, 5 CCR 1001-3, 5 CCR 1001-10, 5 CCR 1001-5, 5 CCR 1001-30
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-72, 6 CCR 1007-3, 5 CCR 1001-9, 5 CCR 1001-10, 5 CCR 1001-3, 5 CCR 1001-29
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 14. direct_overlap

A Colorado facility has an emergency equipment failure that causes excess emissions, production downtime, employee overtime, contractor repair work, and possible waste disposal changes. Identify the Colorado legal obligations triggered by the event.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-101, 6 CCR 1007-1, 7 CCR 1103-1, 29 U.S.C. 654
- Official top citations: 5 CCR 1002-61, 6 CCR 1007-3 Part 265, 5 CCR 1001-9, 6 CCR 1007-3 Part 8, 5 CCR 1001-35
- Shared citations: 5 CCR 1001-5, 5 CCR 1001-10, 5 CCR 1001-29
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 15. geode_broader_than_official

A Colorado manufacturer is preparing for a state agency inspection but does not know which records will be requested. Create a Colorado-specific search query that retrieves environmental, labor, safety, training, payroll, permit, inspection, and incident records obligations.

- Geode top citations: 5 CCR 1001-29, 5 CCR 1002-43, 6 CCR 1007-1, 7 CCR 1103-1, 8 CCR 1507-31
- Official top citations: 3 CCR 719-1, 6 CCR 1007-2 Part 1, 12 CCR 2509-8, 9 CCR 2503-5, 10 CCR 2505-10 8.7000
- Shared citations: none
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Keep Geode's broader result, but surface the official CCR hits as current-status checks. Issue: Geode returned a broader compliance map than the official CCR search.

### 16. direct_overlap

A Colorado industrial facility has incomplete records for air emissions monitoring, hazardous waste inspections, stormwater controls, safety training, and employee timekeeping. What Colorado statutes, regulations, penalties, and corrective action obligations are relevant?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-4, 7 CCR 1103-15, 8 CCR 1507-3
- Official top citations: 5 CCR 1001-35, 6 CCR 1007-2 Part 1, 5 CCR 1001-30, 5 CCR 1001-9, 6 CCR 1007-3 Part 8
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 5 CCR 1001-10
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 17. direct_overlap

A Colorado company is standardizing compliance across facilities in different municipalities. What Colorado statewide requirements should be separated from local permits, local wastewater authority requirements, zoning, building, fire, and utility-specific obligations?

- Geode top citations: 5 CCR 1002-61, 5 CCR 1002-63, 5 CCR 1002-81, 5 CCR 1002-11, 5 CCR 1002-38
- Official top citations: 5 CCR 1002-61, 7 CCR 1101-14, 6 CCR 1007-2 Part 1, 5 CCR 1002-38, 5 CCR 1002-84
- Shared citations: 5 CCR 1002-61, 5 CCR 1002-38, 5 CCR 1002-72
- Geode domains: Water
- Recommendation: Good result. Keep this prompt in regression testing.

### 18. direct_overlap

A Colorado manufacturing site wants to add a second production shift using temporary employees from a staffing agency. Identify Colorado wage, hour, leave, workplace safety, training, injury reporting, joint-employment, and recordkeeping issues.

- Geode top citations: 7 CCR 1103-1, 29 CFR Part 1904, 7 CCR 1103-11, 7 CCR 1103-12, 7 CCR 1103-14
- Official top citations: 7 CCR 1103-7, 4 CCR 801-1, 7 CCR 1103-15, 10 CCR 2505-10 8.7000, 9 CCR 2503-6
- Shared citations: 7 CCR 1103-1, 7 CCR 1103-11, 7 CCR 1103-15
- Geode domains: Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 19. direct_overlap

A Colorado employer uses production bonuses, shift differentials, and overtime for hourly manufacturing employees. What Colorado wage calculation, payroll record, wage statement, deduction, and overtime authorities should be retrieved?

- Geode top citations: 5 CCR 1001-9, 5 CCR 1002-72, 6 CCR 1007-3, 7 CCR 1103-1, 7 CCR 1103-15
- Official top citations: 7 CCR 1103-7, 7 CCR 1103-1, 4 CCR 801-1
- Shared citations: 7 CCR 1103-1
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 20. direct_overlap

A Colorado manufacturing facility is changing employee schedules from five eight-hour shifts to four ten-hour shifts. Identify Colorado meal period, rest period, overtime, wage statement, leave, timekeeping, and record retention obligations.

- Geode top citations: 5 CCR 1001-30, 5 CCR 1002-102, 6 CCR 1007-3, 7 CCR 1103-1, 7 CCR 1103-11
- Official top citations: 7 CCR 1103-1, 4 CCR 801-1, 10 CCR 2505-10 8.7000, 7 CCR 1103-15, 7 CCR 1103-7
- Shared citations: 7 CCR 1103-1
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 21. direct_overlap

A Colorado plant has employees working around heat, dust, noise, chemicals, forklifts, and moving machinery. Retrieve Colorado-relevant workplace safety authorities and distinguish training, PPE, exposure controls, injury reporting, retaliation, and records.

- Geode top citations: 5 CCR 1001-10, 6 CCR 1007-1, 7 CCR 1107-1, 29 CFR 1910.132, 5 CCR 1001-5
- Official top citations: 1 CCR 212-3, 7 CCR 1103-20, 7 CCR 1103-15, 2 CCR 407-6, 7 CCR 1103-11
- Shared citations: 5 CCR 1001-10, 5 CCR 1001-5, 6 CCR 1007-2, 6 CCR 1007-3
- Geode domains: Air, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 22. direct_overlap

A Colorado employee reports unsafe dust exposure and missed meal breaks after a production increase. What Colorado labor, workplace safety, retaliation, wage, inspection, complaint, and documentation authorities should Geode retrieve?

- Geode top citations: 5 CCR 1001-5, 7 CCR 1103-15, 29 U.S.C. 654, 7 CCR 1103-1, 7 CCR 1103-11
- Official top citations: 7 CCR 1103-15, 7 CCR 1103-11, 7 CCR 1103-7, 7 CCR 1107-3, 2 CCR 502-1
- Shared citations: 7 CCR 1103-15, 7 CCR 1103-1, 7 CCR 1103-11
- Geode domains: Air, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 23. direct_overlap

A Colorado facility is using contractors to install production equipment while ordinary operations continue. Identify Colorado legal obligations involving contractor safety, hazardous energy control, hot work, temporary storage, construction stormwater, spills, and permit impacts.

- Geode top citations: 5 CCR 1002-61, 6 CCR 1007-1, 29 CFR 1910.252, 6 CCR 1007-2, 6 CCR 1007-3
- Official top citations: 6 CCR 1007-3 Part 265, 5 CCR 1001-29, 6 CCR 1007-1 Part 03, 5 CCR 1002-87, 6 CCR 1007-3 Part 262
- Shared citations: 5 CCR 1002-61, 6 CCR 1007-1, 6 CCR 1007-2, 6 CCR 1007-3
- Geode domains: Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 24. direct_overlap

A Colorado manufacturer wants contractors to bring chemicals onsite for maintenance work. What Colorado legal requirements address chemical inventory, SDS access, hazard communication, waste ownership, spill reporting, employee exposure, and documentation?

- Geode top citations: 5 CCR 1002-11, 6 CCR 1007-3, 7 CCR 1107-3, 29 CFR 1910.1200, 6 CCR 1007-1
- Official top citations: 1 CCR 212-3, 2 CCR 404-1, 6 CCR 1007-3 Part 262, 6 CCR 1011-1 Chapter 07, 7 CCR 1101-14
- Shared citations: 5 CCR 1002-11, 6 CCR 1007-3, 6 CCR 1007-1, 6 CCR 1007-2
- Geode domains: Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 25. direct_overlap

A Colorado facility discovers unlabeled containers in an old storage room during a renovation. Identify Colorado hazardous waste, unknown waste, storage, labeling, inspection, release reporting, disposal, and recordkeeping authorities.

- Geode top citations: 5 CCR 1001-10, 5 CCR 1002-61, 6 CCR 1007-1, 7 CCR 1103-20, 8 CCR 1507-3
- Official top citations: 6 CCR 1007-3 Part 265, 6 CCR 1007-3 Part 8, 7 CCR 1101-14, 6 CCR 1007-3 Part 264, 1 CCR 212-3
- Shared citations: 5 CCR 1001-10, 6 CCR 1007-1, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 26. direct_overlap

A Colorado site has outdoor pallets, scrap material, drums, dust, and equipment exposed to precipitation. What Colorado stormwater, waste storage, spill prevention, runoff, inspection, permit, and corrective action obligations may apply?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-1, 8 CCR 1507-1, 5 CCR 1001-35
- Official top citations: 5 CCR 1002-61, 2 CCR 404-1, 6 CCR 1007-3 Part 265, 6 CCR 1007-3 Part 261, 5 CCR 1001-35
- Shared citations: 5 CCR 1002-61, 5 CCR 1001-35, 5 CCR 1002-72
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 27. direct_overlap

A Colorado facility is planning a shutdown to clean tanks, dispose of chemicals, repair equipment, and lay off temporary workers. What Colorado environmental, employment, safety, contractor, waste, final wage, and reporting rules should be reviewed?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-63, 6 CCR 1007-3, 7 CCR 1103-15, 8 CCR 1507-3
- Official top citations: 6 CCR 1007-2 Part 1, 6 CCR 1007-3 Part 265, 5 CCR 1001-9, 5 CCR 1001-35, 6 CCR 1007-3 Part 8
- Shared citations: 5 CCR 1001-5, 6 CCR 1007-3, 5 CCR 1001-10
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 28. direct_overlap

A Colorado manufacturing plant is changing suppliers, and the new material has different chemical constituents. Identify Colorado obligations related to SDS updates, employee training, waste characterization, wastewater impacts, air permit assumptions, spill planning, and documentation.

- Geode top citations: 5 CCR 1001-10, 5 CCR 1002-11, 6 CCR 1007-3, 7 CCR 1107-3, 29 CFR 1910.1200
- Official top citations: 5 CCR 1001-34, 6 CCR 1007-3 Part 261, 6 CCR 1007-3 Part 8, 6 CCR 1007-2 Part 1, 6 CCR 1007-1 Part 20
- Shared citations: 5 CCR 1001-10, 5 CCR 1002-11, 6 CCR 1007-3, 5 CCR 1001-5, 6 CCR 1007-1, 5 CCR 1001-26
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 29. direct_overlap

A Colorado company wants to treat a production residual as a byproduct rather than waste. What Colorado definitions, exclusions, classifications, documentation requirements, and enforcement risks determine whether that position is legally supportable?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-72, 6 CCR 1007-3, 6 CCR 1007-1, 6 CCR 1007-2
- Official top citations: 5 CCR 1003-2, 5 CCR 1002-61, 5 CCR 1001-34, 6 CCR 1007-2 Part 1, 6 CCR 1007-3 Part 264
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-72, 6 CCR 1007-3, 6 CCR 1007-1, 6 CCR 1007-2
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 30. direct_overlap

A Colorado facility has a permit condition based on projected production levels, but actual throughput has exceeded projections for several months. What Colorado permit modification, deviation reporting, monitoring, recordkeeping, and enforcement authorities apply?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-3, 7 CCR 1103-12, 5 CCR 1001-9
- Official top citations: 5 CCR 1002-61, 5 CCR 1001-5, 5 CCR 1001-28, 6 CCR 1007-3 Part 264, 5 CCR 1001-8
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-3, 5 CCR 1001-9, 5 CCR 1001-11
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 31. direct_overlap

A Colorado manufacturer has one process that emits dust, generates wastewater, creates sludge, uses hazardous chemicals, and requires overtime labor. Build a Colorado-specific legal issue map connecting each operational activity to statutes, regulations, agencies, permits, records, and penalties.

- Geode top citations: 5 CCR 1001-29, 5 CCR 1002-61, 6 CCR 1007-1, 7 CCR 1103-1, 7 CCR 1103-11
- Official top citations: 6 CCR 1007-3 Part 8, 5 CCR 1001-26, 6 CCR 1007-2 Part 1, 6 CCR 1007-3 Part 260, 2 CCR 404-1
- Shared citations: 5 CCR 1002-61
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 32. geode_broader_than_official

A Colorado user searches “we are making more parts now.” Identify all Colorado regulatory domains Geode should infer, including capacity, emissions, wastewater, waste, employee hours, exposure, reporting, and permit applicability.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-1, 7 CCR 1107-1, 29 CFR Part 1904
- Official top citations: none
- Shared citations: none
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Keep Geode behavior; note that the official tool is narrower and CCR-focused. Issue: Geode returned source-backed results while the official CCR search returned none.

### 33. geode_broader_than_official

A Colorado user searches “the process changed but the product did not.” Retrieve Colorado authorities showing why legal obligations may depend on inputs, emissions, discharges, waste streams, employee exposure, or operating conditions rather than final product.

- Geode top citations: 5 CCR 1001-5, 6 CCR 1007-1, 7 CCR 1107-1, 29 U.S.C. 654, 7 CCR 1107-2
- Official top citations: none
- Shared citations: none
- Geode domains: Air, Waste
- Recommendation: Keep Geode behavior; note that the official tool is narrower and CCR-focused. Issue: Geode returned source-backed results while the official CCR search returned none.

### 34. geode_broader_than_official

A Colorado user searches “we need to know if this project can start next week.” Identify Colorado legal checks required before implementation, including permits, notices, inspections, contractor controls, environmental approvals, wage implications, and missing factual predicates.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-63, 6 CCR 1007-3, 7 CCR 1103-15, 8 CCR 1507-25
- Official top citations: none
- Shared citations: none
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Keep Geode behavior; note that the official tool is narrower and CCR-focused. Issue: Geode returned source-backed results while the official CCR search returned none.

### 35. needs_review

A Colorado user searches “we already have approval.” Determine what Colorado authorities distinguish internal business approval, engineering approval, permit approval, agency authorization, local approval, and legally sufficient compliance documentation.

- Geode top citations: 1 CCR 212-3, 1 CCR 203-2, 2 CCR 404-1, 5 CCR 1001-10, 4 CCR 740-1
- Official top citations: 5 CCR 1002-84, 4 CCR 723-4
- Shared citations: none
- Geode domains: Air
- Recommendation: Review whether Geode should boost the official CCR citations for this prompt type. Issue: Both systems returned results, but the top citations did not overlap.

### 36. direct_overlap

A Colorado manufacturing facility is acquiring used equipment from another site and installing it in Colorado. What Colorado air, water, electrical, pressure vessel, safety, waste, construction, and permit modification issues should be reviewed?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-3, 29 CFR Part 1904, 5 CCR 1001-2
- Official top citations: 7 CCR 1101-5, 5 CCR 1001-26, 7 CCR 1101-14, 5 CCR 1001-30, 5 CCR 1001-8
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-3, 5 CCR 1001-2, 5 CCR 1001-30, 5 CCR 1001-29
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 37. direct_overlap

A Colorado plant wants to relocate a production line within the same facility. Determine whether Colorado permits, exposure controls, ventilation, waste handling, wastewater routing, fire code, contractor safety, and employee-training obligations may be triggered.

- Geode top citations: 5 CCR 1002-61, 6 CCR 1007-3, 7 CCR 1107-7, 8 CCR 1507-25, 6 CCR 1007-1
- Official top citations: 5 CCR 1002-61, 6 CCR 1007-3 Part 264, 1 CCR 213-1, 7 CCR 1101-14, 2 CCR 404-1
- Shared citations: 5 CCR 1002-61, 6 CCR 1007-3, 6 CCR 1007-2
- Geode domains: Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 38. direct_overlap

A Colorado facility plans to increase kiln operating hours at night. Identify Colorado air permit, monitoring, nuisance, employee scheduling, overtime, supervision, safety, emergency response, and recordkeeping authorities.

- Geode top citations: 5 CCR 1001-5, 7 CCR 1103-1, 29 CFR 1910.1053, 7 CCR 1103-11, 7 CCR 1103-12
- Official top citations: 5 CCR 1001-9, 5 CCR 1001-2, 5 CCR 1001-3, 6 CCR 1007-3 Part 265, 6 CCR 1007-2 Part 1
- Shared citations: 5 CCR 1001-5
- Geode domains: Air, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 39. direct_overlap

A Colorado manufacturer is moving from manual handling to automated robotics. What Colorado-relevant legal requirements relate to machine guarding, employee training, injury reporting, job changes, layoffs, overtime, production increases, and equipment permitting?

- Geode top citations: 7 CCR 1103-1, 29 CFR 1910.212, 7 CCR 1103-11, 7 CCR 1103-12, 7 CCR 1103-14
- Official top citations: 7 CCR 1103-20, 2 CCR 407-6, 10 CCR 2505-10 8.7000, 7 CCR 1103-1, 3 CCR 719-1
- Shared citations: 7 CCR 1103-1
- Geode domains: Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 40. direct_overlap

A Colorado facility is testing a new filtration system that may reduce emissions but generate a new waste stream. Identify Colorado air permitting, waste characterization, hazardous waste, operational records, maintenance logs, and permit modification issues.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-101, 6 CCR 1007-1, 5 CCR 1001-10, 5 CCR 1001-31
- Official top citations: 6 CCR 1007-2 Part 1, 5 CCR 1001-8, 5 CCR 1001-5, 6 CCR 1007-3 Part 260, 5 CCR 1002-61
- Shared citations: 5 CCR 1001-5, 6 CCR 1007-1, 5 CCR 1001-10, 5 CCR 1001-2, 5 CCR 1001-34
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 41. direct_overlap

A Colorado site has stormwater controls installed but maintenance records are incomplete and outdoor storage has expanded. What Colorado stormwater permit, inspection, corrective action, recordkeeping, and enforcement provisions should be retrieved?

- Geode top citations: 5 CCR 1002-61, CRS-30-20-110.5, 7 CCR 1103-7, 8 CCR 1507-1, 5 CCR 1002-63
- Official top citations: 5 CCR 1002-61, 2 CCR 404-1, 5 CCR 1002-72, 5 CCR 1002-55, 5 CCR 1001-9
- Shared citations: 5 CCR 1002-61, 5 CCR 1002-73, 5 CCR 1002-72
- Geode domains: Water, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 42. direct_overlap

A Colorado plant has wastewater sampling data showing occasional exceedances but no formal enforcement action yet. Identify Colorado reporting, correction, monitoring, permit compliance, records, penalties, and agency communication obligations.

- Geode top citations: 5 CCR 1001-4, 5 CCR 1002-61, 6 CCR 1007-3, 5 CCR 1002-63, 5 CCR 1002-81
- Official top citations: 5 CCR 1002-61, 5 CCR 1001-5, 2 CCR 404-1, 5 CCR 1002-11, 5 CCR 1002-43
- Shared citations: 5 CCR 1002-61, 6 CCR 1007-3, 5 CCR 1002-11
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 43. direct_overlap

A Colorado facility is considering whether to self-disclose a compliance issue involving air permit records, waste labels, and employee training gaps. What Colorado legal authorities, agency policies, enforcement risks, and corrective action records should be reviewed?

- Geode top citations: 5 CCR 1001-10, 6 CCR 1007-1, 7 CCR 1107-1, 29 U.S.C. 654, 5 CCR 1001-15
- Official top citations: 6 CCR 1007-3 Part 8, 6 CCR 1007-2 Part 1, 6 CCR 1007-3 Part 265, 6 CCR 1011-1 Chapter 08, 6 CCR 1007-3 Part 264
- Shared citations: 5 CCR 1001-10
- Geode domains: Air, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 44. direct_overlap

A Colorado manufacturer is preparing an internal audit and wants to classify findings by confirmed violation, likely violation, conditional issue, missing facts, and best-practice gap. What Colorado legal sources should Geode retrieve to support that classification?

- Geode top citations: 5 CCR 1001-9, 5 CCR 1002-43, 6 CCR 1007-1, 5 CCR 1001-26, 5 CCR 1001-13
- Official top citations: 5 CCR 1002-11, 2 CCR 404-1, 6 CCR 1007-3 Part 8, 3 CCR 702-4 Series 4-2, 5 CCR 1001-5
- Shared citations: 5 CCR 1001-26
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 45. geode_broader_than_official

A Colorado company wants a single search result that connects Colorado Revised Statutes, Colorado Code of Regulations, CDPHE materials, CDLE materials, permit programs, agency forms, and enforcement authorities for manufacturing compliance.

- Geode top citations: 5 CCR 1001-10, 5 CCR 1002-61, 6 CCR 1007-3, 6 CCR 1007-1, 6 CCR 1007-2
- Official top citations: 8 CCR 1402-1, 3 CCR 720-1, 5 CCR 1001-9, 5 CCR 1001-5, 4 CCR 723-3
- Shared citations: none
- Geode domains: Air, Water, Waste
- Recommendation: Keep Geode's broader result, but surface the official CCR hits as current-status checks. Issue: Geode returned a broader compliance map than the official CCR search.

### 46. geode_broader_than_official

A Colorado industrial facility has a new manager who asks, “What can get us fined?” Retrieve Colorado environmental, employment, wage, safety, reporting, permit, recordkeeping, and inspection authorities organized by penalty exposure.

- Geode top citations: 5 CCR 1001-10, 5 CCR 1002-61, 6 CCR 1007-3, 7 CCR 1103-15, 8 CCR 1507-3
- Official top citations: none
- Shared citations: none
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Keep Geode behavior; note that the official tool is narrower and CCR-focused. Issue: Geode returned source-backed results while the official CCR search returned none.

### 47. direct_overlap

A Colorado business unit wants to know whether regulatory obligations change when production increases but headcount does not. Identify Colorado legal duties tied to throughput, emissions, discharge, waste generation, employee exposure, records, and permit assumptions.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-3, 7 CCR 1107-7, 8 CCR 1507-25
- Official top citations: 5 CCR 1001-9, 5 CCR 1001-2, 6 CCR 1007-3 Part 100, 6 CCR 1007-2 Part 1, 6 CCR 1007-3 Part 264
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-3, 5 CCR 1001-9
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 48. direct_overlap

A Colorado facility has a near-miss incident involving chemical handling, possible exposure, unlabeled containers, and no injury. What Colorado workplace safety, hazardous materials, spill, training, documentation, and corrective action obligations should be reviewed?

- Geode top citations: 5 CCR 1002-61, 6 CCR 1007-1, 29 CFR 1910.1200, 6 CCR 1007-4, 6 CCR 1007-3
- Official top citations: 6 CCR 1007-3 Part 263, 5 CCR 1001-10, 2 CCR 404-1, 5 CCR 1002-61, 1 CCR 212-3
- Shared citations: 5 CCR 1002-61, 6 CCR 1007-3, 6 CCR 1007-2
- Geode domains: Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 49. direct_overlap

A Colorado manufacturer wants to build a compliance calendar for a facility with air permits, wastewater permits, hazardous waste obligations, stormwater exposure, hourly workers, safety training, and inspection records. Identify the Colorado authorities that create recurring deadlines.

- Geode top citations: 5 CCR 1001-29, 5 CCR 1002-43, 6 CCR 1007-1, 7 CCR 1103-1, 8 CCR 1507-31
- Official top citations: 5 CCR 1002-61, 6 CCR 1007-3 Part 100, 6 CCR 1007-3 Part 264, 6 CCR 1007-3 Part 265, 5 CCR 1003-2
- Shared citations: 5 CCR 1002-43
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 50. direct_overlap

A Colorado ceramics manufacturing facility is making a combined change involving new raw material, increased kiln temperature, added weekend shift, modified wastewater routing, temporary chemical storage, contractor installation work, and expanded outdoor storage. Identify Colorado statutes, regulations, agencies, permit programs, missing facts, likely obligations, conditional obligations, records, deadlines, penalties, and follow-up questions.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-11, 6 CCR 1007-1, 7 CCR 1103-20, 29 CFR 1910.1053
- Official top citations: 5 CCR 1001-10, 6 CCR 1007-3 Part 264, 5 CCR 1001-26, 5 CCR 1001-5, 5 CCR 1001-28
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-11, 6 CCR 1007-2, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.
