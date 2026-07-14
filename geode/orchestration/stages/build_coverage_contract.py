"""Build answer coverage contracts from intent and jurisdiction."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from geode.orchestration.config import load_orchestration_config
from geode.orchestration.contracts import (
    AuthorityLevel,
    CoverageContract,
    CoverageRequirement,
    ExpectedCategory,
    QueryState,
    StageLog,
    StageStatus,
)
from geode.orchestration.stages._stub import PassThroughStage


class BuildCoverageContractStage(PassThroughStage):
    """Define expected categories for a complete answer."""

    def __call__(self, state: QueryState) -> QueryState:
        """Populate a coverage contract from configured category templates."""

        templates = load_orchestration_config()["coverage"]["coverage_templates"]
        question_type = state.intent.question_type.value
        template = templates.get(question_type) or templates["compliance_survey"]
        jurisdiction_requirement = {
            item.authority_level: item.requirement for item in state.jurisdiction_coverage
        }
        categories = [
            _category_from_config(item, CoverageRequirement.REQUIRED)
            for item in template.get("categories", [])
        ]
        for item in template.get("conditional_categories", []):
            authority_level = AuthorityLevel(str(item["authority_level"]))
            requirement = jurisdiction_requirement.get(authority_level, CoverageRequirement.CONDITIONAL)
            categories.append(_category_from_config(item, requirement))

        required_levels = [
            item.authority_level
            for item in state.jurisdiction_coverage
            if item.requirement == CoverageRequirement.REQUIRED
        ]
        state.coverage_contract = CoverageContract(
            required_authority_levels=required_levels,
            jurisdiction_coverage=state.jurisdiction_coverage,
            expected_categories=categories,
            required_entity_ids=[
                entity.canonical_id for entity in state.entities if entity.canonical_id is not None
            ],
            completeness_standard="source-backed",
            completeness_rule=str(template["completeness_rule"]),
        )
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Coverage contract built from configured templates.",
                completed_at=datetime.now(timezone.utc),
                details={
                    "expected_categories": [
                        category.model_dump(mode="json") for category in categories
                    ],
                    "completeness_rule": state.coverage_contract.completeness_rule,
                },
            )
        )
        return state


def _category_from_config(
    item: dict[str, Any],
    requirement: CoverageRequirement,
) -> ExpectedCategory:
    """Build a typed expected category from config."""

    return ExpectedCategory(
        category_id=str(item["category_id"]),
        label=str(item["label"]),
        authority_level=AuthorityLevel(str(item["authority_level"])),
        requirement=requirement,
        retrieval_targets=[str(target) for target in item.get("retrieval_targets", [])],
        reason=str(item["reason"]),
    )
