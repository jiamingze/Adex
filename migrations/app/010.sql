ALTER TABLE files ADD COLUMN deleted_at timestamptz;
UPDATE files SET deleted_at=now() WHERE status='DELETED' AND deleted_at IS NULL;
