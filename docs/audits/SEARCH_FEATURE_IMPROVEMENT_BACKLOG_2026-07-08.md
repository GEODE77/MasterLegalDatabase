# Geode Search Feature Improvement Backlog

Date: 2026-07-08

## Purpose

This document lists beneficial improvements identified after running the 100-prompt search audit, the 500-prompt search audit, the 100-prompt extreme pressure test, and the search working-order audit.

The goal is to raise Geode search from "working and source-backed" to "executive-review ready": clear, broad enough, precise enough, and easy for a nontechnical user to trust.

## Current Search Status

Geode search is now operating well:

- Prompt sets tested: 700 total prompts across the completed audits.
- Empty results: 0 after repairs.
- Missing citations, excerpts, source URLs, or match reasons: 0 after repairs.
- Search now handles exact CRS/CCR citations, common labor terms, OSHA safety terms, broad manufacturing compliance questions, and multi-domain executive questions.
- Broad manufacturing prompts now return a source spread across air, water, waste, labor, and safety when the question asks for those areas.

The remaining improvements below are not emergency fixes. They are quality, clarity, trust, and scale improvements.

## Highest-Value Improvements

### 1. Add a visible domain coverage panel

Status: Recommended next.

What it would do:

- Show which legal families Geode found in the search results:
  - Air
  - Water
  - Waste
  - Labor
  - Safety
  - Rulemaking
  - Missing facts
- Show which domains were not found or were not clearly asked for.
- Make broad answers easier for a CEO, lawyer, or compliance leader to scan.

Why it matters:

The extreme prompt audit showed that broad manufacturing questions are not just "find one result" questions. Users need to know whether Geode covered the full operating picture. A domain panel would make that visible immediately.

Expected benefit:

- Higher trust.
- Faster executive review.
- Fewer mistaken assumptions that Geode missed a domain.

### 2. Add a "missing facts" section to broad answers

Status: Recommended.

What it would do:

For broad prompts, Geode should list facts needed before anyone can decide applicability, such as:

- What process is changing?
- Are emissions increasing?
- Is wastewater discharged to a stream, sewer, septic system, or reused internally?
- What waste is generated?
- Are chemicals hazardous?
- Are employees hourly, salaried, exempt, or nonexempt?
- Are contractors performing safety-sensitive work?
- Is construction occurring outdoors?
- Are existing permits being modified?

Why it matters:

Many extreme prompts asked for a complete legal answer even though facts were incomplete. A strong legal search tool should not pretend certainty. It should show the likely source path and the missing facts.

Expected benefit:

- Better legal caution.
- Better executive decision-making.
- Better intake workflow.

### 3. Add "confirmed, likely, conditional" result grouping

Status: Recommended.

What it would do:

Group results into:

- Confirmed: directly named by the prompt.
- Likely: strongly related to the facts.
- Conditional: could apply depending on thresholds, exemptions, permit status, or operating facts.

Why it matters:

The extreme prompts repeatedly asked Geode to distinguish confirmed obligations from possible obligations. Search ranking alone cannot communicate that distinction clearly enough.

Expected benefit:

- More human-readable results.
- Better risk prioritization.
- Better support for leadership briefings.

### 4. Add a source hierarchy display

Status: Recommended.

What it would do:

Label each result by source strength:

- Statute
- Regulation
- Rulemaking notice
- Executive order
- Federal standard
- Supplementary report
- Crosswalk relationship

Why it matters:

Users need to know whether they are reading controlling law, implementation rules, history, or supporting material.

Expected benefit:

- Better legal clarity.
- Less confusion between current law and background material.

### 5. Add current-status warnings for rulemaking and CCR results

Status: Recommended.

What it would do:

When a CCR rule appears, show whether Geode has:

- Current rule text.
- Known rulemaking history.
- Pending freshness verification.
- Repealed/newer-version warning, if available.

Why it matters:

Geode has improved rule-history backfill, but live rulemaking status still needs careful verification. Users should see the status boundary.

Expected benefit:

- Better trust in CCR results.
- Lower risk of relying on stale rule text.

## Search Ranking Improvements

### 6. Expand curated business-scenario routing

