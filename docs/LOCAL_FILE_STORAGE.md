# LocalFileStorage — Adex Phase 1 mandatory contract

**Status**: binding ADR in `Adex_Product_Technical_Design_v4.1.md` P1-07. No OSS / S3 / MinIO in Phase 1. Images, videos, recorded audio, user documents, HTML games, reports, screenshots and large checkpoint artifacts live on the single ECS's persistent disk.

## On-disk volumes

- ECS mount: `/data/adex/files` (prefer independent data disk; ensure persists across container rebuild).
- App container mount: `/var/adex/files`, environment `ADEX_FILE_STORAGE_BACKEND=local`, `ADEX_FILE_STORAGE_ROOT=/var/adex/files`.
- Mac compose profile: `./.local-data/files:/var/adex/files`. Git ignore `/.local-data/`.
- Store by random object ID and hashed directory shard. **Never** concatenate user-controlled filenames into paths. Avoid publicly readable webroot and symlink traversal.
- App owns the File API. Agent/Tools/Runners upload via internal protected API, with content streaming and scoped service credentials. Runners use separate temporary directories; persistent files become visible only after controlled import.

## Persistence state machine

1. PostgreSQL record `PENDING`: `file_id`, `owner_id`, `object_id`, `storage_backend=LOCAL`, `storage_key`, `mime`, `size`, `sha256`, ACL, created_at, retention, artifact version and run refs.
2. Stream bytes to temporary file under same filesystem with per-owner quota and max-size enforcement, sniff file type, compute SHA-256, `fsync`.
3. `atomic rename` to final shard path; `fsync` parent directory when supported. In PG CAS `PENDING → READY`.
4. `GET`/`HEAD` only returns READY after authorization, with streaming and HTTP Range 206 for user-owned audio/video, proper private cache controls.
5. Scheduled reconciler removes incomplete temp/orphan objects and handles stale PENDING/DELETING records safely with grace periods and retained references.

*File system and PG are **not ACID together**: do not pretend the rename and PG update are one transaction. Write tests for crash on each boundary.*

## Required API surface

- `POST /api/v1/files`: multipart upload with `Idempotency-Key`, returns `file_id`, `sha256`, `mime_type`, `size_bytes`, `status`.
- `GET /api/v1/files/{file_id}`: metadata with owner ACL check.
- `GET /api/v1/files/{file_id}/content`: authenticated streaming download, `Range` and `206 Partial Content` support when valid.
- `DELETE /api/v1/files/{file_id}`: logical delete / tombstone; physical cleanup only when not referenced/after retention.
- `POST /internal/files`: service-scoped streaming upload with source `task_id/run_id/step_id`, validated caller role and quota. Internal URL not exposed publicly.
- `FileStorage.put/read/stat/delete` backend abstraction; Phase 1 only `LocalFileStorage`, optional future adapter for OSS.

## Security

- Max size, content sniffing, antivirus/isolated processing where available, path traversal/symlink/TOCTOU prevention, malicious archives/zip-bomb protections, execute-bit suppression, per-owner ACL and audit.
- Generated HTML/JS is previewed on sandbox origin and cannot access App session/cookies or arbitrary outbound network. No direct static mapping of file root.
- Music: inline media only user-owned or provider-licensed; do not cache or download unauthorized commercial music. Remote artwork only according to provider terms.

## Reliability and disaster recovery

- Normal container restart and host reboot **must not** lose media. Separate from OS root filesystem and app deployment directory.
- Monitor free bytes, inode exhaustion, disk I/O, quota, upload failures. Reject new uploads before completely filling volume; never delete user objects to reclaim capacity blindly.
- Pair PostgreSQL backup with disk snapshot/file-backup epoch. Validate restored PG metadata ⇄ `READY` objects and sha256, restore to fresh sandbox/ECS. An ECS disk without an independent copy is a single point of failure. No uptime guarantee during single-host outage.
- Future multi-ECS requires shared storage or explicit file routing/migration; multiple separate local disks are not a distributed shared file store.

## Acceptance

- ACC-13 backups and restore; ACC-18 full host restart; ACC-19 container recreate/media playback integrity; ACC-20 interrupted upload/ACL/disk-full.

## v4.1 Creative Media Storage Rules

- Generated image/audio/video, architecture diagram editable `.mmd` and `.json`, exports `.svg` / `.png`, thumbnails/posters/waveforms and reference inputs are covered by **the same App-owned LocalFileStorage API and PG ACL**.
- All long-form media downloads are streamed to a bounded temporary file (never full payload buffered in Java heap) then magic/MIME/size/sha256/duration/probe verified and atomically published. Source URL from model provider is restricted by allowlist and SSRF protections.
- `ArtifactVersion` immutable references its input and all source/output file IDs, model ID and generation job. Content hash and file ACL verified on reads. Shared derived files use reference counting or deletion graph; delete must not break old revisions still retained.
- Video and audio must support authenticated HTTP range `206`, `Content-Range`, `Accept-Ranges`, `ETag`, correct file length and cancellation during stream. Browser and iOS format compatibility must be measured with real devices.
- Existing `/data/adex/files` ECS bind mount remains mandatory. **Never switch to OSS, S3, or MinIO without a future approved ADR.**
