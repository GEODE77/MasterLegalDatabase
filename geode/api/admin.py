"""Admin command for managing Geode API keys."""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel

from geode.api.auth import ApiKeyFile, ApiKeyRecord, create_api_key_hash, default_key_file
from geode.api.auth import key_record_to_public_dict, load_api_key_file
from geode.api.auth import validate_scope_names
from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import append_jsonl_record_atomic, atomic_write_json

DEFAULT_READ_SCOPES = (
    "manifest:read",
    "statutes:read",
    "regulations:read",
    "search:read",
)
EXPORT_SCOPES = ("exports:create", "exports:download")
KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")


@dataclass(frozen=True)
class CreatedApiKey:
    """Result returned after creating one API key."""

    raw_key: str
    record: ApiKeyRecord
    key_file: Path


class ApiKeyAdminEvent(BaseModel):
    """One non-secret API key administration event."""

    timestamp: str
    action: str
    key_id: str
    label: str
    actor: str
    detail: str | None = None


def generate_api_key() -> str:
    """Create a new raw Geode API key."""

    return f"geode_live_{secrets.token_urlsafe(32)}"


def create_key_record(
    root: Path,
    label: str,
    key_id: str | None = None,
    scopes: Sequence[str] | None = None,
    bulk_export_allowed: bool = False,
    rate_limit_per_minute: int | None = 60,
    expires_at: datetime | None = None,
    raw_key: str | None = None,
    created_by: str = "local-admin",
    now: datetime | None = None,
) -> CreatedApiKey:
    """Create one key record and store only its hash in the admin file."""

    project_root = root.resolve()
    now = now or datetime.now(timezone.utc)
    key_file = default_key_file(project_root)
    key_data = load_api_key_file(key_file)
    _validate_label(label)
    final_key_id = key_id or _generated_key_id(label)
    _validate_key_id(final_key_id)
    _ensure_unique_key_id(key_data, final_key_id)
    final_scopes = _normalized_scopes(scopes, bulk_export_allowed)
    api_key = raw_key or generate_api_key()
    record = ApiKeyRecord(
        key_id=final_key_id,
        label=label,
        key_hash=create_api_key_hash(api_key),
        active=True,
        scopes=final_scopes,
        bulk_export_allowed=bulk_export_allowed,
        rate_limit_per_minute=rate_limit_per_minute,
        expires_at=expires_at,
        created_at=now,
        created_by=created_by,
    )
    updated = ApiKeyFile(version=key_data.version, keys=[*key_data.keys, record])
    atomic_write_json(key_file, updated.model_dump(mode="json"), project_root)
    _log_admin_event(project_root, "create_key", record, created_by)
    return CreatedApiKey(raw_key=api_key, record=record, key_file=key_file)


def list_key_records(root: Path, include_inactive: bool = True) -> list[dict[str, object]]:
    """Return non-secret API key records."""

    key_data = load_api_key_file(default_key_file(root.resolve()))
    records = []
    for record in key_data.keys:
        if not include_inactive and not record.active:
            continue
        records.append(key_record_to_public_dict(record))
    return records


def deactivate_key_record(
    root: Path,
    key_id: str,
    deactivated_by: str = "local-admin",
    reason: str | None = None,
    now: datetime | None = None,
) -> ApiKeyRecord:
    """Mark one API key inactive without deleting its record."""

    project_root = root.resolve()
    now = now or datetime.now(timezone.utc)
    key_file = default_key_file(project_root)
    key_data = load_api_key_file(key_file)
    updated_records: list[ApiKeyRecord] = []
    deactivated: ApiKeyRecord | None = None
    for record in key_data.keys:
        if record.key_id == key_id:
            deactivated = record.model_copy(
                update={
                    "active": False,
                    "deactivated_at": now,
                    "deactivated_by": deactivated_by,
                    "deactivation_reason": reason,
                }
            )
            updated_records.append(deactivated)
        else:
            updated_records.append(record)
    if deactivated is None:
        raise KeyError(f"API key ID not found: {key_id}")
    updated = ApiKeyFile(version=key_data.version, keys=updated_records)
    atomic_write_json(key_file, updated.model_dump(mode="json"), project_root)
    _log_admin_event(project_root, "deactivate_key", deactivated, deactivated_by, reason)
    return deactivated


