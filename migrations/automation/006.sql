ALTER TABLE outbox DROP CONSTRAINT outbox_run_id_key;
ALTER TABLE outbox ADD COLUMN delivery_key text NOT NULL DEFAULT 'result';
ALTER TABLE outbox ADD CONSTRAINT outbox_run_delivery UNIQUE(run_id,delivery_key);
