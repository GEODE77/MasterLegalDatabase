"""Command-line query bridge for the Geode read index."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


STOP_WORDS = {
    "the",
    "and",
    "all",
    "applicable",
    "applies",
    "apply",
    "areas",
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
    "regulatory",
    "require",
    "required",
    "requires",
    "requirement",
    "requirements",
    "after",
    "affect",
    "affecting",
    "before",
    "common",
    "create",
    "determine",
    "evaluate",
    "exist",
    "exists",
    "explain",
    "expand",
    "expanding",
    "expansion",
    "govern",
    "governing",
    "identify",
    "leadership",
    "line",
    "likely",
    "major",
    "needed",
    "primary",
    "probably",
    "review",
    "should",
    "state",
    "understand",
    "would",
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
    domain_terms: frozenset[str]
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
        _score_direct_identifier_match(connection, query, scored, intent, relation_counts)
        _score_alias_match(connection, query, scored, intent, relation_counts)
        _score_metadata_matches(connection, search_terms, scored, intent, relation_counts)
        _score_chunk_matches(connection, tokens, search_terms, scored, intent, relation_counts)
    return _rank_results(scored.values(), intent, limit)


def _score_direct_identifier_match(
    connection: sqlite3.Connection,
    query: str,
    scored: dict[str, QueryResult],
    intent: QueryIntent,
    relation_counts: dict[str, int],
) -> None:
    """Add strong hits for exact citation-shaped identifiers."""

    for identifier in _direct_identifiers(query):
        citation = identifier.replace("_CCR_", " CCR ")
        row = connection.execute(
            """
            SELECT e.*, c.text AS chunk_text
            FROM entities e
            LEFT JOIN chunks c ON c.geode_id = e.geode_id AND c.chunk_index = 0
            WHERE e.geode_id = ? OR e.citation = ?
            LIMIT 1
            """,
            (identifier, citation),
        ).fetchone()
        if row is None:
            continue
        relation_count = relation_counts.get(row["geode_id"], 0)
        result = _result_from_row(
            row,
            360 + _intent_boost(row, intent) + _relationship_boost(relation_count, intent),
            query,
            _reason_list(row, intent, relation_count, "Matched an exact citation or Geode ID."),
            relation_count,
        )
        scored[result.id] = result


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
        domain_score = _domain_boost(row, "", intent)
        if not _passes_anchor_filter(haystack, intent) and domain_score < 300:
            continue
        term_score = sum(24 for token in search_terms if _contains_term(haystack, token))
        if term_score <= 0 and domain_score < 300:
            continue
        score = term_score
        score += _operational_boost(row, "", intent)
        score += domain_score
        score -= _noise_penalty(row, "", intent)
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

    first_token = _chunk_lookup_term(tokens, intent)
    rows = connection.execute(
        """
        SELECT e.*, c.text AS chunk_text, c.normalized_text AS normalized_text
        FROM chunks c
        JOIN entities e ON e.geode_id = c.geode_id
        WHERE (' ' || c.normalized_text || ' ') LIKE ?
        ORDER BY e.geode_id, c.chunk_index
        LIMIT 2000
        """,
        (f"% {first_token} %",),
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
        score += _domain_boost(row, normalized, intent)
        score -= _noise_penalty(row, normalized, intent)
        if score <= 0:
            continue
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


def _chunk_lookup_term(tokens: list[str], intent: QueryIntent) -> str:
    """Return the strongest available term for the first chunk scan."""

    for term in ["communication", "hazard", "guarding", "machine", "silica", "osha"]:
        if term in intent.topic_terms:
            return term
    for token in tokens:
        if token in intent.anchor_terms:
            return token
    for token in tokens:
        if token in intent.topic_terms:
            return token
    for term in sorted(intent.anchor_terms):
        return term
    for term in sorted(intent.topic_terms):
        return term
    return tokens[0]


def _merge_result(scored: dict[str, QueryResult], result: QueryResult) -> None:
    """Keep the highest-scoring result for an entity."""

    existing = scored.get(result.id)
    if existing is None or result.score > existing.score:
        scored[result.id] = result


def _rank_results(
    results: Iterable[QueryResult],
    intent: QueryIntent,
    limit: int,
) -> list[QueryResult]:
    """Return ranked results, with domain breadth for broad operating questions."""

    ranked = sorted(results, key=lambda item: item.score, reverse=True)
    if limit <= 0 or len(ranked) <= limit:
        return ranked[:limit]

    required_domains = _required_result_domains(intent)
    if len(required_domains) < 2:
        return ranked[:limit]

    selected: list[QueryResult] = []
    selected_ids: set[str] = set()

    for domain in required_domains:
        domain_result = next(
            (
                result
                for result in ranked
                if result.id not in selected_ids and domain in _result_domains(result)
            ),
            None,
        )
        if domain_result is not None:
            selected.append(domain_result)
            selected_ids.add(domain_result.id)

    for result in ranked:
        if len(selected) >= limit:
            break
        if result.id not in selected_ids:
            selected.append(result)
            selected_ids.add(result.id)

    return selected[:limit]


def _required_result_domains(intent: QueryIntent) -> list[str]:
    """Return the domain order expected for a broad multi-domain answer."""

    order = (
        ["safety", "air", "water", "waste", "labor", "rulemaking"]
        if _has_specific_safety_intent(intent)
        else ["air", "water", "waste", "labor", "safety", "rulemaking"]
    )
    domain_terms = set(intent.domain_terms)
    if "industrial" in domain_terms and _needs_operating_domain_breadth(intent):
        domain_terms.update({"air", "water", "waste"})
    required = [domain for domain in order if domain in domain_terms]
    return required


def _needs_operating_domain_breadth(intent: QueryIntent) -> bool:
    """Return true when an industrial question needs environmental operating coverage."""

    if not _has_specific_safety_intent(intent):
        return True
    return bool(
        intent.topic_terms.intersection(
            {
                "permit",
                "permitting",
                "approval",
                "authorization",
                "authorized",
                "runtime",
                "throughput",
                "operating",
                "environmental",
                "emission",
                "emissions",
                "wastewater",
                "discharge",
                "waste",
            }
        )
    )


def _result_domains(result: QueryResult) -> set[str]:
    """Return high-level legal domains represented by a result."""

    value = _normalize(f"{result.id} {result.citation} {result.title} {result.layer} {result.entityType}")
    domains: set[str] = set()
    if any(term in value for term in ["5 ccr 1001", "crs 25 7"]):
        domains.add("air")
    if any(term in value for term in ["5 ccr 1002", "crs 25 8"]):
        domains.add("water")
    if any(term in value for term in ["6 ccr 1007", "crs 25 15", "crs 30 20"]):
        domains.add("waste")
    if any(term in value for term in ["7 ccr 1103", "7 ccr 1107", "crs 8"]):
        domains.add("labor")
    if any(term in value for term in ["federal standard", "29 cfr", "29 u s c", "8 ccr 1507"]):
        domains.add("safety")
    if "rulemaking" in value or "04 rulemaking" in value:
        domains.add("rulemaking")
    return domains


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


def _direct_identifiers(query: str) -> list[str]:
    """Return exact Geode identifiers implied by a user query."""

    identifiers: list[str] = []
    for match in re.finditer(
        r"\b(?P<dept>\d{1,2})\s+CCR\s+(?P<series>\d+)-(?P<rule>\d+(?:-\d+)*)\b",
        query,
        re.IGNORECASE,
    ):
        identifiers.append(f"{match.group('dept')}_CCR_{match.group('series')}-{match.group('rule')}")
    for match in re.finditer(
        r"\b(?P<dept>\d{1,2})_CCR_(?P<series>\d+)-(?P<rule>\d+(?:-\d+)*)\b",
        query,
        re.IGNORECASE,
    ):
        identifiers.append(f"{match.group('dept')}_CCR_{match.group('series')}-{match.group('rule')}")
    for match in re.finditer(
        r"\bCRS[-\s]+(?P<title>\d+)[-\s]+(?P<article>\d+(?:\.\d+)?)[-\s]+(?P<section>\d+(?:\.\d+)?)\b",
        query,
        re.IGNORECASE,
    ):
        identifiers.append(
            f"CRS-{match.group('title')}-{match.group('article')}-{match.group('section')}"
        )
    return list(dict.fromkeys(identifiers))


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
    if (
        "osha" in normalized
        or "cfr" in normalized
        or "federal" in normalized
        or "hazard communication" in normalized
        or "hazardous communication" in normalized
        or "safety data sheet" in normalized
        or "safety data sheets" in normalized
        or _contains_term(normalized, "sds")
        or "machine guarding" in normalized
        or "lockout tagout" in normalized
        or "lockout" in normalized
        or "tagout" in normalized
        or "personal protective equipment" in normalized
        or _contains_term(normalized, "ppe")
        or "respirator" in normalized
        or "respirators" in normalized
        or "confined space" in normalized
        or "forklift" in normalized
        or "hot work" in normalized
        or "silica" in normalized
    ):
        entity_types.add("federal_standard")
        layers.add("07_Supplementary")

    topic_terms = _topic_terms(normalized)
    anchor_terms = _anchor_terms(normalized)
    domain_terms = _domain_terms(normalized)
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
    if topic_terms or domain_terms or wants_obligations:
        entity_types.update(["regulation_rule", "regulation_rule_acquisition", "statute_section"])
        layers.update(["01_Statutes_CRS", "02_Regulations_CCR"])

    return QueryIntent(
        anchor_terms=frozenset(anchor_terms),
        preferred_entity_types=frozenset(entity_types),
        preferred_layers=frozenset(layers),
        topic_terms=frozenset(topic_terms),
        domain_terms=frozenset(domain_terms),
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


def _domain_boost(row: sqlite3.Row, normalized_text: str, intent: QueryIntent) -> int:
    """Return a boost when a record belongs to the right legal subject family."""

    if not intent.domain_terms:
        return 0

    citation = _normalize(row["citation"] or row["geode_id"])
    geode_id = row["geode_id"]
    haystack = normalized_text or _normalize(
        " ".join(
            value or ""
            for value in [row["geode_id"], row["title"], row["citation"], row["entity_type"]]
        )
    )
    boost = 0

    if "labor" in intent.domain_terms:
        if _id_starts(geode_id, ["7_CCR_1103", "7_CCR_1107"]):
            boost += 320
        if _id_starts(geode_id, ["7_CCR_1103-1"]) and intent.topic_terms.intersection(
            {"wage", "overtime", "break", "meal", "rest", "period"}
        ):
            boost += 130
        if _id_starts(geode_id, ["7_CCR_1103-1"]) and intent.topic_terms.intersection(
            {"minimum", "nonexempt", "exempt", "overtime"}
        ):
            boost += 260
        if _id_starts(geode_id, ["7_CCR_1103"]) and intent.topic_terms.intersection(
            {"hourly", "payroll", "timekeeping", "wage", "wages"}
        ):
            boost += 300
        if _id_starts(geode_id, ["7_CCR_1103-7"]) and intent.topic_terms.intersection(
            {"record", "records", "recordkeeping", "retention", "personnel", "payroll", "wage"}
        ):
            boost += 75
        if _id_starts(geode_id, ["7_CCR_1103-11"]) and intent.topic_terms.intersection(
            {"discrimination", "retaliation"}
        ):
            boost += 100
        if _id_starts(geode_id, ["7_CCR_1103-1"]) and intent.topic_terms.intersection(
            {"tipped", "tip", "tips", "exempt", "nonexempt", "classification"}
        ):
            boost += 110
        if _citation_starts(citation, ["crs 8 4", "crs 8 5", "crs 8 6", "crs 8 13"]):
            boost += 150
        if _citation_starts(citation, ["crs 8 4"]) and intent.topic_terms.intersection(
            {"final", "paycheck", "paychecks", "deduction", "deductions"}
        ):
            boost += 260
        if _citation_starts(citation, ["crs 8 4 103", "crs 8 4 113"]) and intent.topic_terms.intersection(
            {"payment", "theft", "wage", "wages"}
        ):
            boost += 240
        if _citation_starts(citation, ["crs 8 5"]) and intent.topic_terms.intersection(
            {"equal", "transparency"}
        ):
            boost += 260
        if _citation_starts(citation, ["crs 8 4 109"]) and intent.topic_terms.intersection(
            {"final", "paycheck", "paychecks"}
        ):
            boost += 320
        if _citation_starts(citation, ["crs 8 70"]) and intent.topic_terms.intersection(
            {"independent", "contractor", "classification", "employee"}
        ):
            boost += 180
        if _citation_starts(citation, ["crs 8 2"]) and intent.topic_terms.intersection(
            {"record", "records", "recordkeeping", "retention", "personnel"}
        ):
            boost += 220
        if _citation_starts(citation, ["crs 8 43"]) and intent.topic_terms.intersection(
            {"injury", "injuries", "report", "reporting", "notice"}
        ):
            boost += 240
        if _id_starts(geode_id, ["7_CCR_1107"]) and intent.topic_terms.intersection(
            {"compensation", "workers", "injury", "injuries"}
        ):
            boost += 320
        if _citation_starts(citation, ["crs 8 40", "crs 8 41", "crs 8 42", "crs 8 43"]) and intent.topic_terms.intersection(
            {"compensation", "workers"}
        ):
            boost += 260
        if _citation_starts(citation, ["crs 8 70", "crs 8 71", "crs 8 72", "crs 8 73"]):
            boost += 120
        if _citation_starts(citation, ["crs 24 34"]):
            boost += 130

    if "air" in intent.domain_terms:
        if _id_starts(geode_id, ["5_CCR_1001"]):
            boost += 180
        if _id_starts(geode_id, ["5_CCR_1001-5"]):
            boost += 180
        if _id_starts(geode_id, ["5_CCR_1001-5", "5_CCR_1001-9"]) and intent.topic_terms.intersection(
            {"permit", "permitting", "runtime", "throughput", "operating"}
        ):
            boost += 900
        if _citation_starts(citation, ["crs 25 7"]):
            boost += 150

    if "water" in intent.domain_terms:
        if _id_starts(geode_id, ["5_CCR_1002"]):
            boost += 180
        if _id_starts(geode_id, ["5_CCR_1002-61", "5_CCR_1002-63"]):
            boost += 110
        if _citation_starts(citation, ["crs 25 8", "crs 25 9", "crs 25 10"]):
            boost += 150

    if "waste" in intent.domain_terms:
        if _id_starts(geode_id, ["6_CCR_1007"]):
            boost += 190
        if _id_starts(geode_id, ["6_CCR_1007"]) and intent.topic_terms.intersection(
            {"universal", "generator", "generators", "hazardous", "waste"}
        ):
            boost += 240
        if _citation_starts(citation, ["crs 25 15", "crs 30 20"]):
            boost += 150

    if "safety" in intent.domain_terms:
        if row["entity_type"] == "federal_standard":
            boost += 340
        if "osha" in haystack:
            boost += 140
        if _citation_starts(citation, ["29 cfr 1910", "29 usc 654"]):
            boost += 160
        if _citation_starts(citation, ["29 cfr 1910 1200"]) and intent.topic_terms.intersection(
            {"hazard", "communication", "chemical", "chemicals"}
        ):
            boost += 240
        if _citation_starts(citation, ["29 cfr 1910 147"]) and intent.topic_terms.intersection(
            {"lockout", "tagout", "loto", "energy", "energized"}
        ):
            boost += 280
        if _citation_starts(citation, ["29 cfr 1910 132"]) and intent.topic_terms.intersection(
            {"ppe", "personal", "protective", "equipment"}
        ):
            boost += 280
        if _citation_starts(citation, ["29 cfr 1910 134"]) and intent.topic_terms.intersection(
            {"respirator", "respirators", "respiratory"}
        ):
            boost += 280
        if _citation_starts(citation, ["29 cfr 1910 146"]) and intent.topic_terms.intersection(
            {"confined", "space", "spaces"}
        ):
            boost += 280
        if _citation_starts(citation, ["29 cfr 1910 178"]) and intent.topic_terms.intersection(
            {"forklift", "forklifts", "powered", "truck", "trucks"}
        ):
            boost += 280
        if _citation_starts(citation, ["29 cfr 1910 252"]) and intent.topic_terms.intersection(
            {"hot", "work", "welding", "cutting", "brazing"}
        ):
            boost += 280
        if _citation_starts(citation, ["29 cfr part 1904", "29 cfr 1904"]) and intent.topic_terms.intersection(
            {"injury", "injuries", "illness", "illnesses", "log", "logs", "reporting", "recording"}
        ):
            boost += 280
        if _citation_starts(citation, ["29 cfr part 1904", "29 cfr 1904"]) and intent.topic_terms.intersection(
            {"workplace", "injury", "injuries", "report", "reporting"}
        ):
            boost += 240
        if _citation_starts(citation, ["29 cfr 1910 212"]) and intent.topic_terms.intersection(
            {"machine", "guard", "guarding", "point", "operation"}
        ):
            boost += 240
        if _citation_starts(citation, ["29 cfr 1910 1053"]) and intent.topic_terms.intersection(
            {"silica", "exposure", "respirable", "crystalline"}
        ):
            boost += 240
        if _citation_starts(citation, ["29 u s c 654", "29 usc 654"]) and intent.topic_terms.intersection(
            {"osha", "employer", "employers", "compliance", "duty", "duties"}
        ):
            boost += 520
        if _id_starts(geode_id, ["8_CCR_1507"]):
            boost += 320
        if _citation_starts(citation, ["crs 8 14", "crs 8 40", "crs 8 41", "crs 8 42", "crs 8 43"]):
            boost += 120
        emergency_query = bool(intent.topic_terms.intersection({"emergency", "response", "planning"}))
        if emergency_query and _citation_starts(citation, ["crs 24 33 5"]):
            boost += 260
        if emergency_query and _citation_starts(
            citation,
            [
                "crs 24 33 5 702",
                "crs 24 33 5 704",
                "crs 24 33 5 705",
                "crs 24 33 5 707",
                "crs 24 33 5 1203",
                "crs 24 33 5 1614",
            ],
        ):
            boost += 180
        if any(_contains_term(haystack, term) for term in ["safety", "injury", "exposure"]):
            boost += 80
        if intent.topic_terms.intersection({"boiler", "pressure", "vessel", "vessels"}):
            if _id_starts(geode_id, ["7_CCR_1101-5", "7_CCR_1101-16"]):
                boost += 430
            if _citation_starts(citation, ["crs 9 4"]):
                boost += 260

    if "industrial" in intent.domain_terms:
        if _id_starts(geode_id, ["5_CCR_1001", "5_CCR_1002", "6_CCR_1007"]):
            boost += 420
        if intent.topic_terms.intersection(
            {"approval", "authorization", "authorized", "permit", "permitting"}
        ):
            if _id_starts(geode_id, ["5_CCR_1001", "5_CCR_1002", "6_CCR_1007"]):
                boost += 210
            if _contains_term(haystack, "permit") or _contains_term(haystack, "approval"):
                boost += 90
        if _id_starts(geode_id, ["5_CCR_1001-5", "5_CCR_1001-9"]) and intent.topic_terms.intersection(
            {"permit", "permitting", "runtime", "throughput", "operating"}
        ):
            boost += 760
        if _id_starts(geode_id, ["5_CCR_1001"]) and intent.topic_terms.intersection(
            {"air", "dust", "emission", "emissions", "particulate"}
        ):
            boost += 160
        if _citation_starts(citation, ["crs 25 7", "crs 25 8", "crs 25 15", "crs 8"]):
            boost += 70

    return boost


def _noise_penalty(row: sqlite3.Row, normalized_text: str, intent: QueryIntent) -> int:
    """Return a penalty for specialized industries that are not in the user's question."""

    if not intent.domain_terms:
        return 0
    haystack = normalized_text or _normalize(
        " ".join(value or "" for value in [row["geode_id"], row["title"], row["citation"]])
    )
    penalty = 0
    if "industrial" in intent.domain_terms or "air" in intent.domain_terms:
        unrelated_terms = [
            "marijuana",
            "cannabis",
            "gaming",
            "casino",
            "combative sports",
            "liquor",
            "tobacco",
            "natural medicine",
            "driver",
            "vehicle",
            "motor vehicle",
            "child care",
            "childcare",
            "pet animal",
            "sports betting",
            "public utilities commission",
        ]
        if any(term in haystack for term in unrelated_terms):
            penalty += 180
    if "waste" in intent.domain_terms and "methamphetamine" in haystack:
        penalty += 220
    if "waste" in intent.domain_terms and row["entity_type"] == "federal_standard":
        if not intent.topic_terms.intersection({"hazard", "communication", "sds"}):
            penalty += 260
    if (
        "industrial" in intent.domain_terms
        and row["entity_type"] == "federal_standard"
        and "safety" not in intent.domain_terms
    ):
        penalty += 900
    if "safety" in intent.domain_terms and row["entity_type"] == "federal_standard":
        citation = _normalize(row["citation"] or row["geode_id"])
        if not _has_specific_safety_intent(intent) and not _citation_starts(
            citation,
            ["29 u s c 654", "29 usc 654"],
        ):
            penalty += 220
    if "labor" in intent.domain_terms and any(
        term in haystack for term in ["child care facility", "medical assistance", "food assistance"]
    ):
        penalty += 150
    if (
        "labor" in intent.domain_terms
        and _citation_starts(_normalize(row["citation"] or row["geode_id"]), ["crs 8 70"])
        and not intent.topic_terms.intersection({"independent", "contractor"})
    ):
        penalty += 240
    if "industrial" in intent.domain_terms and _id_starts(
        row["geode_id"],
        [
            "10_CCR",
            "3_CCR_702",
            "3_CCR_703",
            "2_CCR_404",
            "2_CCR_406",
            "2_CCR_407",
            "2_CCR_502",
            "4_CCR_723",
            "4_CCR_732",
            "4_CCR_740",
            "1_CCR_203",
            "1_CCR_207",
            "1_CCR_212",
            "1_CCR_213",
            "1_CCR_301",
        ],
    ):
        penalty += 260
    if (
        ("industrial" in intent.domain_terms or "air" in intent.domain_terms)
        and row["geode_id"] == "5_CCR_1001-1"
        and intent.topic_terms.intersection({"permit", "permitting", "production", "operating"})
        and not intent.domain_terms.intersection({"rulemaking"})
    ):
        penalty += 520
    if "industrial" in intent.domain_terms and row["geode_id"].startswith("CRS-42"):
        penalty += 800
    if "waste" in intent.domain_terms and row["geode_id"].startswith("CRS-8-43"):
        penalty += 800
    if (
        (
            row["geode_id"].startswith("CRS-8-40")
            or row["geode_id"].startswith("CRS-8-41")
            or row["geode_id"].startswith("CRS-8-42")
            or row["geode_id"].startswith("CRS-8-43")
        )
        and not intent.topic_terms.intersection({"workers", "compensation", "injury", "injuries"})
    ):
        penalty += 700
    return penalty


