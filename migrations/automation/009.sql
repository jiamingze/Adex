-- Schedule CAS alone cannot distinguish a stale edit from a lost successful response.
CREATE TABLE schedule_mutations (
 owner_id uuid NOT NULL,
 command_key text NOT NULL,
 schedule_id uuid NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
 request_hash text NOT NULL,
 response jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(owner_id,command_key)
);
