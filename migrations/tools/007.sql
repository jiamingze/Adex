CREATE TABLE browser_sessions (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, run_id uuid NOT NULL UNIQUE,
 conversation_id uuid NOT NULL, status text NOT NULL DEFAULT 'AGENT'
 CHECK(status IN ('AGENT','HUMAN','WAITING_APPROVAL','UNKNOWN','CLOSED','LOST')),
 runtime_id text, origin_url text NOT NULL, current_url text NOT NULL,
 revision bigint NOT NULL DEFAULT 1, snapshot jsonb NOT NULL DEFAULT '{}',
 storage_cipher text, pending_cipher text, action_id uuid REFERENCES approvals(id),
 active_command uuid, command_until timestamptz, steps integer NOT NULL DEFAULT 0,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX browser_sessions_owner ON browser_sessions(owner_id,updated_at DESC);
CREATE TABLE browser_profiles (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, host text NOT NULL,
 cipher text, revision bigint NOT NULL DEFAULT 1, expires_at timestamptz NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(owner_id,host));
CREATE TABLE browser_session_profiles (
 session_id uuid NOT NULL REFERENCES browser_sessions(id),
 profile_id uuid NOT NULL REFERENCES browser_profiles(id),
 PRIMARY KEY(session_id,profile_id));
