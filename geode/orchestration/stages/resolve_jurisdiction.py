"""Resolve jurisdiction coverage across the authority hierarchy."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from geode.orchestration.config import load_orchestration_config
from geode.orchestration.contracts import (
    AuthorityLevel,
    CoverageRequirement,
    Jurisdiction,
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

        parsed_location = _parse_configured_location(state)
        if parsed_location:
            state.jurisdiction = _merge_jurisdiction(state, parsed_location)

        has_county = state.jurisdiction is not None and state.jurisdiction.county is not None
        has_municipality = (
            state.jurisdiction is not None and state.jurisdiction.municipality is not None
        )
        has_district = state.jurisdiction is not None and state.jurisdiction.district is not None
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
            JurisdictionCoverage(
                authority_level=AuthorityLevel.DISTRICT,
                requirement=CoverageRequirement.REQUIRED if has_district else CoverageRequirement.CONDITIONAL,
                label=(state.jurisdiction.district if has_district and state.jurisdiction else "District"),
                reason=(
                    "District authority was identified and must be checked."
                    if has_district
                    else "District requirements can be retrieved when a district is known."
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
                    "parsed_location": parsed_location,
                    "limitations": [
                        item.reason
                        for item in coverage
                        if item.requirement == CoverageRequirement.CONDITIONAL
                    ],
                },
            )
        )
        return state


def _parse_configured_location(state: QueryState) -> dict[str, str] | None:
    """Parse a configured county or municipality from the query text."""

    query = (state.intent.normalized_query or state.intent.raw_query).casefold()
    config = load_orchestration_config()["local_jurisdictions"]
    district_match = _match_district(query, config.get("districts", {}))
    if district_match:
        return district_match
    county_match = _match_county(query, config.get("counties", {}))
    municipality_match = _match_municipality(query, config.get("municipalities", {}))

    if county_match:
        return county_match
    return municipality_match


def _match_county(
    query: str,
    counties: dict[str, Any],
) -> dict[str, str] | None:
    """Return a configured county match."""

    for item in counties.values():
        aliases = [str(alias).casefold() for alias in item.get("aliases", [])]
        if any(_contains_place(query, alias) for alias in aliases):
            return {
                "county": str(item["county"]),
                "facility_location": str(item["county"]),
            }
    return None


def _match_municipality(
    query: str,
    municipalities: dict[str, Any],
) -> dict[str, str] | None:
    """Return a configured municipality match."""

    for item in municipalities.values():
        aliases = [str(alias).casefold() for alias in item.get("aliases", [])]
        if any(_contains_place(query, alias) for alias in aliases):
            return {
                "county": str(item["county"]),
                "municipality": str(item["municipality"]),
                "facility_location": str(item["municipality"]),
            }
    return None


def _match_district(query: str, districts: dict[str, Any]) -> dict[str, str] | None:
    """Return a configured district match."""

    for item in districts.values():
        aliases = [str(alias).casefold() for alias in item.get("aliases", [])]
        if any(_contains_place(query, alias) for alias in aliases):
            return {
                "district": str(item["district"]),
                "district_family": str(item.get("district_family", "other")),
                "county": str(item.get("county", "")) or None,
                "facility_location": str(item["district"]),
            }
    return None


def _contains_place(query: str, alias: str) -> bool:
    """Return whether the query contains a configured place alias."""

    padded = f" {query} "
    return f" {alias} " in padded or padded.rstrip(" ?.,;:").endswith(f" {alias}")


def _merge_jurisdiction(
    state: QueryState,
    parsed_location: dict[str, str],
) -> Jurisdiction:
    """Merge parsed local location into the current jurisdiction."""

    existing = state.jurisdiction or Jurisdiction(
        authority_level=AuthorityLevel.STATE,
        authority_levels=[AuthorityLevel.FEDERAL, AuthorityLevel.STATE],
        state="CO",
    )
    levels = list(dict.fromkeys([*existing.authority_levels, AuthorityLevel.COUNTY]))
    if parsed_location.get("municipality") is not None:
        levels.append(AuthorityLevel.MUNICIPAL)
    if parsed_location.get("district") is not None:
        levels.append(AuthorityLevel.DISTRICT)
    return existing.model_copy(
        update={
            "authority_levels": list(dict.fromkeys(levels)),
            "county": parsed_location.get("county") or existing.county,
            "municipality": parsed_location.get("municipality") or existing.municipality,
            "facility_location": parsed_location.get("facility_location")
            or existing.facility_location,
            "district": parsed_location.get("district") or existing.district,
            "district_family": parsed_location.get("district_family") or existing.district_family,
        }
    )
