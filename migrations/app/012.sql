ALTER TABLE messages ADD COLUMN cards jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(cards)='array');
