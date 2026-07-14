"""Retrieval backend interfaces and implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from geode.orchestration.contracts import (
    AuthorityLevel,
    Citation,
    Evidence,
    GraphLink,
    Provenance,
    QueryState,
    RetrievalStep,
)
from geode.utils.file_io import iter_jsonl


class RetrievalBackend(Protocol):
    """Backend interface for source retrieval."""

    def search(self, state: QueryState, step: RetrievalStep) -> list[Evidence]:
        """Return candidate evidence for one planned retrieval step."""

    def traverse(self, evidence: Evidence, relationships: list[str]) -> list[Evidence]:
        """Return candidate evidence reached by graph traversal."""


class FixtureRetrievalBackend:
    """In-memory backend for deterministic tests."""

    def __init__(
        self,
        evidence: list[Evidence],
        graph_links: list[GraphLink] | None = None,
    ) -> None:
        """Create a fixture backend."""

        self.evidence = evidence
        self.graph_links = graph_links or []

    def search(self, state: QueryState, step: RetrievalStep) -> list[Evidence]:
        """Return fixture evidence matching the planned category or targets."""

        del state
        return [
            item
            for item in self.evidence
            if item.category_id == step.category_id
            or item.citation.canonical_id in step.targets
            or any(target in item.provenance.source_id for target in step.targets)
        ]

    def traverse(self, evidence: Evidence, relationships: list[str]) -> list[Evidence]:
        """Follow fixture graph links from one evidence record."""

        source_id = evidence.citation.canonical_id or evidence.provenance.source_id
        target_ids = [
            link.target_id
            for link in self.graph_links
            if link.source_id == source_id and link.relationship in relationships
        ]
        reached: list[Evidence] = []
        for item in self.evidence:
            canonical_id = item.citation.canonical_id or item.provenance.source_id
            if canonical_id in target_ids:
                reached.append(
                    item.model_copy(
                        update={
                            "relationship_path": [
                                *evidence.relationship_path,
                                source_id,
                                canonical_id,
                            ]
                        }
                    )
                )
        return reached


class LocalKnowledgeRetrievalBackend:
    """Read-only retrieval backend over local Geode catalog files."""

    def __init__(self, root: Path | None = None) -> None:
        """Create a local retrieval backend."""

        self.root = (root or Path.cwd()).resolve()

    def search(self, state: QueryState, step: RetrievalStep) -> list[Evidence]:
        """Search local retrieval catalog rows for planned targets and query terms."""

        del state
        catalog_path = self.root / "_CONTROL_PLANE" / "RETRIEVAL_CATALOG.jsonl"
        if not catalog_path.exists():
            return []
        candidates: list[Evidence] = []
        for row in iter_jsonl(catalog_path):
            entity_type = str(row.get("entity_type") or "")
            if step.targets and entity_type not in step.targets:
                continue
            source_id = str(row.get("id") or row.get("citation") or "")
            if not source_id:
                continue
            candidates.append(
                Evidence(
                    evidence_id=f"candidate-{source_id}",
                    text=str(row.get("retrieval_text") or row.get("title") or source_id),
                    citation=Citation(
                        citation_text=str(row.get("citation") or source_id),
                        canonical_id=source_id,
                        authority_level=step.authority_level,
                    ),
                    provenance=Provenance(
                        source_id=source_id,
                        source_path=str(row.get("path") or catalog_path.as_posix()),
                    ),
                    confidence=float(row.get("confidence") or 0.5),
                    category_id=step.category_id,
                    is_candidate=True,
                )
            )
        return candidates

    def traverse(self, evidence: Evidence, relationships: list[str]) -> list[Evidence]:
        """Follow local crosswalk rows when available."""

        source_id = evidence.citation.canonical_id or evidence.provenance.source_id
        crosswalk_dir = self.root / "_CROSSWALKS"
        if not crosswalk_dir.exists():
            return []
        reached: list[Evidence] = []
        for path in crosswalk_dir.glob("*.jsonl"):
            for row in iter_jsonl(path):
                if str(row.get("source_id")) != source_id:
                    continue
                if relationships and str(row.get("relationship")) not in relationships:
                    continue
                target_id = str(row.get("target_id") or "")
                if not target_id:
                    continue
                reached.append(
                    Evidence(
                        evidence_id=f"candidate-{target_id}",
                        text=str(row.get("source_evidence") or target_id),
                        citation=Citation(
                            citation_text=target_id,
                            canonical_id=target_id,
                            authority_level=AuthorityLevel.STATE,
                        ),
                        provenance=Provenance(
                            source_id=target_id,
                            source_path=path.as_posix(),
                        ),
                        confidence=float(row.get("confidence") or 0.5),
                        category_id=evidence.category_id,
                        is_candidate=True,
                        relationship_path=[*evidence.relationship_path, source_id, target_id],
                    )
                )
        return reached
