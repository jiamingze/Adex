# Changelog

## Unreleased

- Admit qwen3.8-flash in PostgreSQL Turn model constraints (App migration 027), fixing message submission failures after the model switch; verify persistence and idempotent retries for all supported selectors.

- Default Qwen chat, memory and background execution to qwen3.8-flash; retain the legacy Max selector as a compatibility alias and MiniMax as an explicit alternative.

- Automatically browse public read-only pages across sites; drop background telemetry instead of requesting approval. Blocked Google search lookups can fall back once to authenticated search, with clearly labelled alternate sources. Sensitive actions retain independent approval.

- Update existing schedule notification rules with owner/revision checks. Tightened conditional rules also suppress older Run snapshots and failures without matching evidence; retain conversation history.

- Use a save icon in note details and tighten toolbar/title/body spacing in both reading and editing modes.

- Keep task pause/resume and delete icons together, with delete on the right on mobile and desktop.

### 2026-10-19 — Notes, reliable intervals and notification navigation

- Read notes as safe Markdown; switch to source editing and preview without losing drafts.
- Create interval checks from chat, including `每10min`; validated semantic timing fallback
  and real Automation receipts retain idempotency, occurrences and recovery.
- Suppress identical consecutive check notifications while keeping every result;
  explicitly requested recurring reports continue to notify each run.
- Open push conversations without blocking on Run lookup, fetch recent messages first,
  and reuse a bounded in-memory conversation cache cleared on session changes/deletion.
- See `docs/architecture/assistant-refinements-2026-10.md` for contracts and limitations.

### 2026-10-18 — In-chat location permission

- Replace the location modal/city entry with an inline chat card and a single “Use current location” action; retain the OS permission sheet.
- Show the question before consent, and cancel pending consent when leaving the conversation or signing out so the composer is released.

### 2026-10-18 — Text and fixture hardening

- Replace wildcard intent scans with ordered literal matching; bound schedule/media numeric fields and strip outer JSON fences without backtracking.
- Validate DNS labels individually, tokenize diagram arrows, and use direct pattern searches for artifact validation.
- Canonicalize fixture cookies and serve brand assets correctly in the synthetic gallery; add adversarial text, policy and header/asset regressions.

### 2026-10-18 — Dependency security refresh

- Update FastAPI/Starlette and pytest/pytest-asyncio to patched versions across all Python environments; regenerate reproducible locks.
- Update Vite within version 6 and Mermaid within version 12; patch vulnerable terminal regex dependencies and scope a CommonJS-compatible UUID override to the legacy Xcode parser.
- Add npm and pinned Python dependency audits to CI. Local audits report no known vulnerabilities; native Xcode parsing and signed device build remain compatible.

### 2026-10-18 — Repository reliability and community

- Fix a shared-suite reminder test that counted unrelated model invocations; assert no model invocation for the specific reminder Run, including redelivery.
- Respect configured or Linux-native Java environments; retain the Homebrew Java 21 default where present.
- Refresh immutable GitHub Action pins, add manual reruns, bounded job timeouts, concurrency cancellation and a secret scan.
- Configure grouped Dependabot updates for Actions, npm, Maven, uv and Docker, plus categorized release notes.
- Refresh the light product banner and social preview; connect bilingual READMEs to Discussions and scoped first-contribution issues.


### 2026-10-16 — Fresh-clone onboarding and project discovery

- Fix `pnpm install` / CI failing on a missing private tunnel file: iOS bundling is now explicit (`pnpm --dir apps/ios bundle`), with actionable endpoint errors and regression tests.
- Add `make demo-ui` for a synthetic, loopback-only interface tour without Java, databases, provider keys or signing.
- Reorganize both README languages around product workflows, mobile screenshots, preview versus deployment, and contribution entry points. Preserve external execution limits.
- Add bounded starter tasks, community guidelines and setup/security issue links; document the repository audit and measurement limits.
- Supply FFmpeg and Chromium OS dependencies in Linux CI; allow only exact installed Chromium paths to create sandbox namespaces while retaining the global AppArmor restriction and browser sandbox.
- Fix normal-user Ubuntu PostgreSQL startup with a private project socket directory; surface bounded CI failure context without hiding exit status. Preserve build/style/unit/integration gates.


### 2026-10-16 — In-chat website actions

- Put browser progress, secure login, actual-page takeover, frozen publication approval and verified title/link receipts in the originating chat.
- Derive login fields from actual HTTPS page controls; keep credentials out of chat, model context and checkpoints. Opt-in encrypted session profiles expire after seven days and support revocation and reuse.
- Validate credential field ownership through native browser document metadata; refuse cross-origin credential controls. Dispatch approved writes without automatic redirects or retries.
- Reuse existing Run/checkpoint/approval/effect/outbox mechanisms; no schema migration or second scheduler.
- Add explicitly labelled synthetic mobile examples and isolated login→approval→receipt/profile-reuse tests. Real Xiaohongshu/Taobao execution remains BLOCKED_EXTERNAL pending authorized external validation.


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

