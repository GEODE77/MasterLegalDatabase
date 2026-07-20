"""Durable, provenance-preserving storage for omitted model evidence."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from geode.orchestration.contracts import Evidence, EvidenceRetrievalReference
from geode.orchestration.services.token_count import TokenCounter


class EvidenceStore:
    """Persist original evidence and its retrieval history in SQLite."""

    def __init__(self, path: Path) -> None:
        """Create or open a durable evidence store."""

        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def put(
        self,
        evidence: Evidence,
        corpus_version: str,
        *,
        retention_seconds: int = 3600,
        reason: str = "excluded_from_immediate_context",
        token_counter: TokenCounter | None = None,
    ) -> EvidenceRetrievalReference:
        """Store original evidence and return an opaque retrieval reference."""

        if retention_seconds < 1:
            raise ValueError("retention_seconds must be positive")
        counter = token_counter or TokenCounter()
        reference_id = _reference_id(evidence, corpus_version)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=retention_seconds)
        payload = json.dumps(evidence.model_dump(mode="json"), sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO evidence_store (
                    reference_id, evidence_id, evidence_json, source_id, source_hash,
                    corpus_version, citation_json, authority_level, created_at,
                    expires_at, retention_seconds, retrieval_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(reference_id) DO UPDATE SET
                    evidence_json=excluded.evidence_json,
                    source_id=excluded.source_id,
                    source_hash=excluded.source_hash,
                    corpus_version=excluded.corpus_version,
                    citation_json=excluded.citation_json,
                    authority_level=excluded.authority_level,
                    expires_at=excluded.expires_at,
                    retention_seconds=excluded.retention_seconds
                """,
                (
                    reference_id,
                    evidence.evidence_id,
                    payload,
                    evidence.provenance.source_id,
                    evidence.provenance.source_hash,
                    corpus_version,
                    json.dumps(evidence.citation.model_dump(mode="json"), sort_keys=True),
                    (evidence.authority_level or evidence.citation.authority_level).value,
                    now.isoformat(),
                    expires_at.isoformat(),
                    retention_seconds,
                ),
            )
        return EvidenceRetrievalReference(
            reference_id=reference_id,
            evidence_id=evidence.evidence_id,
            source_id=evidence.provenance.source_id,
            source_hash=evidence.provenance.source_hash,
            corpus_version=corpus_version,
            original_tokens=counter.count(evidence.text),
            expires_at=expires_at,
            retention_seconds=retention_seconds,
            reason=reason,
        )

    def retrieve(
        self,
        reference_id: str,
        corpus_version: str,
        query: str | None = None,
    ) -> Evidence:
        """Retrieve original evidence after checking reference and corpus version."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM evidence_store WHERE reference_id = ?",
                (reference_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Evidence retrieval reference not found: {reference_id}")
            if row["corpus_version"] != corpus_version:
                raise ValueError(
                    f"Evidence reference belongs to corpus {row['corpus_version']}, "
                    f"not {corpus_version}."
                )
            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at <= datetime.now(timezone.utc):
                raise ValueError(f"Evidence retrieval reference expired: {reference_id}")
            evidence = Evidence.model_validate_json(row["evidence_json"])
            if query and not _matches_query(evidence.text, query):
                raise LookupError(f"Evidence reference has no match for query: {query}")
            retrieved_at = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """
                UPDATE evidence_store
                SET retrieval_count = retrieval_count + 1
                WHERE reference_id = ?
                """,
                (reference_id,),
            )
            connection.execute(
                """
                INSERT INTO evidence_retrieval_events (
                    event_id, reference_id, retrieved_at, query
                ) VALUES (?, ?, ?, ?)
                """,
                (f"ERE-{uuid4().hex}", reference_id, retrieved_at, query),
            )
            return evidence

    def history(self, reference_id: str) -> list[dict[str, str | None]]:
        """Return the recorded retrieval history for one reference."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT retrieved_at, query
                FROM evidence_retrieval_events
                WHERE reference_id = ?
                ORDER BY retrieved_at, event_id
                """,
                (reference_id,),
            ).fetchall()
            exists = connection.execute(
                "SELECT 1 FROM evidence_store WHERE reference_id = ?",
                (reference_id,),
            ).fetchone()
        if exists is None:
            raise KeyError(f"Evidence retrieval reference not found: {reference_id}")
        return [
            {"retrieved_at": item["retrieved_at"], "query": item["query"]}
            for item in rows
        ]

    def _initialize(self) -> None:
        """Create the evidence store schema."""

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_store (
                    reference_id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_hash TEXT,
                    corpus_version TEXT NOT NULL,
                    citation_json TEXT NOT NULL,
                    authority_level TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    retention_seconds INTEGER NOT NULL,
                    retrieval_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_retrieval_events (
                    event_id TEXT PRIMARY KEY,
                    reference_id TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    query TEXT,
                    FOREIGN KEY(reference_id) REFERENCES evidence_store(reference_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_evidence_retrieval_events_reference
                ON evidence_retrieval_events(reference_id, retrieved_at)
                """
            )
            self._migrate_legacy_history(connection)

    def _migrate_legacy_history(self, connection: sqlite3.Connection) -> None:
        """Convert legacy JSON history into append-only retrieval events once."""

        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(evidence_store)").fetchall()
        }
        if "retrieval_history" not in columns:
            return
        rows = connection.execute(
            "SELECT reference_id, retrieval_history FROM evidence_store "
            "WHERE retrieval_history IS NOT NULL AND retrieval_history <> '[]'"
        ).fetchall()
        for row in rows:
            try:
                history = json.loads(row["retrieval_history"])
            except json.JSONDecodeError:
                continue
            for index, item in enumerate(history):
                retrieved_at = item.get("retrieved_at")
                if not retrieved_at:
                    continue
                event_id = hashlib.sha256(
                    f"{row['reference_id']}|{index}|{retrieved_at}|{item.get('query')}".encode(
                        "utf-8"
                    )
                ).hexdigest()
                connection.execute(
                    """
                    INSERT OR IGNORE INTO evidence_retrieval_events
                    (event_id, reference_id, retrieved_at, query)
                    VALUES (?, ?, ?, ?)
                    """,
                    (f"LEGACY-{event_id}", row["reference_id"], retrieved_at, item.get("query")),
                )

    def _connect(self) -> sqlite3.Connection:
        """Open a row-addressable SQLite connection."""

        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


