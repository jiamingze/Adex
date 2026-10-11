CREATE TABLE IF NOT EXISTS invocations (
 invocation_key text PRIMARY KEY, owner_id uuid NOT NULL, request_hash text NOT NULL,
 state text NOT NULL CHECK(state IN ('PREPARED','DISPATCHED','COMPLETED','UNKNOWN','FAILED')),
 result jsonb, provider text NOT NULL, model text NOT NULL, usage jsonb,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS checkpoints (
 id uuid PRIMARY KEY, run_id uuid NOT NULL, owner_id uuid NOT NULL, epoch bigint NOT NULL,
 attempt_id uuid NOT NULL, logical_key text NOT NULL, memory_revision bigint NOT NULL,
 schema_version integer NOT NULL CHECK(schema_version=1), state jsonb NOT NULL,
 sha256 text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(run_id,epoch,logical_key));
CREATE OR REPLACE FUNCTION forbid_checkpoint_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'checkpoints are immutable'; END $$;
DROP TRIGGER IF EXISTS checkpoints_immutable ON checkpoints;
CREATE TRIGGER checkpoints_immutable BEFORE UPDATE OR DELETE ON checkpoints
FOR EACH ROW EXECUTE FUNCTION forbid_checkpoint_mutation();

ALTER TABLE invocations ADD COLUMN IF NOT EXISTS attempt_id uuid;
ALTER TABLE invocations ADD COLUMN IF NOT EXISTS lease_until timestamptz;
