# Geode vs Colorado Rulemaking Search Prompt Comparison

Date: 2026-07-08

## Summary

- Prompts tested: 50
- Geode empty results: 0
- Official empty results: 0
- Direct citation overlap: 49
- Geode broader than official search: 0
- Needs review: 1

## Boundary

This compares Geode's broad legal corpus search to Colorado's official Rulemaking Search, which is a narrower CCR/current-rule search. A lack of official overlap is not automatically a Geode failure.

## Overall Finding

Geode returned results for every prompt. Some prompts need review because the official search surfaced different CCR citations than Geode's top results.

## Prompt Results

### 1. direct_overlap

A Colorado manufacturing facility is installing a temporary pilot kiln while continuing normal production. Identify Colorado air permitting, temporary source, monitoring, employee exposure, waste generation, contractor safety, and recordkeeping obligations.

- Geode top citations: 5 CCR 1001-5, 6 CCR 1007-1, 7 CCR 1103-20, 29 CFR 1910.1053, 6 CCR 1007-2
- Official top citations: 5 CCR 1001-5, 6 CCR 1007-3 Part 8, 5 CCR 1001-30, 6 CCR 1007-3 Part 100, 5 CCR 1002-61
- Shared citations: 5 CCR 1001-5, 6 CCR 1007-2, 6 CCR 1007-3
- Geode domains: Air, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 2. direct_overlap

A Colorado plant is increasing production by extending equipment runtime rather than adding equipment. What Colorado legal authorities determine whether increased operating hours trigger permit, reporting, wage-hour, safety, or inspection obligations?

- Geode top citations: 5 CCR 1001-30, 5 CCR 1002-61, 6 CCR 1007-1, 7 CCR 1103-15, 29 U.S.C. 654
- Official top citations: 2 CCR 404-1, 1 CCR 212-3, 6 CCR 1007-2 Part 1, 7 CCR 1103-15, 5 CCR 1002-61
- Shared citations: 5 CCR 1002-61, 7 CCR 1103-15, 7 CCR 1103-1
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 3. direct_overlap

A Colorado ceramics facility is changing kiln fuel sources. Identify Colorado air quality, emissions calculation, permit modification, equipment safety, utility, reporting, and operational record requirements that may apply.

- Geode top citations: 5 CCR 1001-5, 29 CFR 1910.1053, 5 CCR 1001-1, 5 CCR 1001-10, 5 CCR 1001-11
- Official top citations: 5 CCR 1001-28, 5 CCR 1001-9, 5 CCR 1001-3, 5 CCR 1001-2, 5 CCR 1001-5
- Shared citations: 5 CCR 1001-5, 5 CCR 1001-10, 5 CCR 1001-11
- Geode domains: Air, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 4. direct_overlap

A Colorado manufacturer wants to consolidate several small waste streams into one storage area. What Colorado hazardous waste, solid waste, labeling, accumulation, inspection, compatibility, spill prevention, and documentation rules should be reviewed?

- Geode top citations: 5 CCR 1001-29, 5 CCR 1002-43, 6 CCR 1007-1, 8 CCR 1507-56, 6 CCR 1007-2
- Official top citations: 6 CCR 1007-2 Part 1, 6 CCR 1007-3 Part 8, 6 CCR 1007-3 Part 262, 6 CCR 1007-3 Part 265, 6 CCR 1007-3 Part 267
- Shared citations: 5 CCR 1001-29, 6 CCR 1007-2, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 5. direct_overlap

A Colorado industrial facility is moving raw material unloading from indoors to outdoors. Identify Colorado stormwater, fugitive dust, spill control, material storage, permit, inspection, and local site requirements.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-4, 8 CCR 1507-3, 5 CCR 1001-11
- Official top citations: 5 CCR 1002-61, 6 CCR 1007-3 Part 265, 6 CCR 1007-3 Part 100, 6 CCR 1007-3 Part 260, 6 CCR 1007-2 Part 1
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 5 CCR 1001-29
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 6. direct_overlap

A Colorado plant is adding a dust collection system that may reduce fugitive emissions but create collected particulate waste. What Colorado air, hazardous waste, solid waste, maintenance, monitoring, and disposal obligations could apply?

