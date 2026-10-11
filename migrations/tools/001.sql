CREATE TABLE IF NOT EXISTS effects (
 owner_id uuid NOT NULL, effect_key text NOT NULL, request_hash text NOT NULL,
 tool_id text NOT NULL, state text NOT NULL CHECK(state IN ('PREPARED','IN_FLIGHT','SUCCEEDED','UNKNOWN','FAILED')),
 provider_request_id text, result jsonb, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(owner_id,effect_key));
