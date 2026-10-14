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
