CREATE TABLE connector_connections (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, service text NOT NULL CHECK(service IN ('calendar','gmail')),
 status text NOT NULL CHECK(status IN ('ACTIVE','REVOKE_PENDING','REVOKED','REAUTH_REQUIRED')),
 scopes jsonb NOT NULL, credentials text, revision bigint NOT NULL DEFAULT 1,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX connector_owner ON connector_connections(owner_id);
CREATE TABLE connector_oauth_states (
 state_hash text PRIMARY KEY, owner_id uuid NOT NULL, session_binding text NOT NULL,
 service text NOT NULL, scopes jsonb NOT NULL, verifier_cipher text NOT NULL,
 expires_at timestamptz NOT NULL, consumed_at timestamptz);
ALTER TABLE approvals ADD COLUMN kind text NOT NULL DEFAULT 'calendar.create';
ALTER TABLE approvals ADD COLUMN connection_id uuid REFERENCES connector_connections(id);
ALTER TABLE approvals ADD COLUMN run_id uuid;
CREATE UNIQUE INDEX approval_run ON approvals(run_id) WHERE run_id IS NOT NULL;
CREATE TABLE connector_sync_receipts (
 owner_id uuid NOT NULL, run_id uuid NOT NULL, connection_id uuid NOT NULL REFERENCES connector_connections(id),
 result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(owner_id,run_id));
