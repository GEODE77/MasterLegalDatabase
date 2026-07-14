# Geode API Key System Audit

Date: 2026-07-14

## Summary

The API key system now has a practical first security layer for local and early partner
use. It creates high-entropy keys, stores only hashes, hides secrets from key review
commands, enforces permissions, supports bulk-export gating, logs usage, logs admin
actions, supports deactivation and rotation, and enforces per-minute limits.

This is suitable for a first controlled Geode access layer. It is not yet a full hosted
commercial access system.

## Audit Findings And Actions

### 1. Raw API Keys

Finding: The design already stored only a hash, which is the correct starting point.

Action completed:

- Added a one-time key creation command.
- Kept `_CONTROL_PLANE/API_KEYS.json` ignored by Git.
- Added tests proving the saved file does not contain the raw key.

### 2. Key Review

Finding: Operators needed a safe way to review keys without exposing key hashes or raw
keys.

Action completed:

- Added `geode-api-admin list-keys`.
- Added `geode-api-admin list-keys --json`.
- Public key summaries omit `key_hash`.

### 3. Key Shutdown

Finding: Operators needed a safe way to turn off access without deleting records.

Action completed:

- Added `geode-api-admin deactivate-key <key_id>`.
- Deactivation preserves the key record.
- Deactivated keys fail authentication.
- Deactivation can include actor and reason details.

### 4. Key Rotation

Finding: Once a key has been shared, there needs to be a way to replace the secret value
without changing the partner-facing key ID.

Action completed:

- Added `geode-api-admin rotate-key <key_id>`.
- Rotation prints the new key once.
- The old key stops working.
- The key record tracks rotation count and last rotation time.

### 5. Admin Audit Trail

Finding: Key-management events were not separately logged.

Action completed:

- Added `_CONTROL_PLANE/API_KEY_ADMIN_LOG.jsonl`.
- Logged create, deactivate, and rotate actions.
- The log does not include raw keys or key hashes.

### 6. Scope Safety

Finding: Permission names were free-form, so a typo could create a misleading key.

Action completed:

- Added a fixed scope allowlist.
- Rejected unknown scopes.
- De-duplicated repeated scopes.

### 7. Rate Limits

Finding: `rate_limit_per_minute` existed as a stored value, but the API did not enforce
it.

Action completed:

- Added local per-key minute limits.
- Protected endpoints check the limit after authentication.
- Exceeded keys receive a 429-style error.

### 8. Data Boundary

Finding: Bulk export must never expose `_RAW_ARCHIVE/`.

Action completed:

- Export code excludes `_RAW_ARCHIVE/`.
- Tests verify raw archive files are not packaged.

## Remaining Future Improvements

These are better handled when Geode is hosted rather than running from a local project
folder:

- Move API keys and rate-limit counters to a managed database or secret store.
- Move bulk export ZIP files to private object storage with expiring links.
- Add customer-level plans, billing status, and contract terms.
- Add an operator review report for key review.
- Add alerting for unusually high usage or repeated failed authentication.
- Add a formal incident process for leaked or misused keys.

## Current Recommendation

The next best improvement is to move exports out of the repository folder and into
private storage once the API is hosted. That will reduce local disk pressure and make
large downloads easier to expire.
