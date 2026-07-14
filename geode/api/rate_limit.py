"""Lightweight per-key API rate limiting."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from geode.api.auth import ApiPrincipal
from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, load_json


class ApiRateLimitError(ValueError):
    """Raised when a key has used its current request allowance."""

    def __init__(self, message: str, retry_after_seconds: int) -> None:
        """Create a rate-limit error."""

        super().__init__(message)
        self.status_code = 429
        self.retry_after_seconds = retry_after_seconds


def rate_limit_state_path(root: Path) -> Path:
    """Return the local API rate-limit state file."""

    return root / CONTROL_PLANE_DIR / "API_RATE_LIMIT_STATE.json"


def check_rate_limit(
    root: Path,
    principal: ApiPrincipal,
    now: datetime | None = None,
) -> None:
    """Record one request and raise if the caller exceeds its minute limit."""

    limit = principal.rate_limit_per_minute
    if limit is None or limit <= 0:
        return

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    window_start = current_time.replace(second=0, microsecond=0)
    retry_after = 60 - current_time.second
    path = rate_limit_state_path(root)
    payload = _load_state(path)
    windows = payload.setdefault("windows", {})
    _prune_old_windows(windows, window_start.isoformat())
    key_state = windows.get(principal.key_id)
    if not isinstance(key_state, dict) or key_state.get("window_start") != window_start.isoformat():
        key_state = {"window_start": window_start.isoformat(), "count": 0}

    count = int(key_state.get("count") or 0)
    if count >= limit:
        raise ApiRateLimitError("API key rate limit exceeded", retry_after)

    key_state["count"] = count + 1
    windows[principal.key_id] = key_state
    atomic_write_json(path, payload, root)


def _load_state(path: Path) -> dict[str, Any]:
    """Load rate-limit state if it exists."""

    if not path.exists():
        return {"version": 1, "windows": {}}
    payload = load_json(path)
    if not isinstance(payload, dict):
        return {"version": 1, "windows": {}}
    windows = payload.get("windows")
    if not isinstance(windows, dict):
        payload["windows"] = {}
    return payload


def _prune_old_windows(windows: dict[str, Any], current_window: str) -> None:
    """Keep only the current window for each key."""

    stale_keys = []
    for key_id, value in windows.items():
        if not isinstance(value, dict) or value.get("window_start") != current_window:
            stale_keys.append(key_id)
    for key_id in stale_keys:
        del windows[key_id]
