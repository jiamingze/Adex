-- Bounded native calendar observation, retained only while the chat turn is pending.
-- Hash survives cleanup to keep send retries idempotent without retaining event content.
ALTER TABLE turns ADD COLUMN client_calendar jsonb;
ALTER TABLE turns ADD COLUMN calendar_hash text NOT NULL DEFAULT '';
