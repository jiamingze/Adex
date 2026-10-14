-- Explicit user copies are independent notes; dedupe repeated conversion clicks.
-- No FK to messages: deleting the source conversation must not delete a note the
-- user deliberately kept. A deleted note stays tombstoned on implicit retries.
ALTER TABLE notes ADD COLUMN source_message_id uuid;
CREATE UNIQUE INDEX notes_source_message ON notes(owner_id,source_message_id) WHERE source_message_id IS NOT NULL;
