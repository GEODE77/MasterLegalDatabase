"""Command-line query bridge for the Geode read index."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path


STOP_WORDS = {
    "the",
    "and",
    "for",
    "are",
    "what",
    "which",
    "with",
    "from",
    "that",
    "this",
    "does",
    "into",
    "about",
    "colorado",
    "law",
    "laws",
    "rule",
    "rules",
    "regulation",
    "regulations",
    "requirement",
    "requirements",
}


@dataclass(frozen=True)
class QueryResult:
    """One API-ready read-index result."""

    id: str
    title: str
    citation: str
    excerpt: str
    body: str
    score: float
    sourceUrl: str | None
    layer: str
    entityType: str
    matchReasons: tuple[str, ...]
    relationshipCount: int


@dataclass(frozen=True)
class QueryIntent:
    """Authority type hints detected from the user's query."""

    anchor_terms: frozenset[str]
    preferred_entity_types: frozenset[str]
    preferred_layers: frozenset[str]
    topic_terms: frozenset[str]
    wants_connected_authority: bool
    wants_obligations: bool


def query_index(database_path: Path, query: str, limit: int = 8) -> list[QueryResult]:
    """Return ranked search results from the read index."""

    tokens = _tokens(query)
    if not tokens:
        return []
    intent = _query_intent(query)
    search_terms = _search_terms(tokens, intent)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        relation_counts = _relation_counts(connection)
        scored: dict[str, QueryResult] = {}
        _score_alias_match(connection, query, scored, intent, relation_counts)
        _score_metadata_matches(connection, search_terms, scored, intent, relation_counts)
        _score_chunk_matches(connection, tokens, search_terms, scored, intent, relation_counts)
    return sorted(scored.values(), key=lambda item: item.score, reverse=True)[:limit]


def _score_alias_match(
    connection: sqlite3.Connection,
    query: str,
    scored: dict[str, QueryResult],
    intent: QueryIntent,
    relation_counts: dict[str, int],
) -> None:
    """Add a strong hit when the query resolves to a known alias."""

    row = connection.execute(
        """
        SELECT e.*, c.text AS chunk_text
        FROM aliases a
        JOIN entities e ON e.geode_id = a.geode_id
        LEFT JOIN chunks c ON c.geode_id = e.geode_id AND c.chunk_index = 0
        WHERE a.alias = ?
        LIMIT 1
        """,
        (_normalize(query),),
    ).fetchone()
    if row is not None:
        relation_count = relation_counts.get(row["geode_id"], 0)
        result = _result_from_row(
            row,
            250 + _intent_boost(row, intent) + _relationship_boost(relation_count, intent),
            query,
            _reason_list(row, intent, relation_count, "Matched a known citation or alias."),
            relation_count,
        )
        scored[result.id] = result


def _score_metadata_matches(
    connection: sqlite3.Connection,
    search_terms: list[str],
    scored: dict[str, QueryResult],
    intent: QueryIntent,
    relation_counts: dict[str, int],
) -> None:
    """Score title, citation, ID, and entity metadata."""

    for row in connection.execute(
        """
        SELECT e.*, c.text AS chunk_text
        FROM entities e
        LEFT JOIN chunks c ON c.geode_id = e.geode_id AND c.chunk_index = 0
        ORDER BY e.geode_id
        """
    ):
        haystack = _normalize(
            " ".join(
                value or ""
                for value in [row["geode_id"], row["title"], row["citation"], row["entity_type"]]
            )
        )
        if not _passes_anchor_filter(haystack, intent):
            continue
        score = sum(24 for token in search_terms if _contains_term(haystack, token))
        score += _operational_boost(row, "", intent)
        if score <= 0:
            continue
        relation_count = relation_counts.get(row["geode_id"], 0)
        _merge_result(
            scored,
            _result_from_row(
                row,
                score + _intent_boost(row, intent) + _relationship_boost(relation_count, intent),
                " ".join(search_terms),
                _reason_list(
                    row,
                    intent,
                    relation_count,
                    "Matched the title, citation, ID, or record type.",
                ),
                relation_count,
            ),
        )