Status: Recommended.

What it would do:

Add more plain-English business scenarios to the routing system, such as:

- "new process"
- "new product line"
- "line running hotter"
- "different raw material"
- "new vendor"
- "outdoor staging"
- "inspection coming"
- "permit drift"
- "actual operations differ"
- "capital approval"
- "leadership briefing"

Why it matters:

Real users do not always know legal terms. The prompt audits showed that Geode performs best when business language is mapped to legal domains.

Expected benefit:

- Better search results from vague executive questions.

### 7. Improve cross-domain balancing

Status: Partly completed; more refinement recommended.

What it would do:

For broad prompts, Geode should intentionally balance the first page of results across legal families instead of letting one domain dominate.

Current state:

- Basic domain-diversified ranking has been added.
- Further refinement would make the order smarter.

Future refinement:

- Put the most directly triggered domain first.
- Then show related domains in a predictable order.
- Avoid showing too many records from the same rule family.

Expected benefit:

- More complete first-page answers.
- Better CEO-level scan quality.

### 8. Add scenario-specific ranking profiles

Status: Recommended.

What it would do:

Use different ranking behavior depending on query type:

- Exact citation search.
- Narrow topic search.
- Broad compliance inventory.
- Executive briefing.
- Inspection readiness.
- Permit applicability.
- Rule history/status.
- Legal definitions.

Why it matters:

A one-line citation search and a CEO compliance briefing are different tasks. They should not be ranked the same way.

Expected benefit:

- More accurate and more human-feeling results.

### 9. Improve labor routing precision

Status: Partly completed; more refinement recommended.

What it would do:

Keep improving searches for:

- Wage payment.
- Wage theft.
- Final paycheck.
- Overtime.
- Exempt/nonexempt status.
- Payroll records.
- Leave.
- Retaliation.
- Complaints.
- Employee separation.
- Contractors.

Why it matters:

Labor terms overlap heavily. For example, "employee," "wage," "record," and "termination" can point to many different places. More careful routing prevents misleading top results.

Expected benefit:

- Better HR/compliance search quality.

### 10. Improve safety routing precision

Status: Partly completed; more refinement recommended.

What it would do:

Continue improving OSHA and Colorado safety routing for:

- General employer safety duties.
- Injury logs.
- Workplace injury reporting.
- Contractor safety.
- Heat hazards.
- Dust exposure.
- Respirators.
- PPE.
- Lockout/tagout.
- Confined spaces.
- Forklifts.
- Hot work.

Why it matters:

Selected OSHA records were added, but federal workplace-safety coverage is still incomplete.

Expected benefit:

- Better safety search results.
- Clearer coverage boundaries.

## Source Coverage Improvements

### 11. Complete the federal OSHA supplement

Status: Recommended.

What it would do:

Move from selected OSHA records to a fuller workplace-safety source layer.

Potential additions:

- 29 CFR Part 1903: inspections, citations, and penalties.
- 29 CFR Part 1904: expanded injury and illness recordkeeping detail.
- More 29 CFR Part 1910 standards.
- Selected 29 CFR Part 1926 construction standards for construction-related prompts.
- OSHA guidance pages where appropriate, clearly marked as guidance rather than controlling law.

Why it matters:

Many Colorado manufacturing prompts naturally involve federal OSHA. Geode should be transparent about what it has and what it does not have.

Expected benefit:

- Stronger safety coverage.
- Better contractor/construction safety searches.

### 12. Add local government and permit-program source awareness

Status: Recommended.

What it would do:

Add clear warnings and source placeholders for areas where local permits may matter:

- Zoning.
- Building permits.
- Fire code.
- Local pretreatment programs.
- Local stormwater requirements.
- County/municipal waste or storage rules.

Why it matters:

Many manufacturing questions cannot be answered fully from state law alone.

Expected benefit:

- Better scope control.
- Less false confidence.

### 13. Add Colorado agency guidance and forms as separate source types

Status: Recommended.

What it would do:

Index agency materials separately from statutes and rules:

- Forms.
- Permit applications.
- Compliance guides.
- FAQs.
- Enforcement guidance.

Why it matters:

