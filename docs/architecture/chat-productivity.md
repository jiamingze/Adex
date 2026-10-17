# Chat productivity actions

Natural-language todo creation produces a validated `todo.requested` Agent event:
`draft: {title, important: boolean, urgent: boolean, due_at?: offset timestamp}`.
The App owns persistence and injects conversation/turn ownership; the model cannot
choose owner, task ID, status, execution lease or idempotency identity. Receipt is
returned only after a committed matrix row. App migration 020 adds a unique nullable
source_turn_id, preserving ordinary UI CRUD. Turn row locking/fencing before the
local insert prevents stale attempts; retry of the same turn returns its receipt.

Existing `schedule.requested` supports DAILY local_time and ONCE delay_seconds.
For relative requests the App derives first_fire_at from the durable turn timestamp,
not provider wall time or attempt time. Automation remains the sole scheduler and
uses the same chat-schedule:turn key, occurrence/lease/checkpoint/outbox machinery.
No new scheduler, worker or memory store is introduced. A receipt card distinguishes
one-shot execution time from daily recurrence. Unparseable requests ask for time
rather than claiming completion. Time zone defaults to Asia/Shanghai.

Voice hold/release submits the final recognized text once through the normal chat
send path. Slide-up/cancel, empty speech and interrupted capture do not send.
If sending becomes unavailable, retain the recognized draft instead of losing it.

Chat todo defaults (2026-10-17): omitted/null importance means important=true,
urgency means urgent=false, due_at means durable turn.created_at + 24 hours.
Explicit false/true and explicit timestamps take precedence. Defaults are App-owned
and stable across retries. Optional description is normalized by Agent and persisted
in App migration 021; manual edits omitting description preserve it. The success
reply formats title, description, actual saved deadline (Asia/Shanghai), importance,
urgency and status from the committed row, never the uncommitted model proposal.
Existing todos are not retroactively changed. No reminder is implicitly scheduled.
