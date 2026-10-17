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

### Semantic conversational memory

App → Agent POST `/internal/agent/memory-plan`, `memory:plan` scoped to owner/Turn.
Strict request `{owner_id,turn_id,snapshot,model}`; response mode none/learn/manage,
up to three normalized operations with evidence, confidence, category and target
ID/revision. App 019 freezes input/proposal/receipt by Turn; App alone validates and
commits. Management receipts commit atomically; learning commits only with a completed
normal answer. Existing public message/SSE contracts are unchanged. No raw-text fallback,
keyword production router, new scheduler or model-authorized write.
See [design and limits](../../docs/architecture/conversational-memory.md).

### Important todo reminders

App's durable `matrix.reminder` outbox bridge creates an Automation ONCE schedule
with task_kind=MATRIX_REMINDER and task_request={matrix_reminder_id: UUID}.
first_fire_at=max(reminder.created_at, due_at-10 minutes); late bridge retries may
retain this past timestamp for catch-up. Only this internal template permits it.
Normal public scheduling cannot supply task_kind/task_request. Automatic reminders
are excluded from user automation listings and manual schedule quota accounting.

The existing leased Agent worker checkpoints a deterministic result with artifact
{matrix_reminder_id: UUID}; no model invocation is needed. Existing Automation
completion/outbox delivery calls App result:attach. App revalidates owner,
conversation, current important/TODO/deadline and time window before notification.
Obsolete deliveries are acknowledged without a visible message or notification.
APNs dispatch independently rechecks current eligibility. Notification run_id and
conversation_id continue to use the existing authenticated resume contract.


### Browser research and transport reliability

BrowserStep adds `key` only for `text: "Enter"` with a current, unprotected search
textbox/searchbox/combobox handle. Arbitrary keys, JavaScript, model approval and
credential input remain forbidden. The resulting network request still uses the
existing approval/effect gate. Snapshot text/link/control budgets are independent,
so long feeds do not hide late search and login controls.

Read-only non-navigation GET/HEAD subresources may use the same registrable site
as an explicitly authorized read host (bundled PSL including private suffixes).
Every host still passes public DNS validation and IP pinning. Different sites,
navigation to an ungranted host and mutating requests retain their approval rules.
Unsolicited telemetry is denied, never granted as a side effect.

Snapshots add bounded `network` diagnostics: route/channel/document_status/failures.
Research results add `artifact.research_evidence`, at most ten observations with
source URL/title/observation_id/observed_at/visible_text, persisted in the existing
immutable checkpoint before the Automation reference commit. Evidence is untrusted
page text, not a verified offer or a business execution receipt. No new migration.


### Browser CONNECT recovery and read redirects

`ADEX_BROWSER_DIRECT_FALLBACK=1` explicitly permits a failed local proxy CONNECT
to fall back to a direct socket to the same previously validated public IP:443.
Default is disabled. Recovery happens before returning CONNECT 200 and before TLS
or HTTP bytes; it never retries a dispatched operation, resolves alternative DNS,
or changes a write approval. Both isolated browser runners receive this setting.

For GET/HEAD navigation, fetch the first response with redirects/retries disabled.
A same-site HTTPS Location (private PSL aware) is validated and pinned before the
browser follows it, because Chromium may skip route interception on redirects.
This narrowly extends the website read scope to its same-site navigation redirect.
It does not grant arbitrary cross-site reads or authorize any POST redirect.
Website verification pages remain BLOCKED_EXTERNAL pending actual completion.

### Live speech transcript

iOS AdexSpeech emits `partial {session_id,text}` from actual recognition results
after checking the active plugin call. Web subscribes before starting capture,
accepts only the current gesture ID, and removes the listener after settlement.
Web SpeechRecognition interim results use the same preview callback. The transcript
is transient panel state; partial results do not send messages. Release sends the
final transcript once; cancellation/unmount never sends it. No server API/schema
or new database migration is introduced.
