"""Command-line detail bridge for the Geode read index."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from geode.web.db import CorpusRepository


def detail_index(database_path: Path, geode_id: str) -> dict[str, Any] | None:
    """Return one API-ready entity detail record from the read index."""

    repository = CorpusRepository(database_path)
    entity = repository.resolve_entity(geode_id)
    if entity is None:
        return None

    chunks = repository.list_chunks(entity.geode_id)
    relations = []
    for relation in repository.list_relations(entity.geode_id):
        other_id = (
            relation.target_geode_id
            if relation.source_geode_id == entity.geode_id
            else relation.source_geode_id
        )
        related = repository.resolve_entity(other_id)
        relations.append(
            {
                **asdict(relation),
                "direction": "outbound"
                if relation.source_geode_id == entity.geode_id
                else "inbound",
                "related_id": other_id,
                "related_title": related.title if related is not None else other_id,
                "related_layer": related.layer if related is not None else None,
                "related_type": related.entity_type if related is not None else None,
            }
        )

    return {
        "entity": asdict(entity),
        "chunks": [asdict(chunk) for chunk in chunks],
        "relations": relations,
        "timeline_events": [
            asdict(event) for event in repository.list_timeline_events(entity.geode_id)
        ],
        "source_versions": [
            asdict(version) for version in repository.list_source_versions(entity.geode_id)
        ],
    }


def main() -> None:
    """Run the detail bridge and print JSON."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--id", required=True)
    args = parser.parse_args()
    detail = detail_index(Path(args.database), args.id)
    print(json.dumps(detail, ensure_ascii=False))


if __name__ == "__main__":
    main()
