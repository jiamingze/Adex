CREATE TABLE computer_observations (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, run_id uuid NOT NULL,
 bundle_id text NOT NULL, snapshot jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp());
CREATE INDEX computer_observation_run ON computer_observations(owner_id,run_id,created_at DESC);
CREATE TABLE computer_host_mutex (
 host_id text PRIMARY KEY, command_id uuid, lease_until timestamptz NOT NULL DEFAULT '-infinity');