def _id_starts(value: str, prefixes: list[str]) -> bool:
    """Return true when a Geode ID starts with one of the supplied prefixes."""

    return any(value.startswith(prefix) for prefix in prefixes)


def _citation_starts(value: str, prefixes: list[str]) -> bool:
    """Return true when a normalized citation starts with one of the supplied prefixes."""

    return any(value.startswith(prefix) for prefix in prefixes)


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
    if intent.domain_terms:
        reasons.append("Matched the relevant legal subject area.")
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
        ("air", "emission", "emissions", "environmental", "pollution", "dust", "powder", "powders"): {
            "air",
            "dust",
            "emission",
            "emissions",
            "environmental",
            "particulate",
            "pollutant",
            "pollution",
            "stationary",
        },
        ("kiln", "kilns", "furnace", "furnaces", "particulate", "silica"): {
            "air",
            "emission",
            "emissions",
            "particulate",
            "pollutant",
            "silica",
        },
        (
            "permit",
            "permitting",
            "license",
            "approval",
            "approved",
            "authorization",
            "authorized",
            "permission",
            "green light",
            "sign off",
            "go ahead",
        ): {
            "permit",
            "permitting",
            "license",
            "approval",
            "authorization",
            "authorized",
            "operate",
            "operating",
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
            "retention",
            "personnel",
        },
        ("inspect", "inspection", "inspections"): {
            "inspect",
            "inspection",
            "inspections",
        },
        (
            "manufacturing",
            "manufacturer",
            "facility",
            "production",
            "runtime",
            "operating hours",
            "throughput",
            "increasing production",
        ): {
            "manufacturing",
            "manufacturer",
            "facility",
            "industrial",
            "production",
            "runtime",
            "throughput",
            "operating",
        },
        ("ceramics", "ceramic", "kiln", "kilns", "plant", "factory"): {
            "manufacturing",
            "manufacturer",
            "facility",
            "industrial",
            "production",
        },
        ("waste", "hazardous", "solid waste", "environmental", "spill", "spills", "release", "releases"): {
            "waste",
            "hazardous",
            "environmental",
            "spill",
            "spills",
            "release",
            "releases",
            "solid",
            "disposal",
        },
        ("wastewater", "discharge", "stormwater", "runoff", "pretreatment", "spill", "spills"): {
            "water",
            "wastewater",
            "discharge",
            "stormwater",
            "pretreatment",
            "spill",
            "spills",
        },
        ("wage", "overtime", "payroll"): {
            "employee",
            "employer",
            "wage",
            "wages",
            "overtime",
            "payroll",
            "labor",
        },
        ("minimum wage",): {
            "employee",
            "employer",
            "minimum",
            "wage",
            "wages",
            "labor",
        },
        ("wage payment", "wage theft"): {
            "employee",
            "employer",
            "payment",
            "theft",
            "wage",
            "wages",
            "labor",
        },
        ("hourly", "hourly employees", "wage and hour", "timekeeping"): {
            "employee",
            "employees",
            "hourly",
            "overtime",
            "payroll",
            "timekeeping",
            "wage",
            "wages",
            "labor",
        },
        ("final paycheck", "final paychecks", "final wages", "termination pay"): {
            "final",
            "paycheck",
            "paychecks",
            "wage",
            "wages",
            "termination",
            "labor",
        },
        ("equal pay",): {
            "equal",
            "pay",
            "wage",
            "wages",
            "transparency",
            "labor",
        },
        ("independent contractor", "employee classification", "classification"): {
            "independent",
            "contractor",
            "classification",
            "employee",
            "labor",
        },
        ("tipped employee", "tipped", "tips", "tip credit", "tip offset"): {
            "tipped",
            "tip",
            "tips",
            "wage",
            "labor",
        },
        ("exempt", "nonexempt"): {
            "exempt",
            "nonexempt",
            "classification",
            "overtime",
            "labor",
        },
        ("workers compensation", "worker compensation"): {
            "workers",
            "compensation",
            "injury",
            "injuries",
            "labor",
        },
        ("break", "meal", "rest"): {
            "break",
            "meal",
            "rest",
            "period",
        },
        (
            "employee",
            "employees",
            "employer",
            "employers",
            "employment",
            "personnel",
            "shift",
            "scheduling",
            "staffing",
            "staff",
            "termination",
            "terminating",
            "hiring",
        ): {
            "employee",
            "employer",
            "employers",
            "employment",
            "personnel",
            "shift",
            "schedule",
            "scheduling",
            "termination",
            "hiring",
            "labor",
        },
        ("sick", "leave", "family", "medical", "famli"): {
            "sick",
            "leave",
            "family",
            "medical",
            "famli",
        },
        ("discrimination", "retaliation", "harassment", "minor", "child labor"): {
            "discrimination",
            "retaliation",
            "minor",
            "labor",
            "employee",
        },
        (
            "safety",
            "training",
        ): {
            "safety",
            "training",
        },
        ("injury", "injuries", "complaint", "complaints"): {
            "injury",
            "injuries",
            "complaint",
            "complaints",
            "safety",
        },
        ("exposure", "employee exposure", "workplace exposure"): {
            "exposure",
            "workplace",
            "safety",
        },
        ("heat", "hotter", "heat stress", "heat illness"): {
            "heat",
            "training",
            "safety",
        },
        ("osha",): {
            "osha",
            "safety",
        },
        ("injury log", "injury logs", "workplace injury", "someone got hurt"): {
            "injury",
            "injuries",
            "log",
            "logs",
            "recording",
            "reporting",
            "osha",
            "safety",
        },
        ("chemical", "chemicals"): {
            "chemical",
            "chemicals",
            "safety",
            "hazardous",
        },
        ("hazard communication", "hazardous communication", "safety data sheet", "safety data sheets", "sds"): {
            "hazard",
            "communication",
            "chemical",
            "chemicals",
            "sds",
            "safety",
        },
        ("machine guarding", "guarding", "guard", "machine"): {
            "machine",
            "guard",
            "guarding",
            "safety",
        },
        ("lockout tagout", "lockout", "tagout", "energized machinery"): {
            "lockout",
            "tagout",
            "loto",
            "energy",
            "energized",
            "machine",
            "safety",
        },
        ("personal protective equipment", "protective equipment", "ppe"): {
            "ppe",
            "personal",
            "protective",
            "equipment",
            "safety",
        },
        ("respirator", "respirators", "respiratory protection"): {
            "respirator",
            "respirators",
            "respiratory",
            "protection",
            "safety",
        },
        ("confined space", "confined spaces"): {
            "confined",
            "space",
            "spaces",
            "safety",
        },
        ("forklift", "forklifts"): {
            "forklift",
            "forklifts",
            "powered",
            "truck",
            "trucks",
            "safety",
        },
        ("hot work",): {
            "hot",
            "work",
            "welding",
            "cutting",
            "brazing",
            "safety",
        },
        ("boiler", "boilers", "pressure vessel", "pressure vessels"): {
            "boiler",
            "boilers",
            "pressure",
            "vessel",
            "vessels",
            "safety",
        },
        ("silica",): {
            "silica",
            "respirable",
            "crystalline",
            "exposure",
            "safety",
        },
        ("emergency", "response", "planning"): {
            "emergency",
            "response",
            "planning",
            "hazardous",
            "safety",
        },
    }
    terms: set[str] = set()
    for triggers, expanded in groups.items():
        if any(_trigger_matches(normalized, trigger) for trigger in triggers):
            terms.update(expanded)
    return terms


