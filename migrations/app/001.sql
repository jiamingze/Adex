CREATE TABLE IF NOT EXISTS users (
 id uuid PRIMARY KEY, username text UNIQUE NOT NULL, password_hash text NOT NULL,
 memory_revision bigint NOT NULL DEFAULT 1, forgotten_before timestamptz,
 created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS sessions (
 token_hash text PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id),
 expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS conversations (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id), title text NOT NULL,
 next_seq bigint NOT NULL DEFAULT 0, next_event_seq bigint NOT NULL DEFAULT 0,
 created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS conv_owner ON conversations(owner_id,created_at,id);
CREATE TABLE IF NOT EXISTS messages (
 id uuid PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES conversations(id),
 seq bigint NOT NULL, role text NOT NULL CHECK(role IN ('user','assistant')),
 content text NOT NULL, client_message_id uuid, dedupe_key text,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(conversation_id,seq), UNIQUE(conversation_id,client_message_id), UNIQUE(dedupe_key));
CREATE TABLE IF NOT EXISTS turns (
 id uuid PRIMARY KEY REFERENCES messages(id), conversation_id uuid NOT NULL REFERENCES conversations(id),
 owner_id uuid NOT NULL REFERENCES users(id), status text NOT NULL DEFAULT 'QUEUED',
 epoch bigint NOT NULL DEFAULT 0, attempt_id uuid, lease_until timestamptz,
 memory_revision bigint, error_code text, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS turns_claim ON turns(status,created_at);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_turn ON turns(conversation_id) WHERE status IN ('QUEUED','RUNNING');
CREATE TABLE IF NOT EXISTS events (
 conversation_id uuid NOT NULL REFERENCES conversations(id), seq bigint NOT NULL,
 event_id uuid NOT NULL UNIQUE, type text NOT NULL, payload jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(conversation_id,seq));
CREATE TABLE IF NOT EXISTS memories (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id), content text NOT NULL,
 content_hash text NOT NULL, source_refs jsonb NOT NULL DEFAULT '[]',
 confirmed boolean NOT NULL DEFAULT true, revision bigint NOT NULL DEFAULT 1,
 deleted_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(owner_id,content_hash));
CREATE TABLE IF NOT EXISTS memory_tombstones (
 owner_id uuid NOT NULL REFERENCES users(id), content_hash text NOT NULL,
 deleted_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(owner_id,content_hash));
CREATE TABLE IF NOT EXISTS summaries (
 conversation_id uuid PRIMARY KEY REFERENCES conversations(id), owner_id uuid NOT NULL,
 covered_to_seq bigint NOT NULL, memory_revision bigint NOT NULL, content text NOT NULL,
 source_refs jsonb NOT NULL, summarizer_version text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS notifications (
 id uuid PRIMARY KEY, event_id uuid NOT NULL UNIQUE, owner_id uuid NOT NULL REFERENCES users(id),
 conversation_id uuid NOT NULL REFERENCES conversations(id), title text NOT NULL,
 body text NOT NULL, read boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS consumed_events (
 event_id uuid PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS outbox (
 id uuid PRIMARY KEY, kind text NOT NULL, resource_id uuid NOT NULL, delivered_at timestamptz,
 attempt_count integer NOT NULL DEFAULT 0, next_attempt_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(kind,resource_id));

ALTER TABLE turns ADD COLUMN IF NOT EXISTS web_search boolean NOT NULL DEFAULT false;
CREATE TABLE IF NOT EXISTS login_limits (bucket text PRIMARY KEY,window_start timestamptz NOT NULL,attempts integer NOT NULL);
