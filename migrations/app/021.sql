ALTER TABLE matrix_tasks ADD COLUMN description text NOT NULL DEFAULT ''
    CHECK (char_length(description) <= 16000);
