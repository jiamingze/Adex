CREATE TABLE playback_tickets (
 token_hash text PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id), file_id uuid NOT NULL REFERENCES files(id),
 session_hash text NOT NULL REFERENCES sessions(token_hash) ON DELETE CASCADE,
 expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX playback_expiry ON playback_tickets(expires_at);