- Geode top citations: 5 CCR 1001-5, 6 CCR 1007-1, 6 CCR 1007-2, 6 CCR 1007-3, 6 CCR 1007-4
- Official top citations: 5 CCR 1001-8, 6 CCR 1007-3 Part 264, 6 CCR 1007-2 Part 1, 5 CCR 1001-3, 6 CCR 1007-3 Part 260
- Shared citations: 5 CCR 1001-5, 6 CCR 1007-2, 6 CCR 1007-3, 5 CCR 1001-10
- Geode domains: Air, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 7. direct_overlap

A Colorado production team wants to bypass pollution control equipment during maintenance while continuing partial operations. What Colorado permit, emissions, deviation, reporting, enforcement, safety, and documentation authorities should be retrieved?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-1, 29 CFR Part 1904, 5 CCR 1001-9
- Official top citations: 5 CCR 1002-61, 5 CCR 1001-10, 5 CCR 1001-9, 5 CCR 1001-35, 6 CCR 1007-3 Part 265
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 5 CCR 1001-9, 5 CCR 1001-10
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 8. direct_overlap

A Colorado facility is modifying ventilation to improve worker comfort but may change exhaust points and emission pathways. Identify Colorado air permitting, workplace exposure, engineering controls, monitoring, and recordkeeping requirements.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-101, 6 CCR 1007-1, CRS-8-20-803, 8 CCR 1507-1
- Official top citations: 5 CCR 1001-10, 5 CCR 1001-31, 5 CCR 1001-30, 5 CCR 1001-9, 6 CCR 1007-3 Part 8
- Shared citations: 5 CCR 1001-5, 5 CCR 1001-10
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 9. direct_overlap

A Colorado manufacturer is adding chemical pretreatment before wastewater discharge. What Colorado water quality, wastewater permit, pretreatment, sludge disposal, sampling, operator training, and reporting obligations may apply?

- Geode top citations: 5 CCR 1001-29, 5 CCR 1002-43, 6 CCR 1007-1, 8 CCR 1507-31, 5 CCR 1002-61
- Official top citations: 5 CCR 1002-11, 5 CCR 1002-31, 5 CCR 1002-61, 6 CCR 1007-3 Part 100, 5 CCR 1002-86
- Shared citations: 5 CCR 1001-29, 5 CCR 1002-43, 5 CCR 1002-61, 5 CCR 1002-86, 6 CCR 1007-2, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 10. direct_overlap

A Colorado plant is storing production residuals pending a decision on whether they are waste, byproduct, recyclable material, or reusable feedstock. What Colorado definitions, exclusions, storage limits, documentation, and enforcement risks should Geode surface?

- Geode top citations: 5 CCR 1001-30, 5 CCR 1002-72, 6 CCR 1007-3, 6 CCR 1007-1, 6 CCR 1007-2
- Official top citations: 6 CCR 1007-3 Part 8, 5 CCR 1002-61, 6 CCR 1007-3 Part 261, 2 CCR 404-1, 6 CCR 1007-3 Part 260
- Shared citations: 6 CCR 1007-3, 6 CCR 1007-1, 6 CCR 1007-2
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 11. direct_overlap

A Colorado facility is changing production inputs in a way that may alter both SDS obligations and waste characterization. Identify Colorado hazard communication, employee training, hazardous waste determination, spill planning, and records requirements.

- Geode top citations: 5 CCR 1002-11, 6 CCR 1007-3, 7 CCR 1103-11, 29 CFR 1910.1200, 6 CCR 1007-1
- Official top citations: 6 CCR 1007-3 Part 265, 6 CCR 1007-3 Part 262, 6 CCR 1007-2 Part 1, 6 CCR 1007-3 Part 264, 6 CCR 1007-3 Part 100
- Shared citations: 5 CCR 1002-11, 6 CCR 1007-3, 6 CCR 1007-1, 6 CCR 1007-2
- Geode domains: Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 12. direct_overlap

A Colorado manufacturer has multiple contractors performing electrical work, equipment installation, material handling, and waste removal during normal operations. What Colorado-relevant safety, environmental, site-control, incident reporting, and documentation obligations apply?

