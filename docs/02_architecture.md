# Architecture

Herald has one owner and one runtime process. One resident FastAPI application process serves the management API, ingest API, built dashboard, and a bounded asynchronous delivery loop. MQTT attempts use bounded, short-lived child processes for blocking DNS/connect work; timeout or cancellation terminates and joins them. SQLite is the only database; no external queue, database service, relay, or standalone worker is required.

```text
Sender -- ingest token --> POST /api/ingest --+--> SQLite message + decision + deliveries
Dashboard -- admin token --> POST /api/messages --+              |
                                                              worker
                                                                |
                                                     Bark / ntfy / MQTT / Gotify
```

The APIs share `Store.receive`. Inside one SQLite write transaction it checks the existing idempotency key first, then selects explicit targets or reads the current routing configuration. Explicit nonempty target IDs bypass routing and defaults. Automatic selection scans enabled rules in array order, ANDs each rule's conditions, and unions all matched targets. Only zero matching rules trigger the enabled-default fallback. Every selected target must exist and be enabled; an empty or unavailable selection rejects the entire receipt. One message, its routing decision, and one delivery per selected target commit before returning `201`.

A repeated idempotency key with the same request returns `200` before routing is evaluated again; a conflicting request returns `409`. The existing request fingerprint is unchanged and excludes routing revisions and calculated targets. No key means a new message. Configuration updates and receipt selection are serialized by SQLite write transactions, so a receipt uses one complete routing revision rather than a cached or partly updated configuration.

Routing is a pure matcher over normalized priority/title/body, not a script or general-purpose expression engine. Priority supports `eq/gte/lte`; title/body support case-sensitive `eq/prefix/contains` without trimming. Rule order records the order of matched IDs, not delivery priority. The management API replaces the full rule array using an optimistic revision check. Deleting a target requires clearing every rule reference, including references in disabled rules.

Rules and defaults affect only new receipts. Automatic retries, manual retries, and startup recovery use the already persisted deliveries and never match rules again. Disabling a target does not cancel its accepted work. Each claim reads the target's latest configuration; neither destination configuration nor complete historical rules are snapshotted. The stored decision contains only selection mode, routing revision, and matched rule IDs, and legacy messages have no recorded decision.

SQLite connections use WAL, synchronous FULL, foreign keys, and a bounded busy timeout. Transactions are short; provider network calls run after the claim transaction commits. A filesystem lock prevents a second process from using the same data directory and is acquired before schema initialization or the transactional v1-to-v2 migration.

The delivery loop claims at most the available concurrency slots (default four). Attempts are counted before the provider call. Retryable failures back off exponentially from 5 to 300 seconds; each retry cycle permits five attempts. Terminal failures remain visible and may be manually retried. Manual retry does not resend a successful delivery. On startup, interrupted `sending` work becomes eligible again.

The delivery guarantee is at least once. A provider may accept a message before Herald records success; a restart can then send it again. Request idempotency prevents duplicate receipt, but cannot provide end-to-end exactly-once provider effects.

Only fully successful messages whose last delivery completed more than 30 days ago are eligible for operator-triggered cleanup. Pending and failed work remain. See [Data model](03_data_model.md) and [Operations](07_operations.md).

Receipt idempotency lasts while the message record remains. After successful-history cleanup removes it, the same key can create a new message.
