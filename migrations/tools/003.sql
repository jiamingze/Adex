CREATE TABLE approvals (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, request jsonb NOT NULL, request_hash text NOT NULL,
 state text NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','APPROVED','REVOKED','SUCCEEDED','UNKNOWN')),
 expires_at timestamptz NOT NULL DEFAULT now()+interval '15 minutes',
 created_at timestamptz NOT NULL DEFAULT now(), result jsonb);
