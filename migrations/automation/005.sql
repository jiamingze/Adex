-- Connector polling is a template on the existing schedule/occurrence/Run system.
ALTER TABLE schedules ADD COLUMN task_kind text NOT NULL DEFAULT 'CHAT' CHECK(task_kind IN ('CHAT','CONNECTOR_SYNC'));
ALTER TABLE schedules ADD COLUMN task_request jsonb NOT NULL DEFAULT '{}'::jsonb;