- Geode top citations: 5 CCR 1001-29, 5 CCR 1002-43, 6 CCR 1007-1, 8 CCR 1507-56, 5 CCR 1001-6
- Official top citations: 6 CCR 1007-3 Part 264, 6 CCR 1007-1 Part 03, 5 CCR 1002-61, 5 CCR 1001-26, 2 CCR 404-1
- Shared citations: 5 CCR 1002-43, 6 CCR 1007-1, 5 CCR 1001-26, 5 CCR 1001-9
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 13. direct_overlap

A Colorado plant is adding a weekend maintenance window that requires overtime, contractor work, hot work, temporary chemical use, and equipment lockout. Identify Colorado wage, safety, environmental, training, permit, and recordkeeping authorities.

- Geode top citations: 5 CCR 1001-10, 5 CCR 1002-86, 6 CCR 1007-1, 7 CCR 1103-1, 29 CFR 1910.147
- Official top citations: 4 CCR 801-1, 1 CCR 201-2, 7 CCR 1103-20, 7 CCR 1101-14, 5 CCR 1001-10
- Shared citations: 5 CCR 1001-10, 7 CCR 1103-1
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 14. direct_overlap

A Colorado facility wants to increase throughput but cap emissions using improved controls. What Colorado rules determine whether projected emissions, actual emissions, potential-to-emit, permit limits, and compliance demonstrations are adequate?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-101, 6 CCR 1007-1, 5 CCR 1001-1, 5 CCR 1001-10
- Official top citations: 2 CCR 404-1, 5 CCR 1001-9, 5 CCR 1001-35, 5 CCR 1001-5, 5 CCR 1001-26
- Shared citations: 5 CCR 1001-5, 5 CCR 1001-10, 5 CCR 1001-11, 5 CCR 1001-13
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 15. direct_overlap

A Colorado manufacturer is changing the location of wastewater sampling points after process modifications. What Colorado permit, monitoring, sample integrity, reporting, and agency-approval requirements should be reviewed?

- Geode top citations: 5 CCR 1001-6, 5 CCR 1002-61, 6 CCR 1007-1, 5 CCR 1002-86, 5 CCR 1001-29
- Official top citations: 5 CCR 1002-11, 5 CCR 1002-43, 6 CCR 1007-3 Part 8, 6 CCR 1007-3 Part 100, 7 CCR 1101-14
- Shared citations: 5 CCR 1002-61, 5 CCR 1002-43, 5 CCR 1001-26, 5 CCR 1001-9
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 16. direct_overlap

A Colorado facility has recurring minor spills in the same production area. Identify Colorado reporting, cleanup, root-cause, employee training, hazardous material storage, permit, and enforcement obligations.

- Geode top citations: 5 CCR 1001-1, 5 CCR 1002-61, 6 CCR 1007-1, 7 CCR 1103-11, 29 U.S.C. 654
- Official top citations: 5 CCR 1001-10, 6 CCR 1007-3 Part 265, 6 CCR 1007-3 Part 264, 6 CCR 1007-1 Part 03, 6 CCR 1007-2 Part 1
- Shared citations: 5 CCR 1002-61, 6 CCR 1007-1, 6 CCR 1007-2, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 17. direct_overlap

A Colorado manufacturing employer is changing pay practices for hourly workers to include production incentives. What Colorado wage calculation, overtime, regular rate, deduction, wage statement, payroll record, and dispute provisions should Geode retrieve?

- Geode top citations: 5 CCR 1001-30, 5 CCR 1002-72, 6 CCR 1007-3, 7 CCR 1103-1, 7 CCR 1103-11
- Official top citations: 7 CCR 1103-1, 10 CCR 2505-10 8.7000, 4 CCR 801-1, 1 CCR 201-2, 10 CCR 2506-1
- Shared citations: 7 CCR 1103-1
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 18. direct_overlap

A Colorado plant is reclassifying lead operators as exempt supervisors while they continue production work. Identify Colorado wage-hour, exemption, overtime, recordkeeping, job duty, and enforcement authorities.

- Geode top citations: 5 CCR 1001-9, 5 CCR 1002-81, 6 CCR 1007-3, 7 CCR 1103-1, 7 CCR 1103-12
- Official top citations: 8 CCR 1203-2, 1 CCR 201-2, 5 CCR 1001-5, 7 CCR 1103-20, 4 CCR 801-1
- Shared citations: 5 CCR 1001-9, 6 CCR 1007-3, 7 CCR 1103-1
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 19. direct_overlap

