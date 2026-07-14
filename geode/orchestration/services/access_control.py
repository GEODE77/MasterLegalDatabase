"""Access-control and provenance-integrity checks."""

from __future__ import annotations

from geode.orchestration.contracts import QueryState


class AccessControlService:
    """Enforce provenance integrity and data-governance rules."""

    def validate_state(self, state: QueryState) -> None:
        """Raise when state violates governance rules."""

        for evidence in state.evidence:
            if not evidence.provenance.source_id or not evidence.provenance.source_path:
                raise ValueError(f"evidence missing provenance: {evidence.evidence_id}")
            if evidence.assembled and "_RAW_ARCHIVE" in evidence.provenance.source_path:
                raise ValueError(f"assembled evidence cannot expose raw archive: {evidence.evidence_id}")
            if evidence.assembled and len(evidence.text) > 800:
                raise ValueError(f"assembled evidence exceeds excerpt limit: {evidence.evidence_id}")