def _anchor_terms(normalized: str) -> set[str]:
    """Return stronger topic anchors that broad words must connect to."""

    specific_safety_anchors = _specific_safety_anchor_terms(normalized)
    if specific_safety_anchors:
        return specific_safety_anchors

    anchors: set[str] = set()
    anchor_groups = {
        ("air", "emission", "emissions", "environmental", "pollution"): {
            "air",
            "emission",
            "emissions",
            "environmental",
            "pollutant",
            "pollution",
            "stationary",
        },
        ("kiln", "kilns", "furnace", "furnaces", "particulate"): {
            "air",
            "emission",
            "emissions",
            "particulate",
            "pollutant",
        },
        ("manufacturing", "manufacturer", "facility", "production"): {
            "manufacturing",
            "manufacturer",
            "industrial",
            "production",
        },
        ("runtime", "operating hours", "throughput", "increasing production"): {
            "manufacturing",
            "manufacturer",
            "industrial",
            "production",
            "runtime",
            "throughput",
            "operating",
        },
        ("ceramics", "ceramic", "kiln", "kilns", "plant", "factory"): {
            "manufacturing",
            "manufacturer",
            "industrial",
            "production",
        },
        ("waste", "hazardous", "solid waste", "environmental"): {
            "waste",
            "hazardous",
            "environmental",
            "solid",
            "disposal",
        },
        ("universal waste", "waste generator", "hazardous waste generator"): {
            "universal",
            "waste",
            "generator",
            "generators",
            "hazardous",
        },
        ("wastewater", "discharge", "stormwater", "runoff", "pretreatment"): {
            "water",
            "wastewater",
            "discharge",
            "stormwater",
            "pretreatment",
        },
        (
            "permit",
            "permitting",
            "approval",
            "approved",
            "authorization",
            "authorized",
            "permission",
            "green light",
            "sign off",
            "go ahead",
        ): {
            "permit",
            "permitting",
            "approval",
            "authorization",
            "authorized",
            "operate",
            "operating",
            "facility",
            "division",
        },
        ("wage", "overtime", "payroll"): {
            "wage",
            "overtime",
            "minimum wage",
            "payroll",
            "labor",
        },
        ("break", "meal", "rest"): {
            "break",
            "meal",
            "rest",
            "period",
        },
        ("discrimination", "retaliation", "harassment"): {
            "discrimination",
            "retaliation",
            "harassment",
        },
    }
    for triggers, expanded in anchor_groups.items():
        if any(_trigger_matches(normalized, trigger) for trigger in triggers):
            anchors.update(expanded)
    return anchors


