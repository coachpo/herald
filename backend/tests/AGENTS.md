# backend/tests/AGENTS.md

Tests create temporary SQLite databases and private settings. Keep tests independent and use mocked provider transports; never point fixtures at a user's live data directory or send real notifications.

Verify durable receipt, same-key replay/conflict, failed-only manual retry, bounded worker claims, restart recovery, cleanup retention, authentication separation, configuration redaction, and SSRF enforcement. A provider success followed by a crash can be repeated: do not assert exactly-once external effects.

From the repository root:

```bash
uv run --project backend --locked pytest backend/tests -q
```
