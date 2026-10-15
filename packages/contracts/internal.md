# Internal protocol v1
All requests: signed capability (iss, aud, scope, owner, resource, exp). Caller cannot widen owner/resource.

App → Agent POST /internal/agent/turns: invocation_key, owner_id, conversation_id, turn_id, context, web_search → NDJSON delta / completed(content,usage,provider) / error(code).
App → Automation /internal/automations GET/POST/PATCH: owner bound in capability, stable Idempotency-Key, origin verified by App.
Agent → App GET /internal/context/{conversation_id}: owner/resource verified, optional up_to_seq; return messages, summary, memories, memory_revision.
Agent → Automation POST /internal/runs/claim: worker_id → run, attempt_id, epoch, lease_until, checkpoint_ref.
Agent → Automation POST /internal/runs/{id}/heartbeat, /checkpoint, /complete, /fail: attempt_id, epoch; all write CAS with DB clock; checkpoint_ref must resolve at Agent with same owner/run/epoch/attempt/revision.
Automation → Agent GET /internal/checkpoints/{id}: validate immutable ref before transaction, schema/version/hash checked.
Automation → App POST /internal/results/attach: event_id, run_id, owner_id, origin_conversation_id, content, memory_revision; deduplicating consumer, append assistant + notification in one transaction. Revoked memory returns ack-discard.
Agent → Tools POST /internal/search: query → structured title/url/snippet/fetched_at; strictly read-only.

## Local files and immutable artifacts
Files accept multipart `file` and a required `Idempotency-Key` (128 chars maximum).
Repeated key with different SHA-256 returns 409. Upload limit 25 MiB, owner quota
250 MiB. Only READY objects are downloadable by their owner. Content supports
single byte ranges, private caching and attachment disposition. HTML/SVG remain
attachments, never App-origin previews. DELETE refuses files retained by versions.
Artifacts use an expected_revision CAS and retain immutable JSON source versions.

### Interactive progress (2026-10-11)
Agent NDJSON may emit `{"type":"progress","text":"正在整理资料与回答"}` before answer deltas. App persists this as `turn.progress` with turn ID under the same lease/epoch checks as text. Conversation snapshots expose optional `progress` for running turns; clients show only these bounded processing summaries, never hidden model reasoning. Native clients use WebView streaming fetch and authenticated polling fallback. Native file upload uses multipart form-data with a binary file part and the existing idempotency key.

### Explicit reply-to-note conversion
App → Agent `POST /internal/agent/note-compose`, scope `note:compose`, resource conversation UUID. Body: owner_id, conversation_id, message_id, content (authoritative App assistant reply, <=64000 chars). Response: validated JSON title (1–200 chars), content (1–100000 chars). Existing owner/message-keyed model invocation ledger is used; no tool actions or new worker/scheduler. App performs ownership checks before delegation and commits a source-message-unique note before acknowledging success. Scoped timeout 90 seconds; timeout is ambiguous and retry uses the same invocation/source key, not blind resubmission.

### Public browser read
Agent → Tools `POST /internal/browser/read`: owner-bound `search:read`, `{url, query?, max_pages?:1..3}`. Credential-free public HTTPS rendering, bounded same-host navigation, actual extracted text and source URLs/timestamps. Search snippets are not browser evidence. Invalid/private destinations fail closed; see [browser access](../../docs/architecture/browser-access.md). No DB migration or new scheduler.

### Generic browser operator

App authenticated `/browser/sessions`, `/browser/sessions/{id}` (no-store),
`/{id}/control`, `/{id}/resume`, `/{id}/close`; `/browser/accounts` and
`/browser/accounts/{id}/revoke`. Owner identity is resolved before Tools calls.
Agent uses `browser:operate` capability, scoped Run/epoch/attempt and strict
`/internal/browser/operator/ensure`, `/{session}/observe`, `/{session}/step` contracts.
Human controls use App-only `browser:control`; no model approval or arbitrary JS.
Browser requests use existing `browser.request` approvals and `action:<id>` effects.
Automation suspend validates committed `browser_waiting` checkpoint, emits waiting
outbox delivery, fences attempt; resume queues the original Run with a new epoch.
See [full contract](../../docs/architecture/browser-operator.md).

### Explicit chat memory commands

App handles explicit save/correct/forget/list user messages before Agent routing.
The existing message/Turn API and SSE `turn.completed` contract are unchanged.
Memory operation and durable assistant receipt share a live-attempt-fenced transaction.
No model-provided memory write event is accepted. Existing memory CRUD, source_refs,
tombstones, revision-aware contexts and search outbox remain authoritative. No migration.
See [command grammar and safety](../../docs/architecture/conversational-memory.md).
