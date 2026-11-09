# backend/core/AGENTS.md

Keep helpers framework-independent. Preserve SSRF URL/bare-host checks, validation of all resolved addresses, private/link-local/loopback rejection, and TLS verification. DNS validation and the actual client connection are separate operations; do not describe them as address pinning. Use `crypto.py` for target configuration encryption. Never expose decrypted configuration, auth headers, tokens, or transport URLs in errors or logs.

Run affected provider, SSRF, and API tests from `backend/tests/` using the parent guide. No external database or real provider request is required.
