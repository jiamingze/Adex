# Editing automatic schedules

PATCH /automations/{id} accepts revision and changed title/instruction, kind,
timezone, local_time, interval_seconds, first_fire_at, notification rule or status.
Owner and revision checks remain mandatory. Terminal schedules cannot be revived;
managed connector/reminder schedules cannot be rewritten as chat work. No migration.

A short transaction locks the Schedule, matching the existing scheduler claim lock.
Content-only edits preserve next_fire_at. Timing edits compute a new next occurrence:
daily in selected zone, interval from now + interval (unless explicit first_fire_at),
once at a future explicit/preserved instant. Inapplicable timing columns are cleared.
Already-created Run/occurrence/checkpoint/effect records remain immutable; edits affect
future claims only. Existing conditional-notification completion gate still applies.
No alternate scheduler, task recreation or historical result rewrite.

UI: compact pencil next to pause/delete, edit active/paused chat schedules, show saved
next execution, preserve drafts on save failure and require reopening after a revision
conflict. Notification conditions are explicit editable rules, never silently discarded.

## Observed verification — 2026-10-21

- `pnpm generate:contracts`, `make format`, `make build test check-style`: passed (App 12, Automation 5, Agent 108, Tools 132; client/contracts/architecture passed). Final iOS bundle and style/secret checks passed.
- `uv run python scripts/test_stack.py tests/integration/test_schedule_editing.py tests/integration/test_conditional_notifications.py tests/integration/test_schedule_delete.py`: **6 passed in 28.45s** against isolated PG. Includes content-only next-time retention, daily timezone calculation, interval re-anchor, invalid/past input rejection, owner/field/revision boundaries, actual scheduler claim of updated instruction, one occurrence, immutable older Run and terminal rejection. Conditional outbox and deletion regressions also passed. Fixture work is cancelled through the public API to avoid contaminating subsequent claim tests.
- Browser at 390×844: synthetic task name and time changed, saved, reopened and read back; notification condition retained. Form header/footer remain visible as its inner body scrolls. [Synthetic screenshot](../screenshots/schedule-edit-mobile.png). This UI fixture does not validate scheduling; the PG suite above does.
- Signed iOS overwrite installation and launch succeeded, preserving app data. Automation restarted; no migration or live user task mutation was needed.