def _specific_safety_anchor_terms(normalized: str) -> set[str]:
    """Return OSHA topic anchors that should outrank broad facility wording."""

    if (
        "hazard communication" in normalized
        or "hazardous communication" in normalized
        or "safety data sheet" in normalized
        or "safety data sheets" in normalized
        or _contains_term(normalized, "sds")
    ):
        return {"hazard", "communication", "chemical", "chemicals", "sds"}
    if "machine guarding" in normalized:
        return {"machine", "guard", "guarding"}
    if "lockout" in normalized or "tagout" in normalized or "energized machinery" in normalized:
        return {"lockout", "tagout", "loto", "energy", "energized"}
    if "personal protective equipment" in normalized or _contains_term(normalized, "ppe"):
        return {"ppe", "personal", "protective", "equipment"}
    if "respirator" in normalized or "respiratory" in normalized:
        return {"respirator", "respirators", "respiratory", "protection"}
    if "confined space" in normalized or "confined spaces" in normalized:
        return {"confined", "space", "spaces"}
    if "forklift" in normalized or "forklifts" in normalized:
        return {"forklift", "forklifts", "powered", "truck", "trucks"}
    if "hot work" in normalized:
        return {"hot", "work", "welding", "cutting", "brazing"}
    if "injury log" in normalized or "injury logs" in normalized:
        return {"injury", "injuries", "log", "logs", "recording", "reporting"}
    if "silica" in normalized:
        return {"silica", "exposure", "respirable", "crystalline"}
    return set()