Users often need the operational path, not just the controlling legal text. But guidance must be clearly labeled as nonbinding or implementation material.

Expected benefit:

- More useful practical answers.
- Better source hierarchy.

### 14. Improve rulemaking-current-status integration

Status: Recommended.

What it would do:

Connect CCR search results more visibly to:

- Proposed changes.
- Adopted changes.
- Effective dates.
- Repealed status.
- Newer-version warnings.
- Rulemaking notices.

Why it matters:

Users need to know whether current text is stable or in motion.

Expected benefit:

- Better freshness confidence.
- Stronger rule history answers.

## User Experience Improvements

### 15. Add an executive summary card

Status: Recommended.

What it would do:

At the top of broad results, show:

- "Start here."
- "Likely domains."
- "Most important sources."
- "Missing facts."
- "Open these citations first."

Why it matters:

The current results are source-backed, but a CEO or senior manager needs a compact briefing shape.

Expected benefit:

- Faster understanding.
- Better presentation quality.

### 16. Add a "why this result appeared" explanation by domain

Status: Recommended.

What it would do:

Instead of only saying a result matched text, explain:

- "This appears because the prompt mentioned wastewater."
- "This appears because the prompt mentioned hourly employees."
- "This appears because the prompt mentioned contractor safety."

Why it matters:

Users trust search more when they understand why a result appeared.

Expected benefit:

- More transparent results.
- Easier manual review.

### 17. Add "not enough facts to decide" language

Status: Recommended.

What it would do:

When a user asks "what applies," Geode should say when applicability cannot be decided yet.

Example:

"These are the source areas to review. Applicability depends on discharge route, emissions change, waste classification, employee status, and permit terms."

Why it matters:

Legal search should avoid implying a final compliance conclusion when the facts are incomplete.

Expected benefit:

- Better legal accuracy.
- Less overstatement.

### 18. Add follow-up question suggestions

Status: Recommended.

What it would do:

After broad searches, suggest next searches such as:

- "air permit modification thresholds"
- "industrial wastewater discharge route"
- "hazardous waste generator classification"
- "hourly employee overtime records"
- "contractor safety OSHA duties"

Why it matters:

Users often do not know the next legal question to ask.

Expected benefit:

- Better guided research workflow.

### 19. Add "domain not found" warnings

Status: Recommended.

What it would do:

If the user asks for air, water, waste, labor, and safety but Geode only finds air and water, the UI should say:

"No strong waste, labor, or safety source appeared in the top results. Try adding more facts or open the domain filters."

Why it matters:

Not finding a domain is important information.

Expected benefit:

- Better transparency.
- Less hidden failure.

### 20. Add filters for authority type and legal family

Status: Recommended.

What it would do:

Allow users to narrow results by:

- Statutes.
- Regulations.
- Rulemaking.
- Federal standards.
- Agency guidance.
- Air.
- Water.
- Waste.
- Labor.
- Safety.

Why it matters:

Broad searches can return many valid sources. Filters let the user move from broad map to focused review.

Expected benefit:

- Faster navigation.
- Better legal research workflow.

## Testing and Quality Improvements

### 21. Keep the prompt audit sets as permanent regression tests

Status: Recommended.

What it would do:

Turn the prompt sets into a repeatable test suite:

- Easy prompts.
- Medium prompts.
- Hard prompts.
- Extreme executive prompts.
- Citation-specific prompts.
- Domain-coverage prompts.

Why it matters:

Search quality can regress easily when ranking rules change.

Expected benefit:

- Better long-term reliability.

### 22. Add an automated search-quality score

Status: Recommended.

What it would do:

Score every test prompt on:

- Empty result check.
- Citation check.
- Source URL check.
- Excerpt check.
- Domain coverage check.
- Exact citation priority.
- Top-result relevance.
- Result diversity.

Why it matters:

Right now audits are effective but somewhat manual.

Expected benefit:

- Faster search QA.
- Easier release decisions.

### 23. Add manual-review labels to audit output

Status: Recommended.

What it would do:

When a prompt is flagged, classify the reason:

- True failure.
- Broad-but-acceptable.
- Checker overreach.
- Missing source coverage.
- Needs better ranking.
- Needs UI explanation.

