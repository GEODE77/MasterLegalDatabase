"""Usage logging for Geode API requests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from geode.api.auth import ApiPrincipal
from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import append_jsonl_record_atomic


class ApiUsageRecord(BaseModel):
    """One API request log row."""

    timestamp: str
    key_id: str
    label: str
    method: str
    route: str
    status_code: int
    detail: str | None = None


def usage_log_path(root: Path) -> Path:
    """Return the API usage log path."""

    return root / CONTROL_PLANE_DIR / "API_USAGE_LOG.jsonl"


def log_usage(
    root: Path,
    principal: ApiPrincipal,
    method: str,
    route: str,
    status_code: int,
    detail: str | None = None,
) -> None:
    """Append one API usage event."""

    record = ApiUsageRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        key_id=principal.key_id,
        label=principal.label,
        method=method,
        route=route,
        status_code=status_code,
        detail=detail,
    )
    append_jsonl_record_atomic(usage_log_path(root), record, root)
