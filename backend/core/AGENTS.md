# backend/core/AGENTS.md

## Shared Helper Constraints

- Keep these helpers framework-independent; services and providers share them.
- Preserve URL guarding in `ssrf.assert_ssrf_safe()` and bare-host guarding in `ssrf.assert_host_ssrf_safe()`. Do not weaken loopback/link-local rejection or bypass the existing private-network policy at callers.
- Add secret-like header names centrally in `redaction.redact_headers()`, not ad hoc at storage/logging call sites.
- Use `crypto.py` for channel encryption; do not add ad hoc encryption or expose decrypted configs in logs, errors, or response metadata.
- `rules.rule_matches_message()` is shared by live ingest and rule preview/test. Check both message shapes and the [API contract](../../docs/04_api_spec.md#rules) before changing it; do not add provider-specific branches.
- Keep `template.py` data-only; missing values must not become executable code.
- Validate affected behavior with the existing `backend/tests/test_core.py` and relevant provider/API tests using the dedicated PostgreSQL setup in the parent guide.
