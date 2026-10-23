-- Compare observed evidence independently of LLM wording; no separate task state machine.
ALTER TABLE runs ADD COLUMN observation_fingerprint text;
ALTER TABLE runs ADD CONSTRAINT runs_observation_fingerprint_format
    CHECK (observation_fingerprint IS NULL OR observation_fingerprint ~ '^[a-f0-9]{64}$');