def rotate_key_record(
    root: Path,
    key_id: str,
    rotated_by: str = "local-admin",
    reason: str | None = None,
    raw_key: str | None = None,
    now: datetime | None = None,
) -> CreatedApiKey:
    """Replace one key's secret while keeping its stable key ID."""

    project_root = root.resolve()
    now = now or datetime.now(timezone.utc)
    key_file = default_key_file(project_root)
    key_data = load_api_key_file(key_file)
    api_key = raw_key or generate_api_key()
    updated_records: list[ApiKeyRecord] = []
    rotated: ApiKeyRecord | None = None
    for record in key_data.keys:
        if record.key_id == key_id:
            rotated = record.model_copy(
                update={
                    "key_hash": create_api_key_hash(api_key),
                    "rotated_at": now,
                    "rotation_count": record.rotation_count + 1,
                }
            )
            updated_records.append(rotated)
        else:
            updated_records.append(record)
    if rotated is None:
        raise KeyError(f"API key ID not found: {key_id}")
    updated = ApiKeyFile(version=key_data.version, keys=updated_records)
    atomic_write_json(key_file, updated.model_dump(mode="json"), project_root)
    _log_admin_event(project_root, "rotate_key", rotated, rotated_by, reason)
    return CreatedApiKey(raw_key=api_key, record=rotated, key_file=key_file)