A Colorado facility is using temporary workers for hazardous production tasks. What Colorado labor, wage, training, safety, injury reporting, staffing-agency, supervision, and recordkeeping obligations should be investigated?

- Geode top citations: 6 CCR 1007-1, 7 CCR 1103-1, 8 CCR 1507-3, 6 CCR 1007-4, 6 CCR 1007-3
- Official top citations: 4 CCR 723-7, 4 CCR 801-1, 7 CCR 1103-20, 7 CCR 1103-1, 10 CCR 2505-10 8.7000
- Shared citations: 7 CCR 1103-1
- Geode domains: Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 20. needs_review

A Colorado manufacturer is reducing headcount through automation while increasing output. Identify Colorado employment, final wage, notice, discrimination, safety retraining, equipment guarding, production-related permit, and record obligations.

- Geode top citations: 7 CCR 1103-11, 29 CFR 1910.212, 7 CCR 1103-1, 7 CCR 1103-12, 7 CCR 1103-14
- Official top citations: 10 CCR 2505-10 8.7000, 8 CCR 1504-9, 4 CCR 801-1, 5 CCR 1001-13, 5 CCR 1001-15
- Shared citations: none
- Geode domains: Labor, Safety
- Recommendation: Review whether Geode should boost the official CCR citations for this prompt type. Issue: Both systems returned results, but the top citations did not overlap.

### 21. direct_overlap

A Colorado plant has employees rotating between production, maintenance, waste handling, and chemical storage duties. What Colorado wage, training, safety, exposure, hazardous waste, and personnel record requirements may apply?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-86, 6 CCR 1007-3, 7 CCR 1103-15, 29 U.S.C. 654
- Official top citations: 6 CCR 1007-2 Part 1, 6 CCR 1007-3 Part 264, 6 CCR 1007-3 Part 265, 7 CCR 1101-14, 6 CCR 1007-3 Part 262
- Shared citations: 5 CCR 1001-5, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 22. direct_overlap

A Colorado facility is changing from day shift only to continuous operations. Identify Colorado overtime, meal/rest period, payroll, supervision, emergency response, permit monitoring, noise, nuisance, and records implications.

- Geode top citations: 5 CCR 1001-1, 5 CCR 1002-101, 6 CCR 1007-1, 7 CCR 1103-1, 29 U.S.C. 654
- Official top citations: 7 CCR 1103-1, 7 CCR 1103-15, 10 CCR 2505-10 8.400, 10 CCR 2505-10 8.7000, 12 CCR 2509-8
- Shared citations: 7 CCR 1103-1
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 23. direct_overlap

A Colorado industrial facility wants to conduct experimental production runs using nonstandard materials. What Colorado air, wastewater, waste classification, employee exposure, permit deviation, pilot authorization, and documentation rules should be reviewed?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-4, 7 CCR 1103-15, 8 CCR 1507-3
- Official top citations: 5 CCR 1001-5, 5 CCR 1002-61, 5 CCR 1003-2, 6 CCR 1007-3 Part 8, 6 CCR 1007-3 Part 265
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 5 CCR 1001-10, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 24. direct_overlap

A Colorado manufacturer is changing cleaning procedures from dry cleanup to wet cleanup. Identify Colorado wastewater, sludge, stormwater, employee exposure, chemical use, waste disposal, and recordkeeping obligations.

- Geode top citations: 5 CCR 1001-29, 5 CCR 1002-43, 6 CCR 1007-1, CRS-8-20-206.5, 8 CCR 1507-31
- Official top citations: 2 CCR 404-1, 5 CCR 1001-10, 5 CCR 1001-23, 7 CCR 1101-14, 6 CCR 1007-3 Part 265
- Shared citations: 5 CCR 1001-29, 5 CCR 1002-61, 6 CCR 1007-2, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 25. direct_overlap

A Colorado plant wants to discharge treated process water for reuse onsite. What Colorado water quality, reuse, discharge, treatment residual, permit, monitoring, and land-application authorities may be relevant?

- Geode top citations: 5 CCR 1001-4, 5 CCR 1002-61, 6 CCR 1007-3, 5 CCR 1002-63, 5 CCR 1002-11
- Official top citations: 5 CCR 1002-86, 5 CCR 1002-84, 5 CCR 1002-11, 6 CCR 1007-3 Part 261, 2 CCR 402-2
- Shared citations: 5 CCR 1002-61, 6 CCR 1007-3, 5 CCR 1002-11, 5 CCR 1002-102, 5 CCR 1002-22
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 26. direct_overlap

