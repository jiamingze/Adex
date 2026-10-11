CREATE TABLE media_jobs (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, request_key text NOT NULL, request_hash text NOT NULL,
 kind text NOT NULL, provider text NOT NULL, status text NOT NULL,
 request jsonb NOT NULL, result jsonb, created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(owner_id,request_key));
CREATE TABLE provider_events (
 provider text NOT NULL, event_id text NOT NULL, job_id uuid NOT NULL REFERENCES media_jobs(id),
 version bigint NOT NULL, signature_verified boolean NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(provider,event_id));
