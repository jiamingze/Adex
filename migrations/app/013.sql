CREATE TABLE artifact_exports (
 id uuid PRIMARY KEY, artifact_id uuid NOT NULL REFERENCES artifacts(id),
 version_id uuid NOT NULL REFERENCES artifact_versions(id), file_id uuid NOT NULL REFERENCES files(id),
 format text NOT NULL CHECK(format IN ('SVG','PNG')), renderer_version text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(version_id,file_id));
