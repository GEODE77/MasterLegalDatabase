"""Entity routes for the optional FastAPI read API."""

from __future__ import annotations

from typing import Any

from geode.web.db import CorpusRepository


def register_routes(app: Any, repository: CorpusRepository) -> None:
    """Register legal entity endpoints on a FastAPI application."""

    @app.get("/api/entities/{geode_id}")
    def get_entity(geode_id: str) -> dict[str, Any]:
        """Return one indexed legal entity by ID or citation alias."""

        entity = repository.resolve_entity(geode_id)
        if entity is None:
            try:
                from fastapi import HTTPException
            except ModuleNotFoundError as exc:
                raise RuntimeError("FastAPI is required to raise API exceptions.") from exc
            raise HTTPException(status_code=404, detail="entity not found")
        return entity.model_dump(mode="json")

    @app.get("/api/entities/{geode_id}/text")
    def get_entity_text(geode_id: str) -> list[dict[str, Any]]:
        """Return indexed text chunks for one legal entity."""

        entity = repository.resolve_entity(geode_id)
        if entity is None:
            try:
                from fastapi import HTTPException
            except ModuleNotFoundError as exc:
                raise RuntimeError("FastAPI is required to raise API exceptions.") from exc
            raise HTTPException(status_code=404, detail="entity not found")
        return [chunk.model_dump(mode="json") for chunk in repository.list_chunks(entity.geode_id)]

    @app.get("/api/entities/{geode_id}/relations")
    def get_entity_relations(geode_id: str) -> list[dict[str, Any]]:
        """Return crosswalk-derived relations for one legal entity."""

        entity = repository.resolve_entity(geode_id)
        target_id = entity.geode_id if entity else geode_id
        return [
            relation.model_dump(mode="json")
            for relation in repository.list_relations(target_id)
        ]

    @app.get("/api/entities/{geode_id}/timeline")
    def get_entity_timeline(geode_id: str) -> list[dict[str, Any]]:
        """Return timeline events for one legal entity."""

        entity = repository.resolve_entity(geode_id)
        target_id = entity.geode_id if entity else geode_id
        return [
            event.model_dump(mode="json")
            for event in repository.list_timeline_events(target_id)
        ]

    @app.get("/api/entities/{geode_id}/source-versions")
    def get_entity_source_versions(geode_id: str) -> list[dict[str, Any]]:
        """Return source fingerprints for one legal entity."""

        entity = repository.resolve_entity(geode_id)
        target_id = entity.geode_id if entity else geode_id
        return [
            version.model_dump(mode="json")
            for version in repository.list_source_versions(target_id)
        ]
