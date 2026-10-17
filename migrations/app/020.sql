-- Stable chat-origin identity; UI-created todos remain nullable.
ALTER TABLE matrix_tasks ADD COLUMN source_turn_id uuid REFERENCES turns(id);
CREATE UNIQUE INDEX matrix_tasks_source_turn ON matrix_tasks(source_turn_id)
    WHERE source_turn_id IS NOT NULL;
