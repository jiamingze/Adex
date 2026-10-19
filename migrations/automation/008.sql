-- Keep execution/effect evidence while physically removing schedule definitions.
ALTER TABLE runs DROP CONSTRAINT runs_schedule_id_fkey;
ALTER TABLE runs ADD CONSTRAINT runs_schedule_id_fkey FOREIGN KEY(schedule_id) REFERENCES schedules(id) ON DELETE SET NULL;
ALTER TABLE occurrences DROP CONSTRAINT occurrences_schedule_id_fkey;
ALTER TABLE occurrences ADD CONSTRAINT occurrences_schedule_id_fkey FOREIGN KEY(schedule_id) REFERENCES schedules(id) ON DELETE CASCADE;
CREATE TABLE deleted_schedules (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, idempotency_key text NOT NULL,
 deleted_at timestamptz NOT NULL DEFAULT now(), UNIQUE(owner_id,idempotency_key)
);
