CREATE TABLE assistant_goals (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id),
 title text NOT NULL CHECK(length(title) BETWEEN 1 AND 200),
 outcome text NOT NULL DEFAULT '' CHECK(length(outcome)<=4000),
 status text NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','ARCHIVED')),
 revision bigint NOT NULL DEFAULT 1, request_hash text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX goals_owner ON assistant_goals(owner_id,status,created_at DESC);
CREATE TABLE goal_tasks (
 goal_id uuid NOT NULL REFERENCES assistant_goals(id),
 task_id uuid NOT NULL REFERENCES matrix_tasks(id) ON DELETE CASCADE,
 position integer NOT NULL, PRIMARY KEY(goal_id,task_id));
ALTER TABLE proactive_signals ADD COLUMN status text NOT NULL DEFAULT 'OPEN'
 CHECK(status IN ('OPEN','RESOLVED','DISMISSED','SNOOZED'));
ALTER TABLE proactive_signals ADD COLUMN snoozed_until timestamptz;
ALTER TABLE proactive_signals ADD COLUMN revision bigint NOT NULL DEFAULT 1;
CREATE INDEX signal_feedback ON proactive_signals(owner_id,status,snoozed_until);
ALTER TABLE proactive_signals ADD CONSTRAINT signal_snooze_state
 CHECK((status='SNOOZED')=(snoozed_until IS NOT NULL));