class ControlledEvidenceRetriever:
    """Expose only corpus-checked retrieval actions to orchestration callers."""

    def __init__(self, store: EvidenceStore, corpus_version: str) -> None:
        """Create a retriever bound to one corpus version."""

        self.store = store
        self.corpus_version = corpus_version

    def retrieve(self, reference: EvidenceRetrievalReference, query: str | None = None) -> Evidence:
        """Recover evidence through a validated reference."""

        if reference.corpus_version != self.corpus_version:
            raise ValueError("Retrieval reference is not valid for the active corpus version.")
        return self.store.retrieve(reference.reference_id, self.corpus_version, query=query)

    def retrieve_many(
        self,
        references: list[EvidenceRetrievalReference],
        query: str | None = None,
    ) -> list[Evidence]:
        """Retrieve multiple references through the same corpus and query checks."""

        return [self.retrieve(reference, query=query) for reference in references]


def _reference_id(evidence: Evidence, corpus_version: str) -> str:
    """Build a stable opaque reference from evidence identity and corpus version."""

    raw = "|".join(
        [
            evidence.evidence_id,
            evidence.provenance.source_id,
            evidence.provenance.source_hash or "",
            corpus_version,
        ]
    )
    return f"ER-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]}"


def _matches_query(text: str, query: str) -> bool:
    """Use deterministic meaningful-term matching for scoped retrieval."""

    terms = {
        token
        for token in re.findall(r"[a-z0-9]+", query.casefold())
        if len(token) >= 3
    }
    if not terms:
        return True
    text_terms = set(re.findall(r"[a-z0-9]+", text.casefold()))
    return bool(terms & text_terms)
