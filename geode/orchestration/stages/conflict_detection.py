"""Detect contradictions between assembled evidence items."""

from __future__ import annotations

from datetime import datetime, timezone

from geode.orchestration.contracts import (
    AuthorityLevel,
    ConflictReport,
    ConflictStatus,
    Evidence,
    QueryState,
    StageLog,
    StageStatus,
)
from geode.orchestration.stages._stub import PassThroughStage

AUTHORITY_RANK = {
    AuthorityLevel.FEDERAL: 4,
    AuthorityLevel.STATE: 3,
    AuthorityLevel.COUNTY: 2,
    AuthorityLevel.MUNICIPAL: 1,
}


class ConflictDetectionStage(PassThroughStage):
    """Identify seeded contradictions without hiding them."""

    def __call__(self, state: QueryState) -> QueryState:
        """Attach conflict reports to query state."""

        conflicts = _detect_conflicts(state.evidence)
        state.conflicts = conflicts
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Evidence conflicts detected for disclosure.",
                completed_at=datetime.now(timezone.utc),
                details={"conflicts": [item.model_dump(mode="json") for item in conflicts]},
            )
        )
        return state


def _detect_conflicts(evidence: list[Evidence]) -> list[ConflictReport]:
    """Detect simple contradiction markers in evidence text."""

    conflicts: list[ConflictReport] = []
    by_group: dict[str, list[Evidence]] = {}
    for item in evidence:
        group = item.conflict_group or item.category_id or "general"
        by_group.setdefault(group, []).append(item)
    for group, items in by_group.items():
        required = [item for item in items if _contains_any(item.text, ("must", "required", "shall"))]
        prohibited = [
            item
            for item in items
            if _contains_any(item.text, ("not required", "exempt", "prohibited"))
        ]
        if not required or not prohibited:
            continue
        pair = [required[0], prohibited[0]]
        conflicts.append(_conflict_for_pair(group, pair))
    return conflicts


def _conflict_for_pair(group: str, pair: list[Evidence]) -> ConflictReport:
    """Build a conflict report with hierarchy handling when possible."""

    ranked = sorted(
        pair,
        key=lambda item: AUTHORITY_RANK.get(item.authority_level or item.citation.authority_level, 0),
        reverse=True,
    )
    high = ranked[0]
    low = ranked[1]
    high_level = high.authority_level or high.citation.authority_level
    low_level = low.authority_level or low.citation.authority_level
    if high_level != low_level:
        return ConflictReport(
            conflict_id=f"conflict-{group}",
            evidence_ids=[item.evidence_id for item in pair],
            category_id=group,
            description="Evidence sources appear to conflict.",
            status=ConflictStatus.RESOLVED_BY_HIERARCHY,
            resolution=(
                f"{high_level.value} authority is ranked above {low_level.value}; "
                "the lower-ranked source remains disclosed."
            ),
        )
    return ConflictReport(
        conflict_id=f"conflict-{group}",
        evidence_ids=[item.evidence_id for item in pair],
        category_id=group,
        description="Evidence sources appear to conflict at the same authority level.",
        status=ConflictStatus.UNRESOLVED,
        resolution=None,
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    """Return whether any term appears in text."""

    lowered = text.casefold()
    return any(term in lowered for term in terms)
