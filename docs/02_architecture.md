# Architecture

Herald has one owner and one runtime process. One resident FastAPI application process serves the management API, ingest API, built dashboard, and a bounded asynchronous delivery loop. MQTT attempts use bounded, short-lived child processes for blocking DNS/connect work; timeout or cancellation terminates and joins them. SQLite is the only database; no external queue, database service, relay, or standalone worker is required.

```text
Sender -- ingest token --> POST /api/ingest --+--> SQLite message + deliveries
Dashboard -- admin token --> POST /api/messages --+              |
                                                              worker
                                                                |
                                                     Bark / ntfy / MQTT / Gotify
```

The APIs share `Store.receive`. It resolves explicit targets or enabled defaults, rejects an empty selection, and atomically writes one message and one delivery per target before returning `201`. A repeated idempotency key with the same request returns `200`; a conflicting request returns `409`. No key means a new message.

SQLite connections use WAL, synchronous FULL, foreign keys, and a bounded busy timeout. Transactions are short; provider network calls run after the claim transaction commits. A filesystem lock prevents a second process from using the same data directory.

The delivery loop claims at most the available concurrency slots (default four). Attempts are counted before the provider call. Retryable failures back off exponentially from 5 to 300 seconds; each retry cycle permits five attempts. Terminal failures remain visible and may be manually retried. Manual retry does not resend a successful delivery. On startup, interrupted `sending` work becomes eligible again.

The delivery guarantee is at least once. A provider may accept a message before Herald records success; a restart can then send it again. Request idempotency prevents duplicate receipt, but cannot provide end-to-end exactly-once provider effects.

Only fully successful messages whose last delivery completed more than 30 days ago are eligible for operator-triggered cleanup. Pending and failed work remain. See [Data model](03_data_model.md) and [Operations](07_operations.md).

Receipt idempotency lasts while the message record remains. After successful-history cleanup removes it, the same key can create a new message.
