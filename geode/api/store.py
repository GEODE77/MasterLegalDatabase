"""Read validated Geode corpus files for API responses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import ensure_not_raw_archive, iter_jsonl, load_json

STATUTES_LAYER = "01_Statutes_CRS"
REGULATIONS_LAYER = "02_Regulations_CCR"
SEARCHABLE_LAYERS = (
    "01_Statutes_CRS",
    "02_Regulations_CCR",
    "03_Legislation",
    "04_Rulemaking",
    "05_Executive_Orders",
    "06_Session_Laws",
    "07_Supplementary",
)


class GeodeRecordNotFoundError(LookupError):
    """Raised when a requested Geode record is not in the layer index."""


class GeodeDataStore:
    """Small read service over Geode's validated output files."""

    def __init__(self, root: Path) -> None:
        """Create a store rooted at a Geode project folder."""

        self.root = root.resolve()

    def manifest(self) -> dict[str, Any]:
        """Return the master manifest."""

        manifest_path = self.root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
        payload = load_json(manifest_path)
        if not isinstance(payload, dict):
            raise ValueError("MASTER_MANIFEST.json must contain an object")
        return payload

    def get_statute(self, statute_id: str) -> dict[str, Any]:
        """Return one statute record and its Markdown section text."""

        row = self.find_index_record(STATUTES_LAYER, statute_id)
        content_path = self._resolve_corpus_path(str(row.get("path") or ""))
        text = content_path.read_text(encoding="utf-8")
        section_text = _extract_markdown_section(text, _statute_heading_key(row, statute_id))
        return {
            "id": row.get("id"),
            "layer": STATUTES_LAYER,
            "metadata": row,
            "content": section_text or text,
            "content_path": content_path.relative_to(self.root).as_posix(),
            "content_kind": "markdown",
        }

    def get_regulation(self, regulation_id: str) -> dict[str, Any]:
        """Return one regulation record and its normalized content."""

        row = self.find_index_record(REGULATIONS_LAYER, regulation_id)
        content_path = self._resolve_corpus_path(str(row.get("path") or ""))
        if content_path.suffix.lower() == ".json":
            content: Any = load_json(content_path)
            content_kind = "json"
        else:
            content = content_path.read_text(encoding="utf-8")
            content_kind = "text"
        return {
            "id": row.get("id"),
            "layer": REGULATIONS_LAYER,
            "metadata": row,
            "content": content,
            "content_path": content_path.relative_to(self.root).as_posix(),
            "content_kind": content_kind,
        }

    def search(
        self,
        query: str,
        layers: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search layer indexes by ID, title, citation, and tags."""

        clean_query = query.strip()
        if not clean_query:
            return {"query": query, "count": 0, "results": []}
        selected_layers = _validated_layers(layers)
        terms = [term.casefold() for term in clean_query.split() if term.strip()]
        scored: list[dict[str, Any]] = []
        for layer in selected_layers:
            index_path = self.root / layer / "_index.jsonl"
            if not index_path.exists():
                continue
            for row in iter_jsonl(index_path):
                score = _search_score(row, terms)
                if score <= 0:
                    continue
                scored.append(
                    {
                        "id": row.get("id"),
                        "layer": layer,
                        "entity_type": row.get("entity_type"),
                        "title": row.get("title"),
                        "citation": row.get("citation"),
                        "path": row.get("path"),
                        "score": score,
                    }
                )
        scored.sort(key=lambda item: (-int(item["score"]), str(item["id"])))
        capped = scored[: max(1, min(limit, 100))]
        return {"query": query, "count": len(capped), "results": capped}

    def find_index_record(self, layer: str, record_id: str) -> dict[str, Any]:
        """Find one record in a layer index by ID or citation."""

        index_path = self.root / layer / "_index.jsonl"
        if not index_path.exists():
            raise GeodeRecordNotFoundError(f"missing layer index: {layer}")
        normalized_id = record_id.casefold()
        for row in iter_jsonl(index_path):
            row_id = str(row.get("id") or "").casefold()
            citation = str(row.get("citation") or "").casefold()
            if normalized_id in {row_id, citation}:
                return row
        raise GeodeRecordNotFoundError(f"record not found: {record_id}")

    def _resolve_corpus_path(self, stored_path: str) -> Path:
        """Resolve a corpus path while blocking raw-archive reads."""

        if not stored_path:
            raise ValueError("record does not include a content path")
        candidate = Path(stored_path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError(f"record path is outside project root: {stored_path}")
        ensure_not_raw_archive(resolved, self.root)
        if not resolved.exists():
            raise FileNotFoundError(resolved)
        return resolved


def _validated_layers(layers: list[str] | None) -> list[str]:
    """Return known searchable layers only."""

    if not layers:
        return list(SEARCHABLE_LAYERS)
    allowed = set(SEARCHABLE_LAYERS)
    selected = []
    for layer in layers:
        if layer not in allowed:
            raise ValueError(f"unknown searchable layer: {layer}")
        selected.append(layer)
    return selected


def _search_score(row: dict[str, Any], terms: list[str]) -> int:
    """Return a simple index-search score."""

    haystack_parts = [
        str(row.get("id") or ""),
        str(row.get("title") or ""),
        str(row.get("citation") or ""),
        " ".join(str(tag) for tag in row.get("tags") or []),
        json.dumps(row.get("summary") or "", ensure_ascii=False),
    ]
    haystack = " ".join(haystack_parts).casefold()
    score = 0
    for term in terms:
        if term in haystack:
            score += 1
    return score


def _statute_heading_key(row: dict[str, Any], statute_id: str) -> str:
    """Return the statute heading number used in CRS Markdown files."""

    citation = str(row.get("citation") or statute_id)
    if citation.startswith("CRS-"):
        return citation.removeprefix("CRS-")
    return citation.replace("CRS ", "").replace("C.R.S.", "").strip()


def _extract_markdown_section(markdown: str, heading_key: str) -> str | None:
    """Extract one fourth-level Markdown section by CRS heading number."""

    lines = markdown.splitlines()
    start_index: int | None = None
    prefix = f"#### {heading_key}."
    alternate_prefix = f"#### {heading_key} "
    for index, line in enumerate(lines):
        if line.startswith(prefix) or line.startswith(alternate_prefix):
            start_index = index
            break
    if start_index is None:
        return None
    end_index = len(lines)
    for index in range(start_index + 1, len(lines)):
        if lines[index].startswith("#### "):
            end_index = index
            break
    return "\n".join(lines[start_index:end_index]).strip() + "\n"
