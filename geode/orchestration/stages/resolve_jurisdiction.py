"""Resolve jurisdiction coverage across the authority hierarchy."""

from __future__ import annotations

from datetime import datetime, timezone

from geode.orchestration.contracts import (
    AuthorityLevel,
    CoverageRequirement,
    JurisdictionCoverage,
    QueryState,
    StageLog,
    StageStatus,
)
from geode.orchestration.stages._stub import PassThroughStage


class ResolveJurisdictionStage(PassThroughStage):
    """Expand jurisdiction across federal, state, county, and municipal levels."""

    def __call__(self, state: QueryState) -> QueryState:
        """Populate jurisdiction coverage and record location limitations."""

        has_county = state.jurisdiction is not None and state.jurisdiction.county is not None
        has_municipality = (
            state.jurisdiction is not None and state.jurisdiction.municipality is not None
        )
        county_label = (
            state.jurisdiction.county
            if has_county and state.jurisdiction and state.jurisdiction.county
            else "County"
        )
        municipality_label = (
            state.jurisdiction.municipality
            if has_municipality and state.jurisdiction and state.jurisdiction.municipality
            else "Municipal"
        )
        coverage = [
            JurisdictionCoverage(
                authority_level=AuthorityLevel.FEDERAL,
                requirement=CoverageRequirement.REQUIRED,
                label="Federal",
                reason="Federal environmental requirements may apply to emissions.",
            ),
            JurisdictionCoverage(
                authority_level=AuthorityLevel.STATE,
                requirement=CoverageRequirement.REQUIRED,
                label="Colorado",
                reason="The query is scoped to Colorado law by Geode default.",
            ),
            JurisdictionCoverage(
                authority_level=AuthorityLevel.COUNTY,
                requirement=CoverageRequirement.REQUIRED
                if has_county
                else CoverageRequirement.CONDITIONAL,
                label=county_label,
                reason=(
                    "County requirements can be retrieved when facility county is known."
                    if not has_county
                    else "A county location was supplied."
                ),
            ),
            JurisdictionCoverage(
                authority_level=AuthorityLevel.MUNICIPAL,
                requirement=CoverageRequirement.REQUIRED
                if has_municipality
                else CoverageRequirement.CONDITIONAL,
                label=municipality_label,
                reason=(
                    "Municipal requirements can be retrieved when facility municipality is known."
                    if not has_municipality
                    else "A municipal location was supplied."
                ),
            ),
        ]
        state.jurisdiction_coverage = coverage
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Jurisdiction expanded across the authority hierarchy.",
                completed_at=datetime.now(timezone.utc),
                details={
                    "coverage": [item.model_dump(mode="json") for item in coverage],
                    "limitations": [
                        item.reason
                        for item in coverage
                        if item.requirement == CoverageRequirement.CONDITIONAL
                    ],
                },
            )
        )
        return state
