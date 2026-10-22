-- A task proposal is not a success receipt. Survives chat takeover without duplicating work.
CREATE TABLE chat_task_actions (
 turn_id uuid PRIMARY KEY REFERENCES turns(id) ON DELETE CASCADE,
 request_hash text NOT NULL,
 state text NOT NULL CHECK(state IN ('PENDING','SUCCEEDED')),
 receipt jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK((state='SUCCEEDED')=(receipt IS NOT NULL))
);
