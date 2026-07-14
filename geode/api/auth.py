"""API key loading and permission checks for the Geode access layer."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import load_json
from geode.utils.hashing import sha256_text

KEY_HASH_PREFIX = "sha256:"
VALID_API_SCOPES = frozenset(
    {
        "*",
        "manifest:read",
        "statutes:read",
        "regulations:read",
        "search:read",
        "exports:create",
        "exports:download",
    }
)


class ApiAuthError(ValueError):
    """Raised when an API key cannot be used for a request."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        """Create an authentication or authorization error."""

        super().__init__(message)
        self.status_code = status_code


class ApiKeyRecord(BaseModel):
    """One API key entry from the Geode admin file."""

    key_id: str
    label: str
    key_hash: str
    active: bool = True
    scopes: list[str] = Field(default_factory=list)
    bulk_export_allowed: bool = False
    rate_limit_per_minute: int | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    created_by: str | None = None
    deactivated_at: datetime | None = None
    deactivated_by: str | None = None
    deactivation_reason: str | None = None
    rotated_at: datetime | None = None
    rotation_count: int = 0


class ApiKeyFile(BaseModel):
    """The API key admin file structure."""

    version: int = 1
    keys: list[ApiKeyRecord] = Field(default_factory=list)


@dataclass(frozen=True)
class ApiPrincipal:
    """The authenticated caller for a Geode API request."""

    key_id: str
    label: str
    scopes: frozenset[str]
    bulk_export_allowed: bool
    rate_limit_per_minute: int | None

    def has_scope(self, scope: str) -> bool:
        """Return whether the caller can use a named permission."""

        return "*" in self.scopes or scope in self.scopes


def default_key_file(root: Path) -> Path:
    """Return the default API key admin file path."""

    return root / CONTROL_PLANE_DIR / "API_KEYS.json"


def create_api_key_hash(api_key: str) -> str:
    """Create the stored hash value for a raw API key."""

    return f"{KEY_HASH_PREFIX}{sha256_text(api_key)}"


def validate_scope_names(scopes: list[str]) -> list[str]:
    """Validate and de-duplicate API permission names."""

    normalized: list[str] = []
    for scope in scopes:
        clean_scope = scope.strip()
        if clean_scope not in VALID_API_SCOPES:
            raise ValueError(f"unknown API scope: {scope}")
        if clean_scope not in normalized:
            normalized.append(clean_scope)
    if "*" in normalized and len(normalized) > 1:
        return ["*"]
    return normalized


def load_api_key_file(path: Path) -> ApiKeyFile:
    """Load the API key admin file."""

    if not path.exists():
        return ApiKeyFile()
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"API key file must contain an object: {path}")
    return ApiKeyFile.model_validate(payload)


def authenticate_api_key(
    api_key: str | None,
    key_file: Path,
    required_scope: str | None = None,
    now: datetime | None = None,
) -> ApiPrincipal:
    """Authenticate a raw key and optionally check one permission."""

    if not api_key:
        raise ApiAuthError("missing API key", status_code=401)

    now = now or datetime.now(timezone.utc)
    candidate_hash = create_api_key_hash(api_key)
    key_data = load_api_key_file(key_file)
    for record in key_data.keys:
        if not hmac.compare_digest(record.key_hash, candidate_hash):
            continue
        principal = _principal_from_record(record, now)
        if required_scope and not principal.has_scope(required_scope):
            raise ApiAuthError("API key does not allow this request", status_code=403)
        return principal

    raise ApiAuthError("invalid API key", status_code=401)


def _principal_from_record(record: ApiKeyRecord, now: datetime) -> ApiPrincipal:
    """Convert a key record into a caller after status checks."""

    if not record.active:
        raise ApiAuthError("API key is inactive", status_code=403)
    if record.expires_at and record.expires_at <= now:
        raise ApiAuthError("API key is expired", status_code=403)
    return ApiPrincipal(
        key_id=record.key_id,
        label=record.label,
        scopes=frozenset(record.scopes),
        bulk_export_allowed=record.bulk_export_allowed,
        rate_limit_per_minute=record.rate_limit_per_minute,
    )


def key_record_to_public_dict(record: ApiKeyRecord) -> dict[str, Any]:
    """Return a non-secret summary of an API key record."""

    return {
        "key_id": record.key_id,
        "label": record.label,
        "active": record.active,
        "scopes": list(record.scopes),
        "bulk_export_allowed": record.bulk_export_allowed,
        "rate_limit_per_minute": record.rate_limit_per_minute,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "created_by": record.created_by,
        "deactivated_at": record.deactivated_at.isoformat() if record.deactivated_at else None,
        "deactivated_by": record.deactivated_by,
        "deactivation_reason": record.deactivation_reason,
        "rotated_at": record.rotated_at.isoformat() if record.rotated_at else None,
        "rotation_count": record.rotation_count,
    }
