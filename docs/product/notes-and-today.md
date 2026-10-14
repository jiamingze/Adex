# Notes and Today refinement (2026-10-14)

Notes replaces the navigation entry for the artifact workspace. Existing artifacts and private files remain intact and their APIs remain available; no destructive conversion. The `/workspace` deep link remains compatible.

Inspired by Apple Notes' searchable list and important-note pinning (https://support.apple.com/en-ca/guide/iphone/ipha61270292/ios), this release provides a white list/editor layout, title/body editing, pinning, explicit save, deletion confirmation and in-memory drafts across navigation. Drafts are not durable offline storage; closing the app requires saving. No artificial AI memory extraction from private notes.

App owns `notes` in migration app/017.sql. API: authenticated `GET /notes?query=...` (200 recent matches with preview, count/has_more), `POST /notes` `{id,title,content,pinned}` (client UUID allows retry without duplicate creation), `GET /notes/{id}`, `PATCH /notes/{id}` `{title,content,pinned,revision}` CAS; `DELETE /notes/{id}?revision=N` soft delete CAS. Another owner sees 404; stale revisions return 409. Title 1–200, body <=100000 characters; plain text rendered without HTML execution. PostgreSQL is authoritative, no Redis-only saves. Repeated create with same UUID returns existing note without overwriting edits; owner mismatch returns 404.

Today uses session-local per-section read caches with bounded deadlines and independent rendering. It removes artifact fetching and the recent-results section. Native calendar results are read locally and include organizer (not guessed invite sender) and location when EventKit exposes them. No new execution scheduler, service or external calendar writes.

Validation includes note CRUD/ownership/idempotent creation/CAS/delete tests against isolated PostgreSQL, client cache/deadline tests, builds, formatting/architecture/security checks. EventKit organizer visibility depends on the synced calendar/provider and permission; missing metadata is omitted.

## Daily planning calendar context fix (2026-10-14)

“Together plan today” performs a fresh bounded calendar read before creating the editable chat draft. A calendar read includes the local calendar day from midnight (not only events after now); the upcoming agenda still excludes ended events. The draft includes only events overlapping today's device-local [midnight,next midnight), including ongoing, past and all-day events, bounded to 40 entries with an explicit incomplete marker. It identifies local timezone, fixed meeting intervals and locations so planning can avoid conflicts and reserve travel time. Missing permission, failed reads, partial results and a verified empty day are distinct. Titles and locations are quoted as untrusted calendar data, never execution instructions. The draft explains that pressing Send shares the included local calendar context with the assistant; no background calendar upload or implicit calendar write. Session changes cancel draft handoff. No database migration, scheduler or API change.

## Navigation and editor refinement (2026-10-14)

