-- Display name is independent from the stable login username and ownership UUID.
ALTER TABLE users ADD COLUMN nickname text NOT NULL DEFAULT '' CHECK(char_length(nickname) <= 40);
