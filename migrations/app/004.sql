CREATE TABLE files (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id), object_id uuid NOT NULL UNIQUE,
 idempotency_key text NOT NULL, name text NOT NULL, mime_type text NOT NULL,
 size_bytes bigint NOT NULL CHECK(size_bytes>=0), sha256 text NOT NULL,
 status text NOT NULL CHECK(status IN ('PENDING','READY','DELETED')),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(owner_id,idempotency_key));
CREATE INDEX files_owner ON files(owner_id,created_at DESC);
CREATE TABLE artifacts (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id), kind text NOT NULL,
 title text NOT NULL, revision bigint NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE artifact_versions (
 id uuid PRIMARY KEY, artifact_id uuid NOT NULL REFERENCES artifacts(id), revision bigint NOT NULL,
 source jsonb NOT NULL, file_id uuid REFERENCES files(id), sha256 text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(artifact_id,revision));
CREATE FUNCTION immutable_artifact_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Artifact versions are immutable'; END $$;
CREATE TRIGGER artifact_version_immutable BEFORE UPDATE OR DELETE ON artifact_versions
FOR EACH ROW EXECUTE FUNCTION immutable_artifact_version();
