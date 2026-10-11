ALTER TABLE artifacts ADD COLUMN origin_conversation_id uuid REFERENCES conversations(id);
ALTER TABLE artifacts ADD COLUMN source_run_id uuid;
CREATE UNIQUE INDEX artifact_run_unique ON artifacts(source_run_id) WHERE source_run_id IS NOT NULL;
ALTER TABLE artifact_versions ADD COLUMN parent_version_id uuid REFERENCES artifact_versions(id);
ALTER TABLE artifact_versions ADD COLUMN source_job_id uuid;
CREATE UNIQUE INDEX artifact_job_unique ON artifact_versions(artifact_id,source_job_id) WHERE source_job_id IS NOT NULL;