def _score_chunk_matches(
    connection: sqlite3.Connection,
    tokens: list[str],
    search_terms: list[str],
    scored: dict[str, QueryResult],
    intent: QueryIntent,
    relation_counts: dict[str, int],
) -> None:
    """Score full-text chunks."""

    first_token = tokens[0]
    rows = connection.execute(
        """
        SELECT e.*, c.text AS chunk_text, c.normalized_text AS normalized_text
        FROM chunks c
        JOIN entities e ON e.geode_id = c.geode_id
        WHERE c.normalized_text LIKE ?
        ORDER BY e.geode_id, c.chunk_index
        LIMIT 2000
        """,
        (f"%{first_token}%",),
    ).fetchall()
    for row in rows:
        normalized = row["normalized_text"]
        if not _passes_anchor_filter(normalized, intent):
            continue
        matched_terms = [term for term in search_terms if _contains_term(normalized, term)]
        if len(matched_terms) < _minimum_chunk_matches(tokens):
            continue
        score = 40 + sum(min(normalized.count(term), 12) for term in matched_terms)
        score += _operational_boost(row, normalized, intent)
        relation_count = relation_counts.get(row["geode_id"], 0)
        _merge_result(
            scored,
            _result_from_row(
                row,
                score + _intent_boost(row, intent) + _relationship_boost(relation_count, intent),
                " ".join(tokens),
                _reason_list(
                    row,
                    intent,
                    relation_count,
                    "Matched source text in the indexed record.",
                ),
                relation_count,
            ),
        )


def _merge_result(scored: dict[str, QueryResult], result: QueryResult) -> None:
    """Keep the highest-scoring result for an entity."""

    existing = scored.get(result.id)
    if existing is None or result.score > existing.score:
        scored[result.id] = result


def _result_from_row(
    row: sqlite3.Row,
    score: float,
    query: str,
    reasons: tuple[str, ...],
    relation_count: int,
) -> QueryResult:
    """Build an API result from a joined entity/chunk row."""

    citation = row["citation"] or row["geode_id"]
    body = row["chunk_text"] or row["title"]
    return QueryResult(
        id=row["geode_id"],
        title=row["title"],
        citation=citation,
        excerpt=_excerpt(body, query),
        body=body,
        score=score,
        sourceUrl=row["source_url"] or None,
        layer=row["layer"],
        entityType=row["entity_type"],
        matchReasons=reasons,
        relationshipCount=relation_count,
    )


def _tokens(value: str) -> list[str]:
    """Return useful query terms."""

    normalized = _normalize(value)
    return [
        token
        for token in normalized.split()
        if len(token) >= 3 and token not in STOP_WORDS
    ]


def _query_intent(query: str) -> QueryIntent:
    """Detect explicit authority-type words in the query."""

    normalized = _normalize(query)
    entity_types: set[str] = set()
    layers: set[str] = set()

    if "executive order" in normalized or "governor order" in normalized:
        entity_types.add("executive_order")
        layers.add("05_Executive_Orders")
    if "ag opinion" in normalized or "attorney general opinion" in normalized:
        entity_types.add("ag_opinion")
        layers.add("07_Supplementary")
    if "session law" in normalized or "chapter law" in normalized:
        entity_types.add("session_law")
        layers.add("06_Session_Laws")
    if "rulemaking" in normalized or "edocket" in normalized or "notice of rulemaking" in normalized:
        entity_types.add("rulemaking_notice")
        layers.add("04_Rulemaking")
    if "bill" in normalized or "legislation" in normalized:
        entity_types.add("bill")
        layers.add("03_Legislation")
    if "crs" in normalized or "revised statute" in normalized or "statute" in normalized:
        entity_types.add("statute_section")
        layers.add("01_Statutes_CRS")
    if "ccr" in normalized or "code of colorado regulations" in normalized:
        entity_types.update(["regulation_rule", "regulation_rule_acquisition"])
        layers.add("02_Regulations_CCR")

    topic_terms = _topic_terms(normalized)
    anchor_terms = _anchor_terms(normalized)
    wants_obligations = any(
        term in normalized
        for term in [
            "obligation",
            "obligations",
            "compliance",
            "comply",
            "duties",
            "duty",
            "require",
            "requires",
            "requirements",
            "must",
            "shall",
        ]
    )
    wants_connected_authority = any(
        term in normalized
        for term in ["connect", "connected", "related", "relationship", "authority", "under"]
    )
    if topic_terms or wants_obligations:
        entity_types.update(["regulation_rule", "regulation_rule_acquisition", "statute_section"])
        layers.update(["01_Statutes_CRS", "02_Regulations_CCR"])

    return QueryIntent(
        anchor_terms=frozenset(anchor_terms),
        preferred_entity_types=frozenset(entity_types),
        preferred_layers=frozenset(layers),
        topic_terms=frozenset(topic_terms),
        wants_connected_authority=wants_connected_authority,
        wants_obligations=wants_obligations,
    )


