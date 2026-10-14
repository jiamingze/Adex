# Notes and Today refinement (2026-10-14)

Notes replaces the navigation entry for the artifact workspace. Existing artifacts and private files remain intact and their APIs remain available; no destructive conversion. The `/workspace` deep link remains compatible.

Inspired by Apple Notes' searchable list and important-note pinning (https://support.apple.com/en-ca/guide/iphone/ipha61270292/ios), this release provides a white list/editor layout, title/body editing, pinning, explicit save, deletion confirmation and in-memory drafts across navigation. Drafts are not durable offline storage; closing the app requires saving. No artificial AI memory extraction from private notes.

App owns `notes` in migration app/017.sql. API: authenticated `GET /notes?query=...` (200 recent matches with preview, count/has_more), `POST /notes` `{id,title,content,pinned}` (client UUID allows retry without duplicate creation), `GET /notes/{id}`, `PATCH /notes/{id}` `{title,content,pinned,revision}` CAS; `DELETE /notes/{id}?revision=N` soft delete CAS. Another owner sees 404; stale revisions return 409. Title 1–200, body <=100000 characters; plain text rendered without HTML execution. PostgreSQL is authoritative, no Redis-only saves. Repeated create with same UUID returns existing note without overwriting edits; owner mismatch returns 404.

Today uses session-local per-section read caches with bounded deadlines and independent rendering. It removes artifact fetching and the recent-results section. Native calendar results are read locally and include organizer (not guessed invite sender) and location when EventKit exposes them. No new execution scheduler, service or external calendar writes.

Validation includes note CRUD/ownership/idempotent creation/CAS/delete tests against isolated PostgreSQL, client cache/deadline tests, builds, formatting/architecture/security checks. EventKit organizer visibility depends on the synced calendar/provider and permission; missing metadata is omitted.
