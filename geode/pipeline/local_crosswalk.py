"""Build validated local-to-state authority relationships."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any

from geode.schemas import CrosswalkEntry
from geode.utils.file_io import atomic_write_jsonl, iter_jsonl


def build_local_crosswalks(root: Path) -> dict[str, int]:
    """Create forward and reverse crosswalks from local rule records."""

    resolved_root = root.resolve()
    rows: list[CrosswalkEntry] = []
    seen_records: set[str] = set()
    for layer in ("08_County_Authorities", "09_District_Authorities"):
        index_path = resolved_root / layer / "_index.jsonl"
        if not index_path.exists():
            continue
        metadata_paths = {
            resolved_root / str(index_row.get("meta_path") or index_row.get("path") or "")
            for index_row in iter_jsonl(index_path)
        }
        for path in metadata_paths:
            if not path.exists() or path.name == "_index.jsonl":
                continue
            for record in iter_jsonl(path):
                local_id = str(record.get("id") or "")
                if record.get("entity_type") != "local_rule" or local_id in seen_records:
                    continue
                seen_records.add(local_id)
                for state_id in record.get("state_authority_ids", []):
                    rows.append(
                        _entry(
                            local_id,
                            "local_rule",
                            str(state_id),
                            "statute_section",
                            "cites",
                            _provenance(record, str(state_id)),
                        )
                    )
    forward = resolved_root / "_CROSSWALKS" / "local_rule_to_state_authority.jsonl"
    reverse = resolved_root / "_CROSSWALKS" / "state_authority_to_local_rule.jsonl"
    atomic_write_jsonl(forward, rows, resolved_root)
    atomic_write_jsonl(
        reverse,
        [
            _entry(
                row.target_id or "",
                row.target_type,
                row.source_id,
                row.source_type,
                "cited_by",
                row.source_evidence,
            )
            for row in rows
        ],
        resolved_root,
    )
    return {"forward": len(rows), "reverse": len(rows)}


def _entry(
    source_id: str,
    source_type: str,
    target_id: str,
    target_type: str,
    relationship: str,
    source_evidence: str | None = None,
) -> CrosswalkEntry:
    """Build one validated crosswalk entry."""

    return CrosswalkEntry(
        source_id=source_id,
        source_type=source_type,
        target_id=target_id,
        target_type=target_type,
        relationship=relationship,
        confidence=0.65 if relationship == "cites" else 0.65,
        source_evidence=source_evidence,
        data_retrieved=date.today(),
    )


def _provenance(record: dict[str, Any], state_id: str) -> str:
    """Describe the exact local source location supporting a crosswalk."""

    source_path = str(record.get("source_path") or "")
    citation_pages = record.get("source_citation_pages", {}).get(state_id, [])
    page = ",".join(str(value) for value in citation_pages) or record.get("source_page")
    section = record.get("source_section") or record.get("section_heading")
    location = f"{source_path}#page={page}" if page else source_path
    return f"{location}#section={section}" if section else location


def main() -> int:
    """Build local-to-state crosswalks from the command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(build_local_crosswalks(args.root.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
