# backend/services/AGENTS.md

## Service Boundaries

- Use `database.get_tables()` and reflected SQLAlchemy tables. Services own data access and commits/rollbacks; routes translate `services.exceptions` into HTTP responses.
- Return schema objects or dicts expected by routes; keep UUID serialization dashed through `serialize_uuid()`/schemas.
- Use `channel_records.py` to read/write encrypted configs. Channel tests call the shared dispatcher; do not duplicate provider transport logic in services.
- `ingest.validate_ingest_payload()` is the public JSON trust boundary. Authenticate using `auth.tokens.hash_token()` and `hmac.compare_digest()`, including endpoint revocation/deletion and user-active checks.
- Preserve relay-message idempotency and duplicate-insert rollback behavior in `create_ingest_message()`; redact request headers before storage.
- Rule evaluation currently receives different message shapes in live ingest and preview/test. Verify both callers and the [known limitations](../../docs/04_api_spec.md#rules) when changing filters.
- Run affected ingest/dashboard/auth tests under `backend/tests/` with the parent guide's dedicated PostgreSQL setup.
