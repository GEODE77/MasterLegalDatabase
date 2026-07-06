"""Shared metadata helpers for raw source download manifests."""

from __future__ import annotations

from collections.abc import Mapping

COLORADO_JURISDICTION = "Colorado"


def missing_metadata_fields(fields: Mapping[str, object]) -> list[str]:
    """Return field names whose metadata values are absent."""

    missing = []
    for name, value in fields.items():
        if value is None:
            missing.append(name)
        elif isinstance(value, str) and not value.strip():
            missing.append(name)
        elif isinstance(value, list | tuple | set | dict) and not value:
            missing.append(name)
    return sorted(missing)


def source_format_from_extension(extension: str, default: str = "unknown") -> str:
    """Normalize a file extension into a manifest source format value."""

    suffix = extension.strip().lower().lstrip(".")
    return suffix or default
