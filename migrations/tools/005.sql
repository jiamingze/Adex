ALTER TABLE media_jobs ADD COLUMN provider_job_id text;
ALTER TABLE media_jobs ADD COLUMN provider_status text;
ALTER TABLE media_jobs ADD COLUMN provider_version bigint NOT NULL DEFAULT 0;
CREATE UNIQUE INDEX media_external_job ON media_jobs(provider,provider_job_id) WHERE provider_job_id IS NOT NULL;
