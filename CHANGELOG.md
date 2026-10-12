# Changelog

## Unreleased

### 2026-10-13 — Proactive assistant foundation

- Add Google Calendar/Gmail connector adapters, session-bound PKCE OAuth, AES-GCM credentials, incremental scopes, refresh and revocation.
- Extend the existing approvals/effects for calendar update and Gmail send, immutable confirmation hashes, ETag/readback checks and UNKNOWN reconciliation.
- Add Connector sync/action Run kinds and recurring connector templates on the existing scheduler, leases/checkpoints/outbox.
- Add proactive signal dedupe/correlation/importance, quiet hours, notification preferences and a four-quadrant task board.
- Add APNs HTTP/2 provider transport, encrypted device tokens, delivery ledger and authenticated notification-to-conversation/Run/action restoration.
- Add Web/iOS assistant interfaces and native notification bridge. Google consent starts on Web in this version.
- External validation remains BLOCKED_EXTERNAL without real Google/APNs configuration; fixture tests are explicitly labelled, not real delivery evidence.


- Allow vertical chat scrolling from iOS Markdown tables while retaining horizontal table scrolling.
- Welcome contributors with bilingual participation steps and project entry points.

- Add IntelliJ IDEA/PyCharm service launch configurations, local JVM attach debugging, scoped environment generation and bilingual IDE guides.

- Collapse chat source/evidence cards by default, with source counts, concise excerpts and a bounded detail list on Web and iOS.

Initial public repository packaging. The code predates the first Git commit; dates in implementation evidence describe development checks, not tagged releases.

- Shared React Web and Capacitor iOS client, guest access and account registration.
- Qwen/MiniMax selection, automatic Tavily search, Markdown and streamed responses.
- Service-owned PostgreSQL schemas, three-layer memory and durable task recovery mechanisms.
- Schedules, background research/creative tasks, private file storage and artifact versions.
- Media provider adapters, playback, sandboxed games and editable diagrams.
- Inline chat failures, bounded upload retries and first-message history titles.
- English/Chinese project, architecture, configuration, installation and development guides.
