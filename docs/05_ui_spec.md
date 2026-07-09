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

- The dashboard shell refreshes the session on mount, redirects unauthenticated users to `/login?next=...`, exposes logout, and has a system/light/dark theme toggle stored as `herald_theme` in `localStorage`.
- Home shows quick actions, recent messages, recent failures, and a static getting-started list.
- Messages page supports endpoint, priority range, and time filters plus batch delete by age and optional endpoint.
- Message detail shows payload fields, body wrap/no-wrap, request metadata, extras, headers, query params, deliveries with attempts/timestamps/errors/provider responses, and soft delete.
- Channels page creates, tests, and deletes Bark, ntfy, MQTT, and Gotify channels.
- Rules page creates enabled/disabled rules with endpoint chips, body contains/regex, priority min/max, tags, group, and JSON payload templates. The tester runs a sample payload against enabled rules for a selected endpoint. Endpoint and tag filters are available in the UI/tester, while current live delivery matching only applies body, priority, and group.
- Ingest endpoints page creates endpoints, shows the raw key once, lists existing endpoints, copies dashless ingest URLs and curl examples, and can revoke or archive endpoints.
- Account page changes email/password and deletes the account.

## Auth Storage

Refresh tokens stay in `sessionStorage`. Access tokens stay in React state.
The login `next` parameter is sanitized to same-origin paths before navigation.
