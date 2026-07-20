"""FastAPI application factory for the Geode Commons read API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geode.web.config import WebSettings, load_settings
from geode.web.db import CorpusRepository


def create_app(
    project_root: Path | None = None,
    database_path: Path | None = None,
) -> Any:
    """Create the FastAPI app for read-only corpus access.

    FastAPI is an optional dependency for the web surface. Install it with
    `pip install -e ".[web]"` before running the server.
    """

    try:
        from fastapi import FastAPI
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'FastAPI is not installed. Install the web extra with `pip install -e ".[web]"`.'
        ) from exc

    from geode.web.routes import entities, search

    settings = load_settings(project_root=project_root, database_path=database_path)
    repository = CorpusRepository(settings.database_path)
    app = FastAPI(
        title="Geode Commons Read API",
        version="0.1.0",
        description="Read-only API over the derived Project Geode corpus index.",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return service and index status."""

        run = repository.latest_index_run()
        return {
            "status": "ok",
            "database_path": settings.database_path.as_posix(),
            "latest_index_status": run.status if run else "not_indexed",
        }

    search.register_routes(app, repository)
    entities.register_routes(app, repository)
    return app


def get_settings() -> WebSettings:
    """Return default web settings for diagnostics and tests."""

    return load_settings()
