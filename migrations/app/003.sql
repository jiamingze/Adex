CREATE TABLE IF NOT EXISTS schedule_drafts (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id),
 conversation_id uuid NOT NULL REFERENCES conversations(id), request_hash text NOT NULL,
 request jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
