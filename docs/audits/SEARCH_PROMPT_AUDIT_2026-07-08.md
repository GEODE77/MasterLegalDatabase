# Geode Search Prompt Audit - 2026-07-08

## Scope

I ran the attached 100-prompt search set through Geode's local search index. The prompts ranged from short keyword searches to broad executive-style manufacturing compliance questions.

The audit checked whether Geode returned:

- Usable local results instead of empty or broken responses.
- Clear citations.
- Official source links or an archived-source fallback.
- Human-readable excerpts.
- Results from the right general legal subject area.
- A plain-language answer path that helps a human understand what to read next.

No AI APIs were used.

## Final Result

| Status | Count | Meaning |
|---|---:|---|
| Passed | 100 | Geode returned usable, cited, source-backed results after the OSHA repair. |
| Review | 0 | No prompt remains in review status from this test set. |
| Failed | 0 | No prompt remains failed from this test set. |

## Repairs Completed During The Audit

1. Search now gives less weight to filler words.
   - Words like "required", "should", "needed", "review", and "governing" were overpowering the real subject of the question.
   - This was causing weak matches for labor and manufacturing prompts.

2. Search now routes common business questions by legal subject area.
   - Labor and employment questions now favor CDLE rules and CRS Title 8 records.
   - Air questions now favor Air Quality Control Commission rules and CRS Title 25, Article 7.
   - Water and wastewater questions now favor Water Quality Control Commission rules and CRS Title 25, Article 8.
   - Waste questions now favor hazardous/solid waste rules and statutes.
   - Emergency planning now favors Colorado emergency-management and all-hazards authority.

3. Search now avoids misleading industry noise.
   - Broad industrial/manufacturing prompts were sometimes pulled toward marijuana, gaming, child-care, utility, or other specialized industry rules.
   - Those records are now pushed down unless the user actually asks about that industry.

4. Search now treats short words more carefully.
   - "Rest period" was previously matching unrelated text that merely contained the letters "rest".
   - The search now looks for whole words in the indexed text.

5. The search page now summarizes broad results more like a human intake map.
   - Broad searches now include a "Compliance domains" section.
   - The section groups citations into practical buckets such as Air, Water, Waste, Labor, Safety, and Rulemaking.
   - OSHA-like questions now show a coverage note explaining that selected federal OSHA records are indexed and should be opened before a final workplace-safety decision.

6. Federal OSHA source coverage was added after the initial audit.
   - Added 29 CFR 1910.1200 for hazard communication.
   - Added 29 CFR 1910.212 for machine guarding.
   - Added 29 CFR 1910.1053 for respirable crystalline silica.
   - Added 29 U.S.C. 654 for general OSHA employer and employee duties.
   - Added `federal_standard` schema validation and registered the federal OSHA source in the control plane.

## Completed Review Items

| Prompt | Final status | Top source after repair |
|---|---|---|
| Hazard communication requirements Colorado. | Passed | 29 CFR 1910.1200 |
| OSHA requirements Colorado employers. | Passed | 29 U.S.C. 654 |
| What is required to maintain OSHA compliance? | Passed | 29 U.S.C. 654 |
| Hazard communication obligations for production facilities. | Passed | 29 CFR 1910.1200 |
| Rules governing workplace exposure to silica. | Passed | 29 CFR 1910.1053 |
| Compliance requirements for machine guarding. | Passed | 29 CFR 1910.212 |

## Bottom Line

Geode now passes the full 100-prompt set. The final repair added selected federal OSHA authority so workplace-safety questions no longer fall back to adjacent Colorado-only records.