Use stale-while-revalidate presentation (https://swr.vercel.app/docs/revalidation): show session-local cached projections immediately; background reads must not erase cached data or unsaved drafts. No service/state ownership change. Notes list/search and detail caches are bounded and clear on account changes; confirmed saves update the cached note and list immediately, failed/ambiguous writes retain drafts and are never automatically retried. Keep the last selected note/search in session memory. Today and Matrix retain their existing shared read caches. Native calendar access is rechecked in the background on entry; revoked permission clears the agenda on read completion. No durable offline guarantee.

The notes route must fill the remaining flex viewport between header and tab bar, with min-height:0 on containers and textarea, no vh-based minimum editor height. The tab bar stays at the bottom when the keyboard is closed and hides during editing with the keyboard open (https://developer.apple.com/design/human-interface-guidelines/tab-bars). Verify at phone widths, viewport shrink and supported keyboard event fixtures; fixtures do not prove physical iOS keyboard behavior.

Remove duplicate page headings, keep header names Today / Todo / 笔记. Meeting rows use a compact time rail, two-line title and secondary location; organizer is available in an expandable details area. No invented attendees or venue.

## Chat position preservation (2026-10-14)

Store each conversation's scroll offset and near-bottom state in session memory; clear on account changes. Returning from another tab restores the saved history offset, or follows the latest message if previously near the bottom. First load defaults to bottom. Do not record or restore against another conversation's messages or the empty loading placeholder. Streaming follows only while near bottom; manual history reading stays stationary. No message data or durable storage in this cache.

## Compact attention and 24-hour result feed (2026-10-14)

Merge attention tasks and Action Approvals into “待你处理”, maximum five rows total. UNKNOWN reconciliation and approvals precede priority-sorted open tasks; separate links expose all tasks and approvals. This is a projection only, not executing an approval. Right-aligned text+color priority labels remain readable without color perception. Labels are based on task important/urgent flags; actions get distinct confirmation/reconciliation tags. Inspiration: Todoist priority scanning (https://www.todoist.com/help/articles/set-a-priority-in-todoist-Wy82Jp), not a new task model.

“交给 Adex 的事” shows at most five newest durable notification result records from the existing deduplicated App result backfill. Include Run-linked outcomes and existing legacy result/monitor titles; exclude unrelated general notifications. Show title, a bounded plain-text summary and delivery time; click opens the original conversation. Visibility is `now-24h < created_at <= now` irrespective of read flag, deduplicated by event identity. After 24 hours it disappears from this projection but remains in notifications/history. Existing API returns at most 100 notifications; the feed is limited to those records, so it is not a complete archive. Empty/missing/unavailable states stay distinct. No database/API migration or new scheduler/notification system.

Notification read projection excludes records attached to deleted conversations so exposing results on Today does not restore deleted conversation text. This filters existing records without purging their durable delivery ledger; no migration.

## Compact page context bars (2026-10-14)

Use one route name in the top bar, followed by one compact contextual row in page content. Today: greeting/name on the left, device-local date and weekday on the right, refresh icon at the edge. Remove the decorative sun icon because there is no real weather projection; do not imply temperature or weather from a greeting icon. No new location permission or weather service. Long names truncate without pushing the date/actions outside phone width. Notes uses count + New, Matrix uses current workload + Add; other pages remove repeated route names and oversized explanatory headers. Keep authentication/welcome dialogs and task content headings intact. This is presentation only, no API/schema changes.

Bottom tab navigation disables text selection, WebKit long-press callouts and context menus within the navigation only. It preserves ordinary taps, keyboard focus and accessibility; chat/note content retains selection and copy. No touchstart cancellation or global copy suppression.

## Flat tasks and AI reply-to-note (2026-10-15)

Priority displays two separate badges: important/not important + urgent/not urgent, with all four combinations explicit. Matrix navigation now uses a flat priority-sorted list while retaining importance/urgency fields, state filters, edits and CAS semantics. No scheduling changes. Agenda shows organizer right-aligned on the time/location metadata row, without an expansion control; title attributes expose truncated text. Place recent outcome feed immediately after the agenda inside the responsive grid.

New authenticated `POST /notes/from-message` `{conversation_id,message_id}`. App validates ownership of the live conversation and assistant source message; sends only that authoritative reply to Agent `POST /internal/agent/note-compose` with scoped `note:compose` credentials. Agent invokes existing invocation ledger with stable owner/message key, prompts for faithful JSON `{title,content}`, validates length/structure, and performs no tool actions. App persists the note before returning success. App migration 018 adds owner/source-message uniqueness; retries return the same saved note. Deleted notes are not silently recreated; explicit saved copies survive source conversation deletion. A model or validation error yields failure with retry, never a fake AI success or empty note. User click authorizes this model-assisted transformation and save; ordinary replies are not copied automatically. Existing default model provider used; TEST_FIXTURE mocks are labelled and do not prove real LLM generation.

Verification commands for this change:

```sh
make test
make test-integration
make check-style
pnpm --dir apps/web build
pnpm --dir apps/ios prepare
xcodebuild -project apps/ios/ios/App/App.xcodeproj -scheme App -configuration Debug -destination 'generic/platform=iOS' -derivedDataPath .local-data/proactive-ios-device-build -allowProvisioningUpdates build
uv run python scripts/check_secrets.py
```

Observed: 21 client tests, 35 Agent tests, 32 Tools tests, Java test suites, 44 isolated integration tests and 83 OpenAPI operations validated. A separate live qwen3.8-max formatting probe used a synthetic public technical example, returned a valid note title and 663-character body, and wrote no production database records. The browser fixture model is explicitly simulated; it verifies navigation/UI, not live model execution.
