CREATE TABLE matrix_reminder_inboxes (
 owner_id uuid PRIMARY KEY REFERENCES users(id), conversation_id uuid NOT NULL REFERENCES conversations(id)
);
CREATE TABLE matrix_reminders (
 id uuid PRIMARY KEY, task_id uuid NOT NULL REFERENCES matrix_tasks(id) ON DELETE CASCADE,
 owner_id uuid NOT NULL REFERENCES users(id), due_at timestamptz NOT NULL,
 conversation_id uuid REFERENCES conversations(id), created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(task_id,due_at)
);
ALTER TABLE notifications ADD COLUMN matrix_reminder_id uuid;
-- Backfill future existing important todos through the same outbox path.
INSERT INTO matrix_reminders(id,task_id,owner_id,due_at,conversation_id)
 SELECT gen_random_uuid(),id,owner_id,due_at,conversation_id FROM matrix_tasks
 WHERE important AND status='TODO' AND due_at>now();
INSERT INTO outbox(id,kind,resource_id)
 SELECT gen_random_uuid(),'matrix.reminder',id FROM matrix_reminders ON CONFLICT DO NOTHING;