def _intent_boost(row: sqlite3.Row, intent: QueryIntent) -> int:
    """Return a ranking boost when a row matches an explicit authority type."""

    boost = 0
    if row["entity_type"] in intent.preferred_entity_types:
        boost += 120
    if row["layer"] in intent.preferred_layers:
        boost += 60
    return boost


def _operational_boost(row: sqlite3.Row, normalized_text: str, intent: QueryIntent) -> int:
    """Return a boost for operational topic and obligation matches."""

    if not intent.topic_terms and not intent.wants_obligations:
        return 0
    haystack = normalized_text or _normalize(
        " ".join(
            value or ""
            for value in [row["geode_id"], row["title"], row["citation"], row["entity_type"]]
        )
    )
    boost = 0
    topic_hits = [term for term in intent.topic_terms if _contains_term(haystack, term)]
    if topic_hits:
        boost += min(len(topic_hits), 5) * 14
    if intent.wants_obligations and _has_obligation_language(haystack):
        boost += 52
    return boost


def _relationship_boost(relation_count: int, intent: QueryIntent) -> int:
    """Return a boost for records connected to other authority."""

    if relation_count <= 0:
        return 0
    base = min(relation_count, 5) * 6
    if intent.wants_connected_authority or intent.topic_terms or intent.wants_obligations:
        base += 28
    return base


def _reason_list(
    row: sqlite3.Row,
    intent: QueryIntent,
    relation_count: int,
    base_reason: str,
) -> tuple[str, ...]:
    """Return plain-English reasons for why the result was surfaced."""

    reasons: list[str] = []
    if row["entity_type"] in intent.preferred_entity_types:
        reasons.append("Matched the requested authority type.")
    if row["layer"] in intent.preferred_layers:
        reasons.append("Matched the requested source layer.")
    if intent.topic_terms:
        reasons.append("Matched an operational topic in the question.")
    if intent.wants_obligations:
        reasons.append("Matched obligation or compliance language.")
    if relation_count > 0:
        reasons.append("Connected to related authority in Geode.")
    reasons.append(base_reason)
    return tuple(dict.fromkeys(reasons))


def _relation_counts(connection: sqlite3.Connection) -> dict[str, int]:
    """Return relationship counts keyed by entity ID."""

    counts: dict[str, int] = {}
    for row in connection.execute("SELECT source_geode_id, target_geode_id FROM relations"):
        counts[row["source_geode_id"]] = counts.get(row["source_geode_id"], 0) + 1
        counts[row["target_geode_id"]] = counts.get(row["target_geode_id"], 0) + 1
    return counts


def _search_terms(tokens: list[str], intent: QueryIntent) -> list[str]:
    """Return search terms with conservative operational synonyms."""

    terms = [*tokens, *sorted(intent.topic_terms)]
    if intent.wants_obligations:
        terms.extend(["shall", "must", "required", "permit", "record", "report"])
    return list(dict.fromkeys(terms))


