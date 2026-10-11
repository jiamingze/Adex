CREATE TABLE IF NOT EXISTS daily_budgets (
 owner_id uuid NOT NULL, day date NOT NULL, reserved_calls integer NOT NULL DEFAULT 0,
 PRIMARY KEY(owner_id,day));
CREATE TABLE IF NOT EXISTS checkpoint_audits (
 checkpoint_id uuid PRIMARY KEY REFERENCES checkpoints(id),
 status text NOT NULL CHECK(status IN ('REFERENCED','ORPHAN')),
 checked_at timestamptz NOT NULL DEFAULT now());
