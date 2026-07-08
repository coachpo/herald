# UI Spec

## Routes

- `/login`
- `/signup`
- `/`
- `/messages`
- `/messages/:id`
- `/channels`
- `/rules`
- `/ingest-endpoints`
- `/account`

## Dashboard

- Home shows quick actions, recent messages, recent failures, and a static getting-started list.
- Messages page supports endpoint, priority range, and time filters plus batch delete by age and optional endpoint.
- Message detail shows payload fields, request metadata, deliveries, and soft delete.
- Channels page creates, tests, and deletes Bark, ntfy, MQTT, and Gotify channels.
- Rules page creates enabled/disabled rules with endpoint chips, body contains/regex, priority min/max, tags, group, and JSON payload templates. The tester runs a sample payload against all rules for a selected endpoint.
- Ingest endpoints page creates endpoints, shows the raw key once, lists existing endpoints, copies ingest URLs, and can revoke or archive endpoints.
- Account page changes email/password and deletes the account.

## Auth Storage

Refresh tokens stay in `sessionStorage`. Access tokens stay in React state.
