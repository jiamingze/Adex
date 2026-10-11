ALTER TABLE users ADD COLUMN IF NOT EXISTS is_guest boolean NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS guest_users_created ON users(created_at) WHERE is_guest;
