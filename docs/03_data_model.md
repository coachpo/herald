# Data model

The local `herald.sqlite3` uses schema version 2 and contains four application tables:

| Table | Purpose |
| --- | --- |
| `targets` | Provider kind/name, encrypted configuration, enabled/default flags |
| `messages` | Durable message content, request fingerprint/idempotency key, creation time, nullable `routing_decision_json` |
| `deliveries` | One target/message job, state, total/cycle attempts, due/completion times, sanitized last error |
| `routing_config` | Singleton row (`id=1`) with non-null revision and complete `rules_json`; initially revision 0 and `[]` |

A message, its routing decision, and its selected delivery rows are created in one transaction. The selected jobs remain durable after the receipt response. Each delivery keeps its own state, so a successful target is not resent when another target fails. Routing configuration updates validate the revision and all target references in one write transaction before replacing the full array and incrementing the revision, including when clearing rules.

Read APIs expose parsed `routing_decision`, not the raw JSON column. Its `mode` is `explicit`, `rules`, or `defaults`; `rules_revision` is null for explicit selection and the read configuration version for automatic selection. `matched_rule_ids` preserves matching rule order and is empty for explicit/default selection. Messages predating the migration expose `routing_decision: null`. Decisions do not copy rule bodies, message content, or target configurations and are not a complete historical rule audit. Existing deliveries remain the source of the actual target set; retries do not recompute routing.

States are `pending`, `sending`, `retry`, `sent`, and `failed`. A retryable failure enters `retry` and schedules the next attempt; after the cycle limit, a delivery is `failed`. Only `failed` can be manually retried. The next cycle resets its cycle attempt counter while retaining total attempts. Startup recovers interrupted `sending` work, which may duplicate an external send.

Targets with unfinished delivery work or any rule reference cannot be deleted. Disabled rules still retain their references, so remove those references before deleting a target. Rule references are checked by Store from the JSON configuration inside the deletion transaction, without a separate join table. Successful history remains inspectable after permitted target deletion. No API deletes pending or failed messages. Cleanup removes a message and its deliveries only when every delivery is successful and the latest completion is older than the configured retention period (default 30 days).

Fresh databases initialize directly at v2. Existing v1 stores migrate in one transaction: add the routing singleton and nullable decision column, seed the empty configuration, and set `PRAGMA user_version=2`. A failure rolls back DDL, initial data, and version together. Existing message IDs, fingerprints/idempotency keys, delivery states and counters, encrypted target configurations, foreign keys, and unique constraints are preserved. Reinitializing v2 does not reset routing. Higher unsupported schema versions are rejected; no downgrade migration is provided. Back up before upgrading; see [Operations](07_operations.md#schema-upgrades).

SQLite uses WAL, synchronous FULL, foreign keys, and short transactions. The data directory also contains private `credentials.env` and a process lock. Keep the encryption key with a protected backup: restoring only the database cannot recover encrypted target credentials. See [Operations](07_operations.md#backup-and-restore).