def _domain_terms(normalized: str) -> set[str]:
    """Return high-level legal subject areas implied by the user's wording."""

    domains: set[str] = set()
    domain_groups = {
        "labor": [
            "employee",
            "employees",
            "employer",
            "employment",
            "labor",
            "wage",
            "overtime",
            "hourly",
            "payroll",
            "timekeeping",
            "personnel",
            "recordkeeping",
            "break",
            "meal",
            "rest",
            "leave",
            "sick",
            "family medical",
            "famli",
            "unemployment",
            "workers compensation",
            "worker compensation",
            "discrimination",
            "retaliation",
            "minor employee",
            "child labor",
            "shift",
            "scheduling",
            "staffing",
            "staff",
            "termination",
            "terminating",
            "hiring",
            "final paycheck",
            "final paychecks",
            "final wages",
            "paycheck",
            "paychecks",
            "equal pay",
            "pay transparency",
            "independent contractor",
            "employee classification",
        ],
        "air": [
            "air",
            "dust",
            "powder",
            "powders",
            "emission",
            "emissions",
            "environmental",
            "pollution",
            "particulate",
            "kiln",
            "kilns",
            "furnace",
            "furnaces",
            "stationary source",
            "silica",
        ],
        "water": [
            "water",
            "environmental",
            "wastewater",
            "discharge",
            "stormwater",
            "runoff",
            "pretreatment",
            "spill",
            "spills",
        ],
        "waste": [
            "waste",
            "hazardous",
            "universal waste",
            "environmental",
            "generator",
            "storage",
            "chemical",
            "chemicals",
            "materials",
            "inventory",
            "spill",
            "spills",
            "release",
            "releases",
        ],
        "safety": [
            "safety",
            "osha",
            "injury",
            "injuries",
            "exposure",
            "training",
            "contractor",
            "contractors",
            "contractor work",
            "exposure risk",
            "exposure",
            "inspection",
            "inspections",
            "incident",
            "incidents",
            "heat",
            "hotter",
            "complaint",
            "complaints",
            "heat hazard",
            "heat hazards",
            "machine guarding",
            "guarding",
            "contractor safety",
            "emergency response",
            "hazard communication",
            "hazardous communication",
            "lockout",
            "tagout",
            "personal protective equipment",
            "ppe",
            "respirator",
            "respirators",
            "respiratory protection",
            "confined space",
            "confined spaces",
            "forklift",
            "forklifts",
            "hot work",
            "injury log",
            "injury logs",
            "workplace injury",
            "boiler",
            "boilers",
            "pressure vessel",
            "pressure vessels",
            "silica",
        ],
        "industrial": [
            "manufacturing",
            "manufacturer",
            "industrial",
            "production",
            "facility",
            "plant",
            "factory",
            "ceramics",
            "ceramic",
            "equipment",
            "construction",
            "capacity",
            "capital investment",
            "runtime",
            "operating hours",
            "throughput",
            "increasing production",
        ],
    }
    for domain, triggers in domain_groups.items():
        if any(_trigger_matches(normalized, trigger) for trigger in triggers):
            domains.add(domain)
    if _has_approval_intent(normalized):
        domains.update({"air", "water", "waste", "industrial"})
    return domains