Why it matters:

Not every flagged prompt means the same thing.

Expected benefit:

- Cleaner triage.

### 24. Add snapshot comparison for search changes

Status: Recommended.

What it would do:

Compare current search results against the prior search database:

- What improved?
- What got worse?
- Which top citations changed?

Why it matters:

Ranking changes can have unexpected side effects.

Expected benefit:

- Safer search tuning.

## Data and Indexing Improvements

### 25. Enrich sparse CCR titles

Status: Recommended.

What it would do:

Many CCR records have generic titles like `5 CCR 1001-5`. Add better human-readable labels where possible.

Why it matters:

Search results are harder to understand when the title is just a citation.

Expected benefit:

- Better readability.
- Better executive review.

### 26. Add domain tags to indexed records

Status: Recommended.

What it would do:

Every searchable record should carry high-level domain tags:

- Air.
- Water.
- Waste.
- Labor.
- Safety.
- Rulemaking.
- Emergency.
- Construction.
- Local.

Why it matters:

Current domain detection is mostly inferred from IDs, citations, titles, and text. Explicit tags would be more reliable.

Expected benefit:

- Better ranking.
- Better filtering.
- Better coverage displays.

### 27. Add obligation-type tags

Status: Recommended.

What it would do:

Tag records by obligation type:

- Permit.
- Report.
- Recordkeeping.
- Training.
- Inspection.
- Notice.
- Fee.
- Penalty.
- Exemption.
- Definition.

Why it matters:

Many prompts ask for specific obligation types.

Expected benefit:

- More precise search.
- Better compliance matrices.

### 28. Add agency tags

Status: Recommended.

What it would do:

Tag records by agency:

- CDPHE Air Pollution Control Division.
- Water Quality Control Division.
- Hazardous Materials and Waste Management Division.
- Colorado Department of Labor and Employment.
- Division of Workers' Compensation.
- OSHA/federal.

Why it matters:

Users often need to know who administers the requirement.

Expected benefit:

- Better agency-centered answers.

## Longer-Term Search Improvements

### 29. Build a retrieval planner before ranking

Status: Future improvement.

What it would do:

Before retrieving records, classify the question:

- What domains are present?
- What facts are missing?
- What authority types are needed?
- Is the user asking for a conclusion, a map, a checklist, or a citation?

Why it matters:

The best result set depends on the user’s task.

Expected benefit:

- More human and more reliable search behavior without using AI APIs.

### 30. Add a query rewrite layer without AI APIs

Status: Future improvement.

What it would do:

Use deterministic synonym expansion:

- "plant" -> manufacturing facility, industrial site.
- "new kiln" -> air emissions, heat, dust, equipment, construction, permit.
- "process water" -> wastewater, discharge, pretreatment, stormwater.
- "weekend shift" -> overtime, wage order, payroll records, leave, staffing.

Why it matters:

Users search with operational language, not legal vocabulary.

Expected benefit:

- Better plain-English search.

### 31. Build a legal-domain knowledge map

Status: Future improvement.

What it would do:

Connect domains and triggers:

- Air emissions -> permits, reporting, monitoring, enforcement.
- Wastewater -> discharge, pretreatment, stormwater, sampling.
- Hazardous waste -> generator status, labeling, accumulation, manifests.
- Labor -> wage, overtime, leave, records, retaliation.
- Safety -> OSHA duties, training, injury logs, exposure controls.

Why it matters:

This would make Geode reason more like a compliance intake system.

Expected benefit:

- Stronger broad answers.
- Better domain completeness.

## Recommended Implementation Order

1. Build the visible domain coverage panel.
2. Add missing-facts and confirmed/likely/conditional sections.
3. Add source hierarchy labels.
4. Convert prompt sets into repeatable regression tests.
5. Add domain, obligation-type, and agency tags to indexed records.
6. Complete the federal OSHA supplement.
7. Add local-government and permit-program coverage warnings.
8. Add deterministic query rewrite and retrieval planning.

## Bottom Line

Geode search is now functioning well across the completed prompt sets. The next gains are mostly about making the answer easier to trust, easier to scan, and more clearly organized for executive and legal review.
