# Geode Backend Design Principles

Geode is a backend regulatory intelligence database for AI systems, agents,
search, retrieval, ingestion, and legal data analysis.

## 1. Source-Backed Knowledge

Every canonical record must trace back to an official or approved source. Raw
source material is preserved before normalized records are written.

## 2. Jurisdiction Coverage

Geode models Colorado authority in three layers:

1. State
2. County
3. Municipal

State sources are the current foundation. County and municipal sources are not
covered until they are registered, ingested, validated, indexed, and visible in
the manifest.

## 3. Retrieval Before Synthesis

AI agents must retrieve evidence before generating an answer. Retrieval should
use manifests, layer indexes, canonical text, metadata sidecars, crosswalks,
timelines, freshness records, and audit reports.

## 4. Hard Gates Over Prompt Guidance

Prompts and Markdown policies are guidance. Python validation gates are
authoritative. Gates must enforce:

- grounding
- citation verification
- source freshness
- completeness
- faithfulness
- absence verification
- structured output contracts

## 5. Canonical Data Boundaries

The source archive is immutable. Canonical records require schema validation,
atomic writes, and snapshot protection. Derived indexes, API responses, search
databases, and exports can be rebuilt and must not become independent legal
truth.

## 6. Provenance And Auditability

Records should carry source URLs, retrieval dates, hashes, confidence, and
relationship evidence when available. Operational changes should leave
machine-readable audit trails.

## 7. Machine-Readable Structure

Prefer JSONL for metadata and relationship records, Markdown for legal text,
and Pydantic models for validation. Files should be easy for agents to locate,
stream, inspect, and verify.

## 8. Honest Limits

If a source is missing, stale, blocked, ambiguous, or outside Geode coverage,
the system must say so. Unknown coverage must not be filled by inference.

## 9. Improvement Priority

Prefer changes that improve ingestion reliability, source preservation,
metadata quality, crosswalk coverage, search/indexing, retrieval precision,
freshness checks, auditability, or hard verification gates.
