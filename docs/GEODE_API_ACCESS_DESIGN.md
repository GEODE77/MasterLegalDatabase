# Geode API Access Design

Project Geode needs two kinds of outside access:

- **Small lookups** for tools, agents, and applications that need one record at a time.
- **Bulk exports** for partners who need a full copy of one or more Geode layers.

This design keeps the first API small. It does not change the source archive,
does not invent new legal data, and does not make the API responsible for
extraction. The API is a read layer over the already-validated Geode corpus and
orchestration outputs.

The API is for AI agents, downstream tools, search clients, ingestion operators,
and controlled partners.

## Access Model

Every caller receives an API key. The caller sends that key on each request:

```text
X-Geode-API-Key: <GEODE_API_KEY>
```

Geode checks the key before returning data:

1. The key must exist in the Geode admin file.
2. The key must be active.
3. The key must have the needed permission.
4. The request is written to the usage log.

The admin file stores only a hash of the key, not the key itself.

```text
_CONTROL_PLANE/API_KEYS.json
```

An example file is provided at:

```text
_CONTROL_PLANE/API_KEYS.example.json
```

New keys should be created with the admin command instead of hand-editing the file:

```text
geode-api-admin create-key --label "Partner name"
```

The command prints the real API key one time. Geode stores only the hashed value in:

```text
_CONTROL_PLANE/API_KEYS.json
```

To allow bulk downloads, create the key with:

```text
geode-api-admin create-key --label "Partner name" --bulk-export
```

To review keys without exposing the actual key values:

```text
geode-api-admin list-keys
```

For a machine-readable review:

```text
geode-api-admin list-keys --json
```

To turn off a key without deleting its record:

```text
geode-api-admin deactivate-key <key_id> --reason "No longer needed"
```

To replace the secret value while keeping the same key ID:

```text
geode-api-admin rotate-key <key_id> --reason "Scheduled rotation"
```

Admin actions are written to a non-secret local audit log:

```text
_CONTROL_PLANE/API_KEY_ADMIN_LOG.jsonl
```

## First API Surface

The first version should expose these endpoints:

```text
GET /health
```

Confirms the API process is running. This does not require a key.

```text
GET /v1/manifest
```

Returns `MASTER_MANIFEST.json`, which tells a caller what Geode currently contains.

```text
GET /v1/statutes/{id}
```

Returns one CRS record. The response includes the index metadata and the section text
when the section can be found in the title Markdown file.

```text
GET /v1/regulations/{id}
```

Returns one CCR record. For normalized CCR records, the response includes the normalized
JSON record.

```text
GET /v1/search?q=...
```

Searches the lightweight layer indexes. This first version searches IDs, titles,
citations, and tags. It is meant for discovery, not final legal analysis.

```text
POST /v1/exports
```

Creates a ZIP package for selected layers. The package includes validated Geode outputs
and may include crosswalks. It never includes `_RAW_ARCHIVE/`.

```text
GET /v1/exports/{export_id}/download
```

Downloads an export created by the caller.

## Permission Names

The first version uses simple permission names:

```text
manifest:read
statutes:read
regulations:read
search:read
exports:create
exports:download
```

An internal key may use `*` for all permissions.

Unknown permission names are rejected by the admin command. This avoids creating a key
that appears to have access but cannot actually use any endpoint.

## Bulk Export Rules

Bulk export is the most sensitive part of the API because it can copy a large amount of
data. The first version follows these rules:

- Exports are created under `_CONTROL_PLANE/API_EXPORTS/`.
- Export files receive unique IDs so normal use does not overwrite previous exports.
- `_RAW_ARCHIVE/` is always excluded.
- A key must have `exports:create`.
- The key record must also allow bulk exports.
- Usage is logged.

## Rate Limits

Each key can carry a per-minute request limit:

```text
rate_limit_per_minute
```

The API enforces this value before serving protected endpoints. Local rate-limit state is
kept in:

```text
_CONTROL_PLANE/API_RATE_LIMIT_STATE.json
```

This is intentionally simple and local. For a hosted multi-server deployment, this should
move to shared infrastructure so every server sees the same counters.

## Usage Logging

Usage is written to:

```text
_CONTROL_PLANE/API_USAGE_LOG.jsonl
```

Each line records:

- when the request happened
- which key was used
- the route
- the status
- the client label if available

This gives Geode a basic audit trail without adding a database too early.

Key-management actions are logged separately from data requests. This makes it easier to
review who created, deactivated, or rotated access.

## What This First Version Does Not Try To Solve

This is intentionally not the final commercial API layer. It does not yet include:

- billing
- automatic customer signup
- advanced rate limiting
- hosted object storage
- token-level analytics
- semantic search
- customer-facing account surfaces

Those can be added after the access pattern is proven.

## Recommended Next Improvement

After this first version is working, the next improvement should be a hosted export
store. Instead of keeping export ZIP files inside the project folder, Geode would place
large exports in private storage and give callers short-lived download links. That would
make large partner downloads easier to manage and safer to expire.