A Colorado facility is receiving customer-returned ceramic products for rework, recycling, or disposal. Identify Colorado solid waste, hazardous waste, transportation, storage, product return, recycling, and recordkeeping rules.

- Geode top citations: 5 CCR 1001-26, 5 CCR 1002-64, 6 CCR 1007-3, 7 CCR 1103-7, 6 CCR 1007-4
- Official top citations: 6 CCR 1007-3 Part 260, 6 CCR 1007-3 Part 262, 6 CCR 1007-3 Part 268, 2 CCR 404-1, 6 CCR 1007-3 Part 8
- Shared citations: 6 CCR 1007-3, 6 CCR 1007-2
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 27. direct_overlap

A Colorado manufacturing site is considering onsite crushing of scrap material before disposal or reuse. What Colorado air, dust, waste classification, recycling, stormwater, noise, safety, and permit requirements should be retrieved?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-3, 8 CCR 1507-12, 5 CCR 1001-30
- Official top citations: 6 CCR 1007-3 Part 8, 2 CCR 404-1, 6 CCR 1007-2 Part 1, 6 CCR 1007-3 Part 260, 6 CCR 1007-3 Part 264
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 28. direct_overlap

A Colorado facility plans to install an emergency generator for production continuity. Identify Colorado air permitting, fuel storage, spill prevention, electrical safety, testing limits, maintenance records, and reporting obligations.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-1, 8 CCR 1507-1, 6 CCR 1007-2
- Official top citations: 6 CCR 1007-3 Part 262, 5 CCR 1001-5, 6 CCR 1007-3 Part 100, 6 CCR 1007-3 Part 264, 5 CCR 1001-26
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-2, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 29. direct_overlap

A Colorado plant wants to store chemicals in mobile totes near production lines instead of a centralized storage room. What Colorado hazard communication, spill prevention, fire code, waste, employee exposure, inspection, and record requirements may apply?

- Geode top citations: 5 CCR 1002-11, 6 CCR 1007-3, 7 CCR 1103-11, 29 CFR 1910.1200, 6 CCR 1007-1
- Official top citations: 8 CCR 1203-2, 2 CCR 407-1, 2 CCR 407-4, 5 CCR 1002-11, 5 CCR 1001-5
- Shared citations: 5 CCR 1002-11, 6 CCR 1007-3, 6 CCR 1007-2
- Geode domains: Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 30. direct_overlap

A Colorado manufacturer has changed raw material suppliers several times without updating compliance documentation. Identify Colorado SDS, hazard communication, air permit assumptions, wastewater characteristics, waste determinations, and employee training requirements.

- Geode top citations: 5 CCR 1001-10, 5 CCR 1002-43, 6 CCR 1007-1, 7 CCR 1103-15, 29 CFR 1910.1200
- Official top citations: 6 CCR 1007-3 Part 8, 6 CCR 1007-3 Part 262, 6 CCR 1007-3 Part 261, 6 CCR 1007-3 Part 264, 6 CCR 1007-3 Part 260
- Shared citations: 5 CCR 1001-10, 5 CCR 1002-43, 5 CCR 1001-5, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 31. direct_overlap

A Colorado facility is expanding outdoor laydown areas during construction but believes no environmental permit is needed because the area is temporary. What Colorado stormwater, grading, erosion control, spill, waste storage, and local approval obligations apply?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-1, 6 CCR 1007-2, 6 CCR 1007-3
- Official top citations: 5 CCR 1002-61, 5 CCR 1003-2, 5 CCR 1001-29, 5 CCR 1002-43, 2 CCR 601-18
- Shared citations: 5 CCR 1002-61, 6 CCR 1007-2, 6 CCR 1007-3
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 32. direct_overlap

A Colorado production facility has a wastewater permit but sends some water to evaporation, some to sewer, and some to offsite disposal. Identify Colorado regulatory distinctions, permit obligations, manifests, sampling, reporting, and records.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-1, 5 CCR 1002-63, 5 CCR 1002-81
- Official top citations: 5 CCR 1002-84, 5 CCR 1002-72, 5 CCR 1001-5, 6 CCR 1007-2 Part 1, 6 CCR 1007-3 Part 260
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 5 CCR 1002-32
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 33. direct_overlap