def _trigger_matches(normalized: str, trigger: str) -> bool:
    """Return true when a trigger appears as a phrase or full word."""

    normalized_trigger = _normalize(trigger)
    if " " in normalized_trigger:
        return normalized_trigger in normalized
    return _contains_term(normalized, normalized_trigger)


def _has_approval_intent(normalized: str) -> bool:
    """Return true when the query asks about approval or authorization."""

    approval_triggers = [
        "approval",
        "approved",
        "authorization",
        "authorized",
        "permission",
        "green light",
        "sign off",
        "go ahead",
    ]
    return any(_trigger_matches(normalized, trigger) for trigger in approval_triggers)


def _has_specific_safety_intent(intent: QueryIntent) -> bool:
    """Return true when the user named a specific OSHA-style safety topic."""

    return bool(
        intent.topic_terms.intersection(
            {
                "hazard",
                "communication",
                "sds",
                "machine",
                "guard",
                "guarding",
                "lockout",
                "tagout",
                "loto",
                "ppe",
                "personal",
                "protective",
                "respirator",
                "respiratory",
                "confined",
                "forklift",
                "hot",
                "welding",
                "cutting",
                "brazing",
                "silica",
                "injury",
                "injuries",
                "log",
                "logs",
            }
        )
    )


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

    return " ".join(re.sub(r"[^0-9a-z]+", " ", value.casefold()).split())


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
