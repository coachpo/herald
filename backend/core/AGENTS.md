# backend/core/AGENTS.md

## Overview

Security and data-shaping helpers shared by services, providers, and tests. Small files here have high blast radius.

## Files

| File | Role |
| --- | --- |
| `crypto.py` | Fernet JSON encryption/decryption for channel configs |
| `redaction.py` | Header redaction before message storage/logging |
| `rules.py` | Framework-independent rule matching |
| `ssrf.py` | DNS/IP/network guard for outbound URLs and MQTT hosts |
| `template.py` | Payload template rendering for provider dispatch |

## Conventions

- Keep helpers framework-independent and easy to unit test.
- `assert_ssrf_safe()` guards user-controlled URLs; `assert_host_ssrf_safe()` guards bare hosts such as MQTT hosts.
- `redact_headers()` protects stored message headers; add secret-like header names here, not at call sites.
- Rule matching is shared by live ingest and rule preview/test behavior; keep filter semantics aligned with API docs.
- Template rendering should treat missing values as data problems, not code execution.

## Do Not

- Do not weaken current SSRF rejection for loopback, link-local, and private network targets.
- Do not add provider-specific branching to `rules.py`.
- Do not serialize decrypted channel configs into logs, errors, or response metadata.
- Do not use ad hoc encryption or redaction outside this package.
