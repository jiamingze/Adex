CREATE TABLE IF NOT EXISTS schedules (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, origin_conversation_id uuid NOT NULL,
 title text NOT NULL, instruction text NOT NULL, kind text NOT NULL CHECK(kind IN ('ONCE','INTERVAL','DAILY')),
 timezone text NOT NULL, local_time time, interval_seconds integer,
 next_fire_at timestamptz, status text NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','PAUSED','CANCELLED','COMPLETED')),
 revision bigint NOT NULL DEFAULT 1, idempotency_key text NOT NULL, request_hash text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(owner_id,idempotency_key),
 CHECK(kind <> 'INTERVAL' OR interval_seconds >= 60), CHECK(kind <> 'DAILY' OR local_time IS NOT NULL));
CREATE INDEX IF NOT EXISTS schedules_due ON schedules(next_fire_at) WHERE status='ACTIVE';
CREATE TABLE IF NOT EXISTS runs (
 id uuid PRIMARY KEY, schedule_id uuid NOT NULL REFERENCES schedules(id), owner_id uuid NOT NULL,
 origin_conversation_id uuid NOT NULL, instruction text NOT NULL, status text NOT NULL DEFAULT 'QUEUED',
 epoch bigint NOT NULL DEFAULT 0, attempt_id uuid, worker_id text, lease_until timestamptz,
 checkpoint_ref uuid, memory_revision bigint, result text, error_code text,
 attempts integer NOT NULL DEFAULT 0, max_attempts integer NOT NULL DEFAULT 5,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS runs_claim ON runs(status,created_at);
CREATE TABLE IF NOT EXISTS occurrences (
 schedule_id uuid NOT NULL REFERENCES schedules(id), scheduled_at timestamptz NOT NULL,
 run_id uuid REFERENCES runs(id), status text NOT NULL,
 PRIMARY KEY(schedule_id,scheduled_at));
CREATE TABLE IF NOT EXISTS attempts (
 id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES runs(id), epoch bigint NOT NULL,
 worker_id text NOT NULL, status text NOT NULL DEFAULT 'RUNNING',
 started_at timestamptz NOT NULL DEFAULT now(), ended_at timestamptz, UNIQUE(run_id,epoch));
CREATE TABLE IF NOT EXISTS steps (
 run_id uuid NOT NULL REFERENCES runs(id), logical_key text NOT NULL,
 checkpoint_ref uuid NOT NULL, epoch bigint NOT NULL, attempt_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(run_id,logical_key));
CREATE TABLE IF NOT EXISTS outbox (
 id uuid PRIMARY KEY, run_id uuid NOT NULL UNIQUE REFERENCES runs(id), payload jsonb NOT NULL,
 delivered_at timestamptz, attempts integer NOT NULL DEFAULT 0,
 next_attempt_at timestamptz NOT NULL DEFAULT now(), lease_until timestamptz, claim_id uuid,
 created_at timestamptz NOT NULL DEFAULT now());