A Colorado plant uses baghouse dust as a possible ingredient in another process. What Colorado rules determine whether this is legitimate reuse, recycling, speculative accumulation, solid waste, hazardous waste, or exempt material?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-4, 6 CCR 1007-3, 5 CCR 1001-8
- Official top citations: 6 CCR 1007-3 Part 8, 6 CCR 1007-3 Part 264, 6 CCR 1007-3 Part 261, 6 CCR 1007-2 Part 1, 6 CCR 1007-3 Part 262
- Shared citations: 5 CCR 1002-61, 6 CCR 1007-3
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 34. direct_overlap

A Colorado industrial site is preparing for ISO-style internal compliance review but needs primary Colorado legal authority rather than best-practice checklists. What Colorado statutes, regulations, agency rules, and permit sources should be retrieved?

- Geode top citations: 5 CCR 1001-1, 5 CCR 1002-101, 6 CCR 1007-1, 5 CCR 1001-10, 5 CCR 1001-11
- Official top citations: 4 CCR 723-3, 6 CCR 1007-3 Part 262, 6 CCR 1007-2 Part 1, 5 CCR 1001-31, 5 CCR 1001-26
- Shared citations: 5 CCR 1001-13
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 35. direct_overlap

A Colorado facility wants to rely on vendor statements that a waste is nonhazardous. What Colorado hazardous waste determination, generator responsibility, documentation, sampling, analytical testing, and liability provisions should be reviewed?

- Geode top citations: 5 CCR 1001-26, 5 CCR 1002-72, 6 CCR 1007-3, 6 CCR 1007-4, 6 CCR 1007-1
- Official top citations: 6 CCR 1007-3 Part 261, 6 CCR 1007-2 Part 1, 6 CCR 1007-3 Part 268, 6 CCR 1007-3 Part 264, 6 CCR 1007-3 Part 262
- Shared citations: 6 CCR 1007-3, 6 CCR 1007-2
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 36. direct_overlap

A Colorado manufacturing facility is modifying process water chemistry but not increasing total discharge volume. What Colorado rules determine whether discharge characteristics, permit limits, monitoring frequency, pretreatment, or reporting obligations change?

- Geode top citations: 5 CCR 1001-31, 5 CCR 1002-61, 6 CCR 1007-3, 5 CCR 1002-102, 5 CCR 1002-63
- Official top citations: 5 CCR 1002-31, 5 CCR 1003-2, 6 CCR 1007-3 Part 264, 5 CCR 1002-38, 2 CCR 407-1
- Shared citations: 5 CCR 1002-61, 6 CCR 1007-3, 5 CCR 1002-102
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 37. direct_overlap

A Colorado plant has employees reporting heat stress near kilns after production hours increased. Identify Colorado-relevant workplace safety, injury reporting, hazard assessment, training, PPE, retaliation, and recordkeeping authorities.

- Geode top citations: 5 CCR 1001-5, CRS-8-43-102, 29 CFR Part 1904, 29 U.S.C. 654, 29 CFR 1910.132
- Official top citations: 7 CCR 1103-15, 6 CCR 1007-3 Part 262, 4 CCR 801-1, 5 CCR 1001-5, 6 CCR 1007-2 Part 1
- Shared citations: 5 CCR 1001-5, 5 CCR 1001-10
- Geode domains: Air, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 38. direct_overlap

A Colorado employer is combining paid sick leave, production attendance policies, disciplinary points, and overtime scheduling. What Colorado leave, wage, retaliation, personnel record, payroll, and employee-notice rules should Geode retrieve?

- Geode top citations: 5 CCR 1001-30, 5 CCR 1002-81, 6 CCR 1007-1, 7 CCR 1103-11, 7 CCR 1103-1
- Official top citations: 4 CCR 801-1, 1 CCR 201-2, 10 CCR 2505-10 8.7000, 10 CCR 2505-5, 7 CCR 1103-7
- Shared citations: 7 CCR 1103-11, 7 CCR 1103-1
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 39. direct_overlap

A Colorado facility is changing waste vendors after a cost-reduction initiative. Identify Colorado cradle-to-grave responsibility, manifest, transporter, disposal facility, record retention, rejected load, and liability obligations.

