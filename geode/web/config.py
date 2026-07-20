"""Configuration helpers for the Geode Commons read API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DATABASE_RELATIVE_PATH = Path("data") / "structured_output" / "geode_commons.sqlite3"


@dataclass(frozen=True)
class WebSettings:
    """Runtime settings for the read API and derived corpus index."""

    project_root: Path
    database_path: Path


def default_project_root() -> Path:
    """Return the current working directory as the default project root."""

    return Path.cwd()


def default_database_path(project_root: Path) -> Path:
    """Return the default generated SQLite database path for a project root."""

    configured = os.getenv("GEODE_WEB_DB_PATH")
    if configured:
        return Path(configured).expanduser()
    return project_root / DEFAULT_DATABASE_RELATIVE_PATH


def load_settings(
    project_root: Path | None = None,
    database_path: Path | None = None,
) -> WebSettings:
    """Load web settings from explicit values and environment defaults."""

    root = (project_root or default_project_root()).resolve()
    db_path = (database_path or default_database_path(root)).resolve()
    return WebSettings(project_root=root, database_path=db_path)
