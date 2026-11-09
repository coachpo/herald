# Herald — Delivery ledger

## Direction

App-screen workflow, not a marketing page. Explored data-terminal, achromatic-ledger and framed-sheet. Selected **framed-sheet**, seed **863551341**, because a single-user inbox needs a quiet work surface and a clear list/detail hierarchy rather than dashboard metrics. No redraws.

The product face is the receipt ledger: a three-stroke forwarding mark, compact delivery-state labels and a Received → Queue → Delivered rail derived from actual per-target deliveries. No invented global totals, health claims or charts.

## Questions and priority

- Connection: can I safely open this inbox? Management token, connection feedback, session-storage explanation; appearance is accessible before authentication.
- Messages: what was received, what is still delivering, and what needs intervention? List first, selected message body and per-target evidence beside it. Send is one action away.
- Send: what will be stored, and which enabled targets will receive it? Message, routing, priority, durable receipt feedback. Receipt is never worded as delivery success.
- Targets: where will future messages go? Names, providers, enabled/default state and endpoint first; provider-specific configuration on demand.
- Connection details: how do my scripts ingest messages, and what does retention remove? Same-origin example with a literal environment-variable placeholder and an explicit cleanup confirmation.

## Tokens

IBM Plex Sans 400/500/600; IDs and code use a system monospace. Page title 22/28, section 16/24, body 14/20, meta 12/18. Tabular numeric figures.

| Semantic role | Light | Dark |
| --- | --- | --- |
| Frame | #f3f5f6 | #111111 |
| Surface | #ffffff | #181818 |
| Raised | #f4f6f8 | #232323 |
| Selected | #ebedee | #2b2b2b |
| Text | #131416 | #f0f0f0 |
| Secondary | #5d5f60 | #b4b4b4 |
| Structural border | #e8eaec | #333333 |
| Control border | #a4a9ad | #636363 |
| Received / focus | #1b6c80 | #8ac8d5 |
| Sent text / surface | #246444 / #e6f2ea | #9cd6b0 / #1b3022 |
| Failed text / surface | #a33136 / #fbeaec | #f0a5a8 / #351f22 |
| Waiting text / surface | #825b12 / #fbf2dc | #e6c987 / #30291b |

Neutral primary buttons; color lives on status and focus. No gradients, glow, glass, shadows on resting surfaces or colored icon containers. 16px work-sheet radius, 8px panels, 6px controls; 24px canvas gutter. Desktop 228px navigation plus remaining work sheet; 8px right/bottom inset. Mobile uses 16px gutters, one pane at a time and bottom navigation. Tablet folds navigation into a top band. Touch controls at least 44px.

## Implementation boundaries

Stitch Design assets are reference material, not an application scaffold. Stitch Build retrieval, visual audit and token extraction are required; its generic Tailwind, React Router and mockData prescriptions are deliberately replaced by the explicitly required existing React/TypeScript/Vite/native-CSS architecture and real API hooks. Do not add a UI framework, router, state library, or runtime fixture data. The request already authorizes local services and browser verification.

Preserve same-origin authenticated requests, session-only management token, text-only message/error rendering, omitted blank edit secrets, failed-only retry, all four providers, cursor paging, page-local failure filtering, four-second polling, ingest help and retention cleanup. Backend, API, database and deployment remain unchanged.
