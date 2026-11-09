# Data model

The local `herald.sqlite3` contains three application tables:

| Table | Purpose |
| --- | --- |
| `targets` | Provider kind/name, encrypted configuration, enabled/default flags |
| `messages` | Durable message content, request fingerprint/idempotency key, creation time |
| `deliveries` | One target/message job, state, total/cycle attempts, due/completion times, sanitized last error |

A message and its selected delivery rows are created in one transaction. The selected jobs remain durable after the receipt response. Each delivery keeps its own state, so a successful target is not resent when another target fails.

States are `pending`, `sending`, `retry`, `sent`, and `failed`. A retryable failure enters `retry` and schedules the next attempt; after the cycle limit, a delivery is `failed`. Only `failed` can be manually retried. The next cycle resets its cycle attempt counter while retaining total attempts. Startup recovers interrupted `sending` work, which may duplicate an external send.

Targets with unfinished delivery work cannot be deleted. Successful history remains inspectable after permitted target deletion. No API deletes pending or failed messages. Cleanup removes a message and its deliveries only when every delivery is successful and the latest completion is older than the configured retention period (default 30 days).

SQLite uses WAL, synchronous FULL, foreign keys, and short transactions. The data directory also contains private `credentials.env` and a process lock. Keep the encryption key with a protected backup: restoring only the database cannot recover encrypted target credentials. See [Operations](07_operations.md#backup-and-restore).