- Geode top citations: 5 CCR 1001-8, 5 CCR 1002-64, 6 CCR 1007-3, 6 CCR 1007-1, 6 CCR 1007-4
- Official top citations: 6 CCR 1007-3 Part 260, 6 CCR 1007-3 Part 264, 6 CCR 1007-3 Part 265, 6 CCR 1007-3 Part 8, 6 CCR 1007-3 Part 262
- Shared citations: 6 CCR 1007-3, 6 CCR 1007-2
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 40. direct_overlap

A Colorado industrial facility experienced a power outage causing uncontrolled emissions, unscheduled wastewater discharge, employee overtime, and emergency cleanup. What Colorado incident reporting, permit deviation, wage, safety, cleanup, and documentation obligations apply?

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-4, 7 CCR 1103-15, 29 U.S.C. 654
- Official top citations: 6 CCR 1007-3 Part 261, 5 CCR 1001-10, 7 CCR 1101-14, 6 CCR 1007-2 Part 1, 5 CCR 1001-5
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61, 5 CCR 1001-10, 5 CCR 1001-29
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 41. direct_overlap

A Colorado manufacturer is installing new equipment that requires foundation work inside an existing building. Identify Colorado construction, building, safety, contractor, environmental, dust, waste, and permit modification issues.

- Geode top citations: 5 CCR 1001-29, 5 CCR 1002-43, 6 CCR 1007-1, 8 CCR 1507-30, 5 CCR 1001-26
- Official top citations: 8 CCR 1302-14, 5 CCR 1001-5, 6 CCR 1007-3 Part 8, 5 CCR 1001-10, 5 CCR 1001-26
- Shared citations: 5 CCR 1001-29, 5 CCR 1002-43, 5 CCR 1001-26, 5 CCR 1001-9
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 42. direct_overlap

A Colorado facility is changing from solvent-based to water-based materials and assumes compliance risk decreases. What Colorado air, wastewater, hazardous waste, employee safety, SDS, disposal, and permit assumptions should still be checked?

- Geode top citations: 5 CCR 1001-10, 5 CCR 1002-43, 6 CCR 1007-1, 7 CCR 1103-15, 29 CFR 1910.1200
- Official top citations: 6 CCR 1007-3 Part 261, 6 CCR 1007-3 Part 8, 6 CCR 1007-3 Part 268, 6 CCR 1007-3 Part 264, 1 CCR 213-1
- Shared citations: 5 CCR 1001-10, 5 CCR 1002-43, 5 CCR 1001-5, 6 CCR 1007-3
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 43. direct_overlap

A Colorado plant wants to reduce waste by accumulating material longer before shipment. What Colorado accumulation time, generator status, labeling, inspection, storage area, contingency planning, and enforcement provisions apply?

- Geode top citations: 5 CCR 1001-10, 5 CCR 1002-43, 6 CCR 1007-1, 8 CCR 1507-3, 6 CCR 1007-4
- Official top citations: 6 CCR 1007-3 Part 262, 6 CCR 1007-3 Part 8, 6 CCR 1007-3 Part 100, 6 CCR 1007-3 Part 264, 6 CCR 1007-3 Part 268
- Shared citations: 6 CCR 1007-1, 6 CCR 1007-3, 6 CCR 1007-2
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 44. direct_overlap

A Colorado manufacturer is considering treating wastewater sludge onsite before disposal. Identify Colorado water quality, sludge, hazardous waste determination, treatment authorization, air emissions, worker safety, and disposal documentation obligations.

- Geode top citations: 5 CCR 1001-29, 5 CCR 1002-43, 6 CCR 1007-1, 8 CCR 1507-30, 5 CCR 1001-26
- Official top citations: 6 CCR 1007-3 Part 8, 6 CCR 1007-3 Part 261, 6 CCR 1007-3 Part 260, 7 CCR 1101-14, 5 CCR 1001-26
- Shared citations: 5 CCR 1001-26, 5 CCR 1001-8
- Geode domains: Air, Water, Waste, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 45. direct_overlap

A Colorado facility has a production bottleneck at grinding and plans to add a second grinder. What Colorado dust, air permit, noise, employee exposure, machine guarding, waste, maintenance, and monitoring obligations may apply?

