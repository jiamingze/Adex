ALTER TABLE notifications ADD COLUMN run_id uuid;
ALTER TABLE notifications ADD COLUMN action_id uuid;
ALTER TABLE notifications ADD COLUMN importance integer NOT NULL DEFAULT 70 CHECK(importance BETWEEN 0 AND 100);
CREATE TABLE proactive_signals (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id), connection_id uuid NOT NULL,
 conversation_id uuid NOT NULL REFERENCES conversations(id), run_id uuid NOT NULL,
 resource_id text NOT NULL, resource_version text NOT NULL, kind text NOT NULL,
 correlation_key text NOT NULL, importance integer NOT NULL CHECK(importance BETWEEN 0 AND 100),
 reasons jsonb NOT NULL, suggestion text NOT NULL, evidence jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(owner_id,connection_id,resource_id,resource_version,kind));
CREATE INDEX proactive_owner ON proactive_signals(owner_id,created_at DESC);
CREATE TABLE notification_preferences (
 owner_id uuid PRIMARY KEY REFERENCES users(id), enabled boolean NOT NULL DEFAULT true,
 push_enabled boolean NOT NULL DEFAULT false, min_importance integer NOT NULL DEFAULT 70 CHECK(min_importance BETWEEN 0 AND 100),
 quiet_start time, quiet_end time, timezone text NOT NULL DEFAULT 'Asia/Shanghai');
CREATE TABLE push_devices (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id), token_hash text NOT NULL UNIQUE,
 token_cipher text NOT NULL, environment text NOT NULL CHECK(environment IN ('sandbox','production')),
 active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE push_deliveries (
 notification_id uuid NOT NULL REFERENCES notifications(id), device_id uuid NOT NULL REFERENCES push_devices(id),
 status text NOT NULL CHECK(status IN ('PREPARED','IN_FLIGHT','ACCEPTED','UNKNOWN','FAILED','BLOCKED_EXTERNAL')),
 apns_id uuid NOT NULL, error_code text, dispatched_at timestamptz, completed_at timestamptz,
 PRIMARY KEY(notification_id,device_id));
CREATE TABLE matrix_tasks (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id), title text NOT NULL,
 important boolean NOT NULL, urgent boolean NOT NULL, due_at timestamptz,
 status text NOT NULL DEFAULT 'TODO' CHECK(status IN ('TODO','DONE')),
 run_id uuid, conversation_id uuid REFERENCES conversations(id), revision bigint NOT NULL DEFAULT 1,
 created_at timestamptz NOT NULL DEFAULT now());
