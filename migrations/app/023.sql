-- Short-lived per-turn query context, distinct from durable long-term memory.
ALTER TABLE turns ADD COLUMN client_location jsonb;
ALTER TABLE turns ADD COLUMN location_hash text NOT NULL DEFAULT '';
