ALTER TABLE runs ALTER COLUMN schedule_id DROP NOT NULL;
ALTER TABLE runs ADD COLUMN kind text NOT NULL DEFAULT 'CHAT';
ALTER TABLE runs ADD COLUMN request jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE runs ADD COLUMN idempotency_key text;
ALTER TABLE runs ADD COLUMN request_hash text;
CREATE UNIQUE INDEX run_request_unique ON runs(owner_id,idempotency_key) WHERE idempotency_key IS NOT NULL;
