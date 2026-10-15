# Changelog

## Unreleased

- Extend the server-side Chromium reader from GitHub-only to public HTTPS pages, bounded same-host links and direct URL/follow-up chat routing.
- Add per-run public-DNS-pinned CONNECT egress, read-only resource controls, explicit failure diagnostics and a live public-browser verification command; preserve existing retrieval quota and evidence persistence.

- Fix Today card spacing on mobile/desktop and use a task-list icon for attention items.
- Move the reply-to-note action after Copy, using an accessible icon with pending feedback.
- Open confirmed cached notes immediately without a blocking detail fetch; fence stale opens when switching notes.
- Add long-press/right-click/Shift+F10 note actions for pinning and confirmed deletion; preserve unsaved text when pinning.

- Repair temporary public access with configurable HTTP/2/IPv4 tunnel transport; rebuild and verify the iOS bundled endpoint.
- Verify signed iPhone build, installation and launch after development certificate repair (real APNs still requires separate acceptance).

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

### Task matrix refresh — 2026-10-13

- Redesigned shared Web/iOS matrix with subdued quadrant colors, compact rows,
  progress counts, search, completion filters and due-date sorting.
- Added per-quadrant quick add and an accessible task editor for titles,
  deadlines and moving tasks; deletion now has explicit confirmation.
- Mobile quadrant focus and local-time deadlines; existing persistence and
  revision contracts preserved.

### Personal assistant experience — 2026-10-13

- Added Today: owner-scoped daily focus, upcoming automations, approval attention,
  proactive observations, background Runs and recent artifacts, with independent
  failure states. Daily planning prepares a visible editable chat draft using
  bounded task/schedule snapshots; it never automatically calls a model or executes.
- Grouped navigation and mobile non-chat tabs, fixed page deep links/history,
  consistent light/dark surfaces and account-aware onboarding.
- Split assistant settings into suggestions, approvals, connectors and preferences;
  create the origin conversation on demand and preserve explicit action approval.
- Settings links now reach memory, service connections and quiet hours directly.
  Guest local appearance settings do not make authenticated account requests.
- Added six client regressions and a loopback-only synthetic UI fixture.
  Google/APNs/booking/health/device-control external boundaries are unchanged.

### White canvas and persistent navigation — 2026-10-13

- Restore the original white light theme and neutral gray surfaces.
- Keep the mobile bottom navigation on chat as well as Today and other pages;
  hide it for the software keyboard and restore it on dismissal, with a header
  Today shortcut still available. Switching pages retains the unsent draft.
- Reduce Today's hero/summary height so actionable work appears earlier.
- Refresh synthetic preview screenshots; keyboard event-contract smoke is distinct
  from physical-device keyboard acceptance.

### Matrix loading reliability — 2026-10-14

- Bound task reads to eight seconds, show a recoverable timeout and lightweight
  initial placeholder instead of waiting indefinitely.
- Share a short-lived session-only task snapshot between Today and Matrix;
  revalidation preserves visible tasks and concurrent reads are deduplicated.
- Clear private snapshots on authentication changes, reject late old-session data,
  and invalidate reads after confirmed matrix mutations from every UI entry point.
- Add four client regressions; no changes to durable state or write retry behavior.
