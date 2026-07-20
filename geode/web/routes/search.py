"""Search routes for the optional FastAPI read API."""

from __future__ import annotations

from typing import Any

from geode.web.db import CorpusRepository


def register_routes(app: Any, repository: CorpusRepository) -> None:
    """Register search endpoints on a FastAPI application."""

    @app.get("/api/search")
    def search(q: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search indexed legal entities."""

        results = repository.search_entities(q, limit=max(1, min(limit, 100)))
        return [result.model_dump(mode="json") for result in results]