def build_parser() -> argparse.ArgumentParser:
    """Build the admin command parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-key", help="Create one API key.")
    create.add_argument("--root", type=Path, default=Path.cwd(), help="Geode project root.")
    create.add_argument("--key-id", help="Stable internal key ID. Generated if omitted.")
    create.add_argument("--label", required=True, help="Human label for the caller.")
    create.add_argument(
        "--scope",
        action="append",
        dest="scopes",
        help="Permission to grant. Can be used more than once.",
    )
    create.add_argument(
        "--all-scopes",
        action="store_true",
        help="Grant all API permissions with the wildcard scope.",
    )
    create.add_argument(
        "--bulk-export",
        action="store_true",
        help="Allow this key to create and download bulk exports.",
    )
    create.add_argument(
        "--rate-limit-per-minute",
        type=int,
        default=60,
        help="Basic rate limit note stored with the key.",
    )
    create.add_argument(
        "--expires-at",
        help="Optional expiration time, such as 2026-12-31T00:00:00Z.",
    )
    create.add_argument(
        "--created-by",
        default="local-admin",
        help="Person or process creating the key.",
    )

    list_keys = subparsers.add_parser("list-keys", help="List non-secret API key records.")
    list_keys.add_argument("--root", type=Path, default=Path.cwd(), help="Geode project root.")
    list_keys.add_argument(
        "--active-only",
        action="store_true",
        help="Show only active API keys.",
    )
    list_keys.add_argument("--json", action="store_true", help="Print JSON instead of text.")

    deactivate = subparsers.add_parser("deactivate-key", help="Deactivate one API key.")
    deactivate.add_argument("--root", type=Path, default=Path.cwd(), help="Geode project root.")
    deactivate.add_argument("key_id", help="The key ID to deactivate.")
    deactivate.add_argument(
        "--deactivated-by",
        default="local-admin",
        help="Person or process deactivating the key.",
    )
    deactivate.add_argument("--reason", help="Short reason for the deactivation.")

    rotate = subparsers.add_parser("rotate-key", help="Rotate one API key secret.")
    rotate.add_argument("--root", type=Path, default=Path.cwd(), help="Geode project root.")
    rotate.add_argument("key_id", help="The key ID to rotate.")
    rotate.add_argument(
        "--rotated-by",
        default="local-admin",
        help="Person or process rotating the key.",
    )
    rotate.add_argument("--reason", help="Short reason for the rotation.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the API admin command."""

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "create-key":
        scopes = ["*"] if args.all_scopes else args.scopes
        result = create_key_record(
            root=args.root,
            key_id=args.key_id,
            label=args.label,
            scopes=scopes,
            bulk_export_allowed=bool(args.bulk_export or args.all_scopes),
            rate_limit_per_minute=args.rate_limit_per_minute,
            expires_at=_parse_expires_at(args.expires_at),
            created_by=args.created_by,
        )
        sys.stdout.write(_format_created_key(result))
    elif args.command == "list-keys":
        records = list_key_records(args.root, include_inactive=not args.active_only)
        if args.json:
            sys.stdout.write(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
        else:
            sys.stdout.write(_format_key_list(records))
    elif args.command == "deactivate-key":
        try:
            record = deactivate_key_record(
                args.root,
                args.key_id,
                deactivated_by=args.deactivated_by,
                reason=args.reason,
            )
        except KeyError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1
        sys.stdout.write(_format_deactivated_key(record))
    elif args.command == "rotate-key":
        try:
            result = rotate_key_record(
                args.root,
                args.key_id,
                rotated_by=args.rotated_by,
                reason=args.reason,
            )
        except KeyError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1
        sys.stdout.write(_format_rotated_key(result))
    else:
        parser.error("unknown command")
    return 0


def _normalized_scopes(
    scopes: Sequence[str] | None,
    bulk_export_allowed: bool,
) -> list[str]:
    """Return the final permission list for a new key."""

    final_scopes = list(scopes or DEFAULT_READ_SCOPES)
    if bulk_export_allowed and "*" not in final_scopes:
        final_scopes.extend(scope for scope in EXPORT_SCOPES if scope not in final_scopes)
    return validate_scope_names(final_scopes)


def _generated_key_id(label: str) -> str:
    """Generate a readable key ID from a label."""

    slug = re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-")
    if not slug:
        slug = "api-key"
    return f"{slug[:40]}-{uuid.uuid4().hex[:8]}"


def _ensure_unique_key_id(key_data: ApiKeyFile, key_id: str) -> None:
    """Raise if a key ID already exists."""

    existing = {record.key_id for record in key_data.keys}
    if key_id in existing:
        raise ValueError(f"API key ID already exists: {key_id}")


def _validate_key_id(key_id: str) -> None:
    """Validate the stable admin-facing key ID."""

    if not KEY_ID_RE.match(key_id):
        raise ValueError(
            "API key ID must be 3-80 lowercase letters, numbers, dots, underscores, or hyphens"
        )


def _validate_label(label: str) -> None:
    """Validate a human key label."""

    if not label.strip():
        raise ValueError("API key label cannot be blank")


def _parse_expires_at(value: str | None) -> datetime | None:
    """Parse an optional ISO expiration date."""

    if value is None:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _format_created_key(result: CreatedApiKey) -> str:
    """Format the one-time key creation response."""

    record = result.record
    scopes = ", ".join(record.scopes)
    bulk = "yes" if record.bulk_export_allowed else "no"
    path = result.key_file.as_posix()
    return (
        "Created Geode API key\n"
        f"Key ID: {record.key_id}\n"
        f"Label: {record.label}\n"
        f"Scopes: {scopes}\n"
        f"Bulk export: {bulk}\n"
        f"Stored admin file: {path}\n"
        f"API key shown once: {result.raw_key}\n"
        "Store this key now. Geode saved only its hash.\n"
    )


def _format_rotated_key(result: CreatedApiKey) -> str:
    """Format the one-time key rotation response."""

    record = result.record
    return (
        "Rotated Geode API key\n"
        f"Key ID: {record.key_id}\n"
        f"Label: {record.label}\n"
        f"API key shown once: {result.raw_key}\n"
        "Store this key now. Geode saved only its hash.\n"
    )


def _format_key_list(records: list[dict[str, object]]) -> str:
    """Format non-secret key records for review."""

    if not records:
        return "No Geode API keys found.\n"
    lines = ["Geode API keys"]
    for record in records:
        active = "active" if record["active"] else "inactive"
        raw_scopes = record["scopes"]
        if isinstance(raw_scopes, (list, tuple, set)):
            scopes = ", ".join(str(scope) for scope in raw_scopes)
        else:
            scopes = str(raw_scopes)
        bulk = "yes" if record["bulk_export_allowed"] else "no"
        expires_at = record["expires_at"] or "never"
        created_at = record["created_at"] or "unknown"
        rotated_at = record["rotated_at"] or "never"
        deactivated_at = record["deactivated_at"] or "never"
        lines.extend(
            [
                f"- Key ID: {record['key_id']}",
                f"  Label: {record['label']}",
                f"  Status: {active}",
                f"  Scopes: {scopes}",
                f"  Bulk export: {bulk}",
                f"  Expires: {expires_at}",
                f"  Created: {created_at}",
                f"  Rotated: {rotated_at}",
                f"  Deactivated: {deactivated_at}",
            ]
        )
    return "\n".join(lines) + "\n"


def _format_deactivated_key(record: ApiKeyRecord) -> str:
    """Format a deactivation confirmation."""

    return (
        "Deactivated Geode API key\n"
        f"Key ID: {record.key_id}\n"
        f"Label: {record.label}\n"
        "Status: inactive\n"
    )


def _admin_log_path(root: Path) -> Path:
    """Return the API key admin audit log path."""

    return root / CONTROL_PLANE_DIR / "API_KEY_ADMIN_LOG.jsonl"


def _log_admin_event(
    root: Path,
    action: str,
    record: ApiKeyRecord,
    actor: str,
    detail: str | None = None,
) -> None:
    """Append a non-secret admin audit event."""

    event = ApiKeyAdminEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        action=action,
        key_id=record.key_id,
        label=record.label,
        actor=actor,
        detail=detail,
    )
    append_jsonl_record_atomic(_admin_log_path(root), event, root)


if __name__ == "__main__":
    raise SystemExit(main())
