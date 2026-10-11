CREATE TABLE monitor_sources (
 id uuid PRIMARY KEY, source_key text NOT NULL UNIQUE, query text NOT NULL,
 interval_seconds integer NOT NULL CHECK(interval_seconds>=300), next_poll_at timestamptz NOT NULL DEFAULT now(),
 lease_until timestamptz, epoch bigint NOT NULL DEFAULT 0, last_error text);
CREATE TABLE monitor_subscriptions (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, origin_conversation_id uuid NOT NULL,
 source_id uuid NOT NULL REFERENCES monitor_sources(id), keyword text NOT NULL,
 active boolean NOT NULL DEFAULT true, quiet_seconds integer NOT NULL DEFAULT 3600 CHECK(quiet_seconds>=300),
 last_notified_at timestamptz, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE observations (
 id uuid PRIMARY KEY, source_id uuid NOT NULL REFERENCES monitor_sources(id), content_hash text NOT NULL,
 payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(source_id,content_hash));
CREATE TABLE monitor_intents (
 id uuid PRIMARY KEY, observation_id uuid NOT NULL REFERENCES observations(id), subscription_id uuid NOT NULL REFERENCES monitor_subscriptions(id),
 payload jsonb NOT NULL, delivered_at timestamptz, lease_until timestamptz, claim_id uuid,
 UNIQUE(observation_id,subscription_id));
