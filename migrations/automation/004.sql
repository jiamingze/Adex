ALTER TABLE monitor_sources ADD COLUMN kind text NOT NULL DEFAULT 'SEARCH';
ALTER TABLE monitor_sources ADD COLUMN request jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE monitor_subscriptions ADD COLUMN rule jsonb NOT NULL DEFAULT '{}'::jsonb;
