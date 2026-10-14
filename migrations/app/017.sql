-- App-owned personal notes; CAS revisions prevent concurrent-device overwrites.
CREATE TABLE notes (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id),
 title text NOT NULL CHECK(char_length(title) BETWEEN 1 AND 200),
 content text NOT NULL DEFAULT '' CHECK(char_length(content) <= 100000),
 pinned boolean NOT NULL DEFAULT false, revision bigint NOT NULL DEFAULT 1,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 deleted_at timestamptz
);
CREATE INDEX notes_owner_order ON notes(owner_id,pinned DESC,updated_at DESC) WHERE deleted_at IS NULL;
