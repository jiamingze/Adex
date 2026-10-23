-- One-use speech capabilities and a bounded connection lease, no audio/transcript storage.
CREATE TABLE speech_sessions (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL,
    expires_at timestamptz NOT NULL,
    active_until timestamptz NOT NULL
);
CREATE INDEX speech_sessions_owner ON speech_sessions(owner_id, active_until);
