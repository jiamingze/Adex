CREATE TABLE message_files (message_id uuid NOT NULL REFERENCES messages(id), file_id uuid NOT NULL REFERENCES files(id), PRIMARY KEY(message_id,file_id));