def _minimum_chunk_matches(tokens: list[str]) -> int:
    """Return the minimum number of terms a chunk must contain."""

    if len(tokens) <= 1:
        return 1
    return 2


def _passes_anchor_filter(normalized: str, intent: QueryIntent) -> bool:
    """Return false when a broad operational query lacks its real topic anchor."""

    if not intent.anchor_terms:
        return True
    return any(_contains_term(normalized, term) for term in intent.anchor_terms)


def _topic_terms(normalized: str) -> set[str]:
    """Map common operational language to source-text terms."""

    groups = {
        ("air", "emission", "emissions", "pollution"): {
            "air",
            "emission",
            "emissions",
            "pollutant",
            "pollution",
        },
        ("permit", "permitting", "license", "approval"): {
            "permit",
            "permitting",
            "license",
            "approval",
        },
        ("report", "reporting", "notice", "notify"): {
            "report",
            "reporting",
            "notice",
            "notify",
        },
        ("record", "records", "recordkeeping"): {
            "record",
            "records",
            "recordkeeping",
        },
        ("inspect", "inspection", "inspections"): {
            "inspect",
            "inspection",
            "inspections",
        },
        ("manufacturing", "manufacturer", "facility", "production"): {
            "manufacturing",
            "manufacturer",
            "facility",
            "industrial",
            "production",
        },
        ("waste", "hazardous", "solid waste"): {
            "waste",
            "hazardous",
            "solid",
            "disposal",
        },
    }
    terms: set[str] = set()
    for triggers, expanded in groups.items():
        if any(trigger in normalized for trigger in triggers):
            terms.update(expanded)
    return terms


def _anchor_terms(normalized: str) -> set[str]:
    """Return stronger topic anchors that broad words must connect to."""

    anchors: set[str] = set()
    anchor_groups = {
        ("air", "emission", "emissions", "pollution"): {
            "air",
            "emission",
            "emissions",
            "pollutant",
            "pollution",
        },
        ("manufacturing", "manufacturer", "facility", "production"): {
            "manufacturing",
            "manufacturer",
            "industrial",
            "production",
        },
        ("waste", "hazardous", "solid waste"): {
            "waste",
            "hazardous",
            "solid",
            "disposal",
        },
    }
    for triggers, expanded in anchor_groups.items():
        if any(trigger in normalized for trigger in triggers):
            anchors.update(expanded)
    return anchors


def _has_obligation_language(normalized: str) -> bool:
    """Return true when source text contains duty or compliance language."""

    return any(
        _contains_term(normalized, term)
        for term in [
            "shall",
            "must",
            "required",
            "requires",
            "prohibited",
            "may not",
            "permit",
            "report",
            "record",
            "inspection",
        ]
    )


def _contains_term(normalized: str, term: str) -> bool:
    """Return true when a normalized text contains a full normalized term."""

    return f" {term} " in f" {normalized} "


def _normalize(value: str) -> str:
    """Normalize lookup and search text."""

    return " ".join(
        value.casefold()
        .replace(".", " ")
        .replace(",", " ")
        .replace("-", " ")
        .replace("_", " ")
        .split()
    )


def _excerpt(body: str, query: str) -> str:
    """Return a compact excerpt around the first query hit."""

    clean = " ".join(body.split())
    tokens = _tokens(query)
    indexes = [
        clean.casefold().find(token)
        for token in tokens
        if clean.casefold().find(token) >= 0
    ]
    start = max(0, (min(indexes) if indexes else 0) - 160)
    end = min(len(clean), start + 460)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean) else ""
    return f"{prefix}{clean[start:end]}{suffix}"


def main() -> None:
    """Run the query bridge and print JSON results."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    results = query_index(Path(args.database), args.query, args.limit)
    print(json.dumps([asdict(result) for result in results], ensure_ascii=False))


if __name__ == "__main__":
    main()
