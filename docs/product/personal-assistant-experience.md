# Personal assistant experience / 个人助手体验

## Scope and references — 2026-10-13

User confirmed Meta Muse. Read official [Today AI](https://today.ai/),
[Meta Muse](https://ai.meta.com/muse/) and [Muse productivity](https://ai.meta.com/muse/productivity/).
Public marketing/walkthroughs inform the design; we did not inspect authenticated
clients or establish parity with their implementation.

Today emphasizes a daily view, user-controlled memory and timely proactive help.
Muse emphasizes handing off work, connected accounts, background progress and human
approval. Adex should surface the same useful journey using its existing state.

## Actual gaps and implementation plan

| Gap in Adex | This change | Further work / external boundary |
| --- | --- | --- |
| Chat-only landing, no day overview | Today page: priority/due tasks, next schedules, pending approvals, suggestions, active Runs and recent artifacts | Rich daily brief over real calendar/mail requires configured OAuth |
| Eight flat navigation items, inconsistent active states | Grouped sidebar, persistent mobile tab bar; preserve a compact chat composer | No new navigation framework or business domain |
| Deep links reset to chat; browser back ignores matrix/assistant | Shared route parser and page path contract, tested history restoration | Native notification restore still server-authorized |
| Assistant is one long configuration form | Separate suggestions, approvals, connected services and preferences; compact status/empty states | Google and APNs remain BLOCKED_EXTERNAL until real configuration/acceptance |
| Manual configuration needs a pre-existing conversation | App creates a scoped conversation on demand for approved workflows | No writes to external services without explicit approval |
| Background Runs obscure status, results and pending decisions | Daily work cards with status and origin-conversation links | UNKNOWN remains unknown; no auto retry or invented completion |
| Presentation varies between pages | Shared surface tokens, typography, input/touch states and responsive layout | Test Web, narrow viewport, theme and signed iOS build |
| No unified goal/project domain | Explicit roadmap only | Define goal/task/artifact links + migration and acceptance before implementing |
| Limited connectors and travel transactions | Existing Calendar/Gmail connection UI and capability boundaries | Notes/cloud files, real booking quotes, purchases and cross-device execution need separate contracts and approvals |
| No personal health context or community skill marketplace | No placeholder buttons or fake health metrics | Consent/provenance for health; trusted skill review/sandbox/versioning before third-party skills |

## Contracts and migrations

No database migration or new server endpoint. All data is owner-scoped through
existing App APIs. Today uses GET /matrix, /automations, /tasks, /actions, /signals,
/artifacts and /connectors, independently; failed sections retain their own error
and never display an invented zero. Guest onboarding skips registered-only reads.
Complete-task uses the existing PATCH /matrix/{id} revision check. Opening work
uses the server-returned origin conversation ID. Suggestions and action approvals
route to the existing AssistantHub; the daily page cannot approve external writes.

Routes: `/today`, `/`, `/c/{conversation_id}`, `/matrix`, `/tasks`, `/workspace`,
`/memory`, `/assistant`, `/tools`, `/settings`. Legacy `/` stays chat for saved links.
The daily view is a client projection, not a second task state or scheduler.
UI refresh runs only while visible, aborts/ignores stale completion on unmount and
cannot execute workflows. Native offline work remains Automation-owned.

## Verification plan

First write route/date/priority projection tests, then components and shell changes.
Run client tests, TypeScript/Vite, formatting/architecture and secret checks.
Browser smoke: Today guest state, responsive/mobile navigation, history/deep links,
assistant tabs and editing, keyboard focus, light/dark themes. Registered behavior
must use isolated fixture data, never mutate personal data as a development test.
Update READMEs/changelog/status and install the signed shared UI build if the
previously authorized connected phone is available; push only verified source/docs.

## Delivered and observed verification

The daily overview and contextual planning draft, grouped navigation, persistent
mobile tabs, assistant sections and settings shortcuts are implemented. Planning
copies only bounded task/schedule data into a visible editable composer; it does
not send to an LLM until the user sends. Partial reads show unknown/error, not zero.
Read-only connections cannot submit write drafts; revoked connections cannot open operation controls. External operation
approval and provider receipt requirements remain enforced by the existing backend.

Commands observed on 2026-10-13:

- `pnpm --dir apps/web build`: TypeScript + Vite pass; existing large Mermaid
  chunk warnings remain (not resolved by this design change).
- `make test`: 6 client + Java 7 + Agent 33 + Tools 32 tests pass; OpenAPI 77
  operations validated. `make test-integration`: 39 pass in 70.12 seconds using
  isolated databases/fixture providers, no real Google/APNs execution.
- `make test-client check-style`: client tests, Spotless, Ruff format and
  architecture checks pass; Prettier check, secret scan and `git diff --check` pass.
- Browser smoke using `python3 tests/fixtures/experience_server.py` after a web
  build: completion persisted in fixture memory; attention card opens approval
  tab; unconfigured connectors disabled; planning fills composer without an API
  write/model call; page reload/history restored; injected approval HTTP 503
  leaves other sections usable and the counter unknown.
- 375×812 browser: document width 375, tab bar 61px; light/dark screenshots
  contain synthetic TEST_FIXTURE data only. 1280 desktop layout inspected. The
  fixture server was stopped after testing; it binds loopback and has no real data.
- `pnpm --dir apps/ios prepare`, signed `xcodebuild ... build` and strict/deep
  codesign verification passed; devicectl installed and launched io.adex.personal.
  Public `/today` returned HTTP 200. These prove packaging/installation, not
  physical keyboard/voice/APNs interaction acceptance.

No new external capability, schema, provider credential or scheduling system was
introduced. Goal/project persistence and the additional integrations listed above
remain explicit follow-up work, not hidden claims of Muse/Today parity.

## White style and persistent navigation follow-up

User feedback restored the light canvas to pure white with neutral gray accents.
Today now uses a smaller date/title, a compact planning strip and inline counts,
putting actionable tasks nearer the top. Mobile navigation stays available on chat
and all page views; native keyboard events hide it while typing and restore it
after dismissal. Mobile Web detects editable-field viewport shrinkage instead of
hiding on focus alone, preserving hardware-keyboard navigation. The header Today
shortcut remains available while the bottom bar is hidden.

Observed: six client regressions pass; `make check-style`, Web/TypeScript and signed
iOS builds pass. In the 375×812 fixture browser, canvas RGB is 255/255/255, document
width is 375, and the task area starts at y≈364. Chat→Today→Chat retains the draft.
TEST_FIXTURE keyboard events hide/restore the bottom bar; this event-contract
check is not a physical software-keyboard measurement. Light/dark public fixture
screenshots refreshed. Signed app reinstalled on the connected phone.

## Matrix read reliability — 2026-10-14

The matrix previously remounted with an empty list and an unbounded fetch on each
navigation. Added a shared, session-local read projection for Today/Matrix, an
8-second read deadline (also bounds transports that ignore AbortSignal), in-flight
deduplication and a 15-second freshness window. Revalidation keeps the prior list
visible; initial loading uses a lightweight skeleton. A failed first read shows
unknown counts and an explicit retry instead of an invented empty task list.

Login/logout/session expiry clears the in-memory projection and invalidates old
read attempts; late responses cannot repopulate another session's cache. An old
session's late HTTP 401 cannot reset a newer login. Confirmed matrix writes clear
freshness through the shared API adapter, including task additions from suggestions.
Reads after mutations still come from the owner-scoped App API. No localStorage,
DB migration, new endpoint, scheduler, write retry or durable task state is added.

Observed checks: `make test-client check-style` (10 client tests, Spotless/Ruff and
architecture pass), Web TypeScript/Vite build and signed iOS build pass, secret
scan and diff checks pass. Explicit UI fixture delays GET /matrix by 12 seconds:
the client exits waiting and offers retry at its deadline. A normal matrix→chat→
matrix switch shows three fixture task rows with zero loading placeholders, even
when background revalidation is running. Tests cover a permanently hung read,
concurrent deduplication, snapshot reuse, session reset/late response and retry.
These fixture checks do not establish actual iPhone network latency.

## Upcoming calendar agenda contract — 2026-10-14

Requested: show real calendar meetings in Today / Upcoming; automatic schedules
must remain labelled separately. Calendar source is being clarified (existing
Google connector vs iPhone EventKit). The common display uses explicit-offset
instants, nominal all-day dates with exclusive end, ongoing/upcoming filtering,
sorting, cancelled-event exclusion and invalid-data reporting. No guessed dates
or meeting inventory. Calendar reads do not confer external write approval.

For the existing Google source, reuse authenticated POST /connectors/{id}/query
with a now→seven-day interval and the primary calendar. It expands recurring
instances; paginated/truncated results must be labelled partial, not exhaustive.
No database migration or second scheduler is needed for a read-only display.
Missing configuration/consent remains BLOCKED_EXTERNAL. Native EventKit, if selected,
requires an explicit in-app permission action and real device acceptance; a fixture
can only verify presentation and cannot stand in for personal calendar access.

Implemented: Today reads the first ACTIVE Google Calendar connection through the existing owner-scoped App Connector query API. The seven-day agenda is independent of task loading, bounded to eight seconds, and cached in memory for thirty seconds with session-change reset. Refresh retries failed reads. Upcoming meetings (maximum five), ongoing and all-day events are separate from automatic schedules. Missing configuration is shown as BLOCKED_EXTERNAL; a connection entry opens existing OAuth management. Partial results and malformed dates are labelled. No migrations or API changes are required. iPhone system-calendar access is not implemented by this change; it requires a separate explicit EventKit permission flow. Real personal-calendar acceptance remains BLOCKED_EXTERNAL until a working authorized Google connection is available.


### iPhone calendar source — 2026-10-14

User clarified that the source is the iPhone system calendar, including calendars already synced to that device. Native Today now prioritizes EventKit, never Google or the server for this agenda. Bridge contract: `AdexCalendar.read()` returns `{permission: GRANTED|NEEDS_PERMISSION|DENIED, events: CalendarEvent[], partial: boolean}`; it does not prompt. `request()` is only called by the explicit calendar-permission button. EventKit requires iOS 17 full-access authorization for reads; usage text explains the broad OS permission while the bridge exposes no writes. Denied access points to iPhone settings. Reads expand recurring instances over seven days across all synced calendars, cap at 200, return only title/id/start/end, and never upload or persist meetings. Refresh on foreground rechecks permission and clears the snapshot first. Web retains existing Google Connector support and cannot access an iPhone's local calendar. No database migration or service/API changes. Physical-device consent and real calendar display require device acceptance; compiler/unit tests alone do not prove it.
