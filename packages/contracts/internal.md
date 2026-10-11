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
