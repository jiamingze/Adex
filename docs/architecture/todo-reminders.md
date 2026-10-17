# Important todo deadline reminders

Important TODO items with a future deadline notify ten minutes before due. If
created inside the ten-minute window, enqueue immediate catch-up. Completed,
unimportant, deleted, or rescheduled items suppress obsolete notifications.
Existing notification preferences and APNs permissions remain authoritative.

App migration 022 stores immutable (task, due_at) reminder identities and publishes
`matrix.reminder` through its existing durable outbox, in the task transaction.
Automation migration 007 permits MATRIX_REMINDER on existing ONCE schedules.
The bridge retries idempotently without holding database locks over HTTP. Existing
Scheduler/occurrence/lease/fencing/checkpoint/outbox remain the only execution path.
The Agent worker performs a deterministic reminder result (no LLM call); App
revalidates the current todo at result consumption and before APNs dispatch.
Notification content uses actual task/deadline and links the source conversation,
or an owner-scoped reminder inbox for manually created todos without a conversation.
No UI/API endpoint is added; internal result artifact carries matrix_reminder_id.

Uniqueness is task+deadline, so title edits and replay do not duplicate reminders.
Changed deadlines create a new version; old versions become no-ops. Once Apple has
accepted a push it cannot be recalled. Server downtime/network/iOS settings can delay
or prevent display; catch-up does not claim an exact physical delivery guarantee.

Concurrency: task edits lock old/new conversation references in sorted order before
the todo row, matching result consumption (conversation -> todo). Reminder/outbox
inserts stay in that short local transaction; schedule HTTP calls run after the
publisher claim transaction commits. Publication retries preserve immutable timing
and identity; no database lock is held during remote scheduling or execution.
