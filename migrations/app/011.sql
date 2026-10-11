ALTER TABLE artifacts ADD COLUMN deleted_at timestamptz;
CREATE TABLE artifact_shares (
 token_hash text PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id),
 artifact_id uuid NOT NULL REFERENCES artifacts(id), version_id uuid NOT NULL REFERENCES artifact_versions(id),
 expires_at timestamptz NOT NULL, revoked_at timestamptz, created_at timestamptz NOT NULL DEFAULT now());
