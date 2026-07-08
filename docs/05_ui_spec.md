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

- Home shows quick actions, recent messages, recent failures, and setup progress.
- Messages page supports endpoint, priority range, and time filters plus batch delete.
- Message detail shows payload fields, request metadata, deliveries, and soft delete.
- Channels page creates, tests, and deletes Bark, ntfy, MQTT, and Gotify channels.
- Rules page creates, previews/tests, lists, and deletes rules.
- Ingest endpoints page creates endpoints, shows the raw key once, and provides URL/curl helpers.
- Account page changes email/password and deletes the account.

## Auth Storage

Refresh tokens stay in `sessionStorage`. Access tokens stay in React state.
