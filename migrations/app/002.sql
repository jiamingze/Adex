ALTER TABLE outbox ADD COLUMN IF NOT EXISTS lease_until timestamptz;
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS claim_id uuid;
