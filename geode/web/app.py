"""FastAPI factory for the Geode read API."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def create_app(project_root: Path, database_path: Path) -> Any:
    """Create the optional FastAPI read app."""

    try:
        from fastapi import FastAPI
    except ImportError as exc:
        raise RuntimeError("FastAPI is not installed") from exc

    app = FastAPI(title="Geode Commons Read API")

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return a minimal health response."""

        return {
            "status": "ok",
            "project_root": project_root.as_posix(),
            "database_path": database_path.as_posix(),
        }

    return app
