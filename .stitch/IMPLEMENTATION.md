# Herald UI redesign — implementation and acceptance

## Design provenance

- Stitch project: https://stitch.withgoogle.com/projects/5701621175042394082
- Light design system: `assets/18024183445211519821`; dark counterpart: `assets/7680595233516220540`. Both carry the shared semantic roles and calibrated light/dark values in `DESIGN.md`.
- Final reference screens: inbox `05eb3fada3c74454b1cb4a3437efbccf`, send `cf6f157427b74ff8a8b101774790a5f5`, targets `5375331c01434638bc460a6f3000f7d6`, mobile detail `bea40552093b4b95b242eaf1ada6f6d3`, mobile inbox `22c16d97b45045bbb434ece7d07891a9`, simplified login `b2bf5f82e479410391e9c8d396635822`. Original exploration screens are retained as design references only.
- Used Stitch Design's real create/update design-system, generation and targeted-edit calls. Used Stitch Build's real `get_screen` retrieval for every generated screen, authenticated `download_file`, screenshot audits, HTML-head token extraction and its SWC component validator. The bundled `fetch-stitch.sh` was attempted but received HTTP 401; the current MCP explicitly requires `download_file` for those authenticated URLs.
- `resources/style-guide.json` contains tokens extracted from this project's downloaded HTML. `metadata.json` is mirrored in `frontend/.stitch/metadata.json`. Canvas positions were not returned by `get_project`, so they are recorded as unavailable, not invented.
- The app-screen draw explored data-terminal, achromatic-ledger and framed-sheet. Selected framed-sheet, seed **863551341**, with no redraw. The face is the forwarding mark and the signature is the real receipt/queue/delivery rail, not a chart or KPI grid.

Stitch output was adapted, not copied as an application. Generated Telegram/fallback behavior, latency, queue IDs, fabricated token formats, version labels, daemon health and message-size constraints were rejected or corrected. No generated fixture data, Tailwind, router, state library or additional UI framework enters the application.

## Preserved capability inventory

| Job | Delivered UI and contract |
| --- | --- |
| Connect / disconnect | Management token validation, session restore, same-token retry, 401 disconnect, masked/showable entry, sessionStorage only |
| Send | Optional title, required plain-text body, priority 1–5, all enabled defaults or explicit enabled targets; receipt ID and queue feedback |
| Browse | Four-second refresh, manual refresh, latest/older cursor paging with 50-message pages; page-local failed filter and honest visible counts |
| Inspect | Full body/title, receipt time, priority and ID; target-name snapshots, all five delivery states, cumulative attempts, completion/next-retry times and text errors |
| Recover | Manual retry only for terminal `failed`; no sent replay; receipt, queued and delivered remain distinct |
| Configure Bark | Name, server URL, device key, enabled/default |
| Configure ntfy | Name, server URL, topic, optional access token, enabled/default |
| Configure MQTT | Name, broker host/port, publish topic, optional username/paired password, QoS 0/1/2, TLS, retain, enabled/default |
| Configure Gotify | Name, server URL, application token, enabled/default |
| Manage targets | Create/edit, fixed provider on edit, blank secrets omitted to retain stored values, direct enabled toggle, confirmed deletion with server errors preserved |
| Operate | Same-origin ingest instructions with literal environment-variable placeholder; confirmed cleanup of sufficiently old fully delivered history; unfinished/failed history retained |

The desktop uses a master/detail ledger; phone/tablet use one pane with a return action and restored list focus/scroll. Mobile detail removes list-only chrome so the failure and retry are visible sooner. Forms use labeled native controls; dialogs explicitly wrap Tab/Shift+Tab, prevent dismissal while submitting and restore focus. All controls support keyboard use and reduced motion. Fonts are local IBM Plex Sans assets with the upstream OFL license; runtime requires no font CDN.

## Validation performed

All browser writes used synthetic fixtures, with outbound requests blocked. No real backend data, credentials or notification suppliers were used. Production assets from `frontend/dist` were previewed locally; a separate ignored test-only gateway supplied fixtures for the skill inspector. Neither fixtures nor the gateway is imported by the app or included in its build.

- `corepack pnpm@10.30.1 --dir frontend lint` — passed.
- `corepack pnpm@10.30.1 --dir frontend build` — passed.
- `python3 scripts/sync_version.py --check` — passed, version 1.0.0.
- `git diff --check` — passed.
- Stitch Build SWC validator — all seven reusable component files passed after temporary, non-project validator dependency setup.
- Functional browser suite — **36/36 passed**, 18 scenarios at each of 1440px and 390px. Includes authentication, session recovery and stale-session responses; routing, send failures and receipt/detail; polling/filter/paging; all four provider create/edit and retained secrets; enable/default/delete; cleanup; loading/empty/error states; text rendering; keyboard/focus and busy dialogs.
- Visual suite — **42 screenshots**, seven screens at 390px, 768px and 1440px in both themes; no horizontal overflow. Theme system-following, OS change, manual override, refresh restoration and reset were verified.
- Long-content suite — six width/theme combinations passed for long titles, message bodies, destination names/endpoints and error text, including HTML-like content rendered as text.
- `design-taste-frontend/scripts/lint.mjs --app frontend/src frontend/index.html` — **0 FAIL**. Its em-dash warning is retained only for numeric select-option delimiters, not decorative prose.
- `design-taste-frontend/scripts/inspect.mjs --app` on the production-asset fixture gateway — **0 FAIL** for light/dark inbox, light detail, light/dark send, light/dark targets, light/dark login and dark connection at all three required widths. Remaining heuristic whitespace warnings are intentional: login stays a narrow token form rather than filling space with decoration; target/connection workspace sheets fill the viewport, while their actual rows/sections remain content-sized. No rule was disabled with an allow flag.

Screenshots were inspected and fixes included tablet-login header overlap, navigation hover contrast, mobile text density, dialog focus containment, and removal of list controls from mobile detail. Detailed test scripts, reports, baseline screenshots, final screenshots and inspector contact sheets are in the ignored `.evidence/ui-redesign/` directory.

## Limits

Browser testing used desktop Chromium/Edge with responsive viewports, not physical phones, Safari or Firefox. Real provider dispatch was deliberately not exercised. Backend/API/database/deployment code and package dependencies remain unchanged. No commit, push, release, deployment or publication was performed.
