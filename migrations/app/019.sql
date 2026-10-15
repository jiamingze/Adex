-- Freeze semantic input before paid inference; Turn identity fences replay and ownership.
CREATE TABLE memory_turn_plans (
 turn_id uuid PRIMARY KEY REFERENCES turns(id),
 owner_id uuid NOT NULL REFERENCES users(id),
 input jsonb NOT NULL,
 proposal jsonb,
 receipt text,
 applied_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX memory_turn_plans_owner ON memory_turn_plans(owner_id,created_at);