## 2026-10-15 — Generic browser operator

- Add controlled accessibility-based browser tasks, secure login takeover and optional encrypted profiles.
- Reuse action approvals/effects and Automation Run suspension/resumption; never replay uncertain writes.
- Add mobile browser preview/control and contract/security/integration coverage.
- Real merchant publishing, ordering and payments remain BLOCKED_EXTERNAL pending account validation.

## 2026-10-16 — Explicit conversational memory

- Save, correct, forget and inspect long-term memory through explicit chat commands.
- Commit memory changes and assistant receipts atomically under the live Turn fence.
- Preserve source provenance, revision invalidation and non-resurrection tombstones;
  ambiguous edits, disabled memory, guests and credential content do not write.
- Keep asynchronous extraction summary-only to avoid duplicate delayed writes.

## 2026-10-16 — Semantic memory and normalization

- Replace production memory command matching with model semantic assessment and rewriting.
- Learn durable preferences from normal conversation, deduplicate and correct existing facts.
- Freeze proposals by Turn; validate provenance/revisions/safety and commit learning with
  successful answers, preserving cancellation and forgetting invariants.
- Add App migration 019, scoped Agent planning endpoint, deterministic regression tests
  and separate synthetic real-provider checks.

### 2026-10-19 — Compact task cards and contextual push titles

- Keep task title/copy beside fixed pause/delete controls at phone widths; place
  status in compact metadata and hide duplicate descriptions.
- Notifications include a bounded task-title excerpt; APNs carries that title
  with a generic body, preserving conversation/Run/action routing identifiers.

### 2026-10-19 — Goals, activity and proactive feedback

- Add owner-scoped goals with editable AI plan proposals and idempotent publication
  to real todos; progress derives from those todos, archive preserves them.
- Add cached activity timeline with true Run states and original-conversation links.
- Resolve, dismiss, reopen or snooze individual suggestions with revision checks;
  closed items suppress pending notifications, and snoozed items reappear when due.
- Include bounded active-goal progress when the user asks about goals in chat.
- Filter obvious authentication-code/reset-link mail subjects from normal model metadata.
- App migration 024; existing four services, scheduler, checkpoints, approvals and
  effects remain authoritative. See Muse gap review for external/unimplemented areas.

### Unified personal assistant workspace (2026-10-20)

- Unified primary navigation: 今日 / 对话 / 任务 / 资料, retaining existing deep links.
- Grouped duplicate action reviews on Today; expanding a group opens individual reviews, never batch consent. Evening planning uses tomorrow's calendar window.
- Shared owner-scoped todo/note context and Automation-owned schedule observations in chat. Native iPhone calendar snapshots are bounded, validated, and cleared from turns after completion/cancellation; no L3 write.
- Deadline groups and compact priority labels; automation active/paused/history/execution views; notes plus private reports/files in Materials.
- Migration: App 025. External site execution and autonomous replanning remain separately gated.

### Today read recovery

- Use native HTTP for iPhone JSON GETs rather than the WebView proxy, preserving authorization/status and cancelling late results.
- Subscribe Today to shared resource updates so a recovered read clears the previous error; retain cached contents during failed refreshes and provide per-section retry.
- Allow a bounded 20-second mobile overview read for cold HTTPS connections. Writes are not retried.

### Permanent automation deletion

- The automatic-task trash button now calls a real DELETE endpoint with revision checking, instead of changing the status to CANCELLED. Confirmation explains the permanent removal.
- Physically removes the schedule/occurrences, fences pending execution and retains detached execution/effect history. Deletion tombstones prevent delayed creation retries from resurrecting schedules.
- App forwards authenticated ownership; Automation migration 008 preserves service ownership and scheduler/lease mechanisms.

### Account nicknames

- Add an optional account nickname under Settings → General. Today greetings, sidebar names and avatars use it immediately; clearing restores the login username.
- Nicknames support up to 40 Unicode code points, including Chinese and emoji. Login identifiers and ownership remain unchanged. App migration 026; authenticated, owner-scoped profile update with guest denial and input validation.

### Conditional task notifications

- Natural-language schedules can preserve an explicit notification condition separately from the work instruction. Creation receipts and task lists show the rule.
- NOT_MET, UNKNOWN and failed conditional checks still backfill the conversation without creating a notification/APNs delivery; MET requires checkpointed, cited evidence. Numeric thresholds are rechecked using decimal comparison.
- Price conditions require rendered-page evidence rather than search snippets. Missing access/data stays UNKNOWN. Existing task policies are unchanged; no new scheduler or database migration.