- Geode top citations: 5 CCR 1001-5, 6 CCR 1007-1, CRS-8-20-803, 29 CFR 1910.212, 6 CCR 1007-2
- Official top citations: 5 CCR 1001-5, 5 CCR 1001-29, 2 CCR 404-1, 5 CCR 1001-23, 1 CCR 212-3
- Shared citations: 5 CCR 1001-5, 6 CCR 1007-2, 6 CCR 1007-3
- Geode domains: Air, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 46. direct_overlap

A Colorado employer has supervisors editing time records to match scheduled shifts rather than actual production work. Identify Colorado wage-hour, payroll record, overtime, meal/rest period, retaliation, penalty, and audit authorities.

- Geode top citations: 5 CCR 1001-30, 5 CCR 1002-61, 6 CCR 1007-3, 7 CCR 1103-11, 7 CCR 1103-1
- Official top citations: 10 CCR 2505-10 8.7000, 4 CCR 801-1, 10 CCR 2506-1, 7 CCR 1107-7, 7 CCR 1103-7
- Shared citations: 7 CCR 1103-11, 7 CCR 1103-1, 7 CCR 1103-15
- Geode domains: Air, Water, Waste, Labor
- Recommendation: Good result. Keep this prompt in regression testing.

### 47. direct_overlap

A Colorado plant wants to conduct maintenance during lunch breaks to avoid downtime. What Colorado labor, safety, contractor, lockout, hot work, supervision, exposure, and recordkeeping obligations could be implicated?

- Geode top citations: 7 CCR 1103-7, 29 CFR 1910.147, 29 CFR 1910.252, 29 CFR 1910.1053, 29 CFR 1910.212
- Official top citations: 4 CCR 801-1, 8 CCR 1203-2, 5 CCR 1002-61, 6 CCR 1007-2 Part 1, 10 CCR 2506-1
- Shared citations: 5 CCR 1001-10
- Geode domains: Labor, Safety, Waste, Water, Air
- Recommendation: Good result. Keep this prompt in regression testing.

### 48. direct_overlap

A Colorado facility is preparing a permit application using estimated production rates but expects actual production may exceed estimates after startup. What Colorado misrepresentation, permit condition, modification, monitoring, reporting, and enforcement risks should be reviewed?

- Geode top citations: 5 CCR 1001-1, 5 CCR 1002-101, 6 CCR 1007-1, 5 CCR 1001-10, 5 CCR 1001-11
- Official top citations: 5 CCR 1002-61, 5 CCR 1001-9, 5 CCR 1001-29, 6 CCR 1007-3 Part 8, 5 CCR 1001-11
- Shared citations: 5 CCR 1001-10, 5 CCR 1001-11
- Geode domains: Air, Water, Waste
- Recommendation: Good result. Keep this prompt in regression testing.

### 49. direct_overlap

A Colorado ceramics manufacturer wants a single view of compliance obligations by operational trigger: new material, new equipment, higher throughput, modified wastewater, outdoor storage, added shift, contractor work, and waste vendor change.

- Geode top citations: 5 CCR 1001-29, 5 CCR 1002-43, 6 CCR 1007-1, CRS-8-20-206.5, 8 CCR 1507-56
- Official top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-2 Part 1, 5 CCR 1001-26, 5 CCR 1002-11
- Shared citations: 6 CCR 1007-2, 6 CCR 1007-3, 5 CCR 1002-61
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.

### 50. direct_overlap

A Colorado industrial facility is undergoing a combined operational change involving automation, increased kiln hours, new raw material chemistry, wastewater pretreatment, dust collector installation, temporary outdoor storage, staffing changes, and contractor maintenance. Identify Colorado statutes, regulations, agencies, permit programs, records, deadlines, penalties, missing facts, uncertainty levels, and follow-up questions.

- Geode top citations: 5 CCR 1001-5, 5 CCR 1002-61, 6 CCR 1007-1, 7 CCR 1103-20, 29 CFR 1910.1053
- Official top citations: 5 CCR 1003-2, 6 CCR 1007-3 Part 8, 5 CCR 1002-61, 2 CCR 404-1, 6 CCR 1007-3 Part 265
- Shared citations: 5 CCR 1001-5, 5 CCR 1002-61
- Geode domains: Air, Water, Waste, Labor, Safety
- Recommendation: Good result. Keep this prompt in regression testing.
