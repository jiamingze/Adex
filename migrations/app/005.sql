ALTER TABLE conversations ADD COLUMN deleted_at timestamptz;
ALTER TABLE users ADD COLUMN settings jsonb NOT NULL DEFAULT '{"memory_enabled":true,"email_notifications":false}'::jsonb;
