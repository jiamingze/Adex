# Adex Codex / AI Coding Agent Rules (Phase 1 · v4.1)

## Source of truth
Read `README_CODEX_START_HERE.md`, then `docs/Adex_Product_Technical_Design_v4.1.md`, `docs/PHASE1_BACKLOG.md`, and `docs/ACCEPTANCE.md` **before modifying code**. All examples are design contracts, not claims existing code already runs.

## Frozen architecture
- Exactly four **business service domains**: Java 21 Spring Boot `services/adex-app`, Java 21 Spring Boot `services/adex-automation`, Python 3.12+ FastAPI `services/adex-agent`, Python 3.12+ FastAPI `services/adex-tools`.
- Agent interactive/background Workers and Browser/Code Runners may be standalone containers; they are **not new business services**.
- iOS/Web first: React + TypeScript + shared UI Schema. Web Vite. iOS uses Capacitor + Xcode Personal Team (free 7-day signing); no React Native in Phase 1.
- Databases: PostgreSQL authoritative; Redis cache; Elasticsearch async search/index (non-authoritative); **local persistent ECS disk for ALL files/media/artifacts** via `LocalFileStorage` (no MinIO, OSS or S3 in Phase 1). One DB instance may host separate service-owned schemas + DB roles.
- Files are App-owned with PostgreSQL file metadata and `/data/adex/files` bind mount on ECS, private API read/write, durable temp→rename→READY and orphan cleanup; Tools/Runner use internal File API, not unmanaged writes to persistent files.
- Preserve 3-layer memory: L1 Working / L2 Conversation / L3 Long-term with user deletion and non-resurrection; memory != Agent Checkpoint != Automation Run state.
- Ordinary chats go App -> Agent -> optional Tools -> App SSE; **do not route all chat through Automation**. Background/recurring/monitor work goes through Automation.
- Phase1 Single-Agent default; multi-agent extension points only until proven useful; do not create per-feature microservices.

## Non-negotiable correctness
- PG unique occurrence `schedule_id + scheduled_at`; atomic schedule claiming via `FOR UPDATE SKIP LOCKED` inside short transaction + Run + Outbox.
- Worker claim / lease / heartbeat / fencing epoch + attempt ID. CAS on state writes. Do not hold row lock across LLM/browser execution.
- Agent immutable checkpoint first, Automation authoritative checkpoint-ref commit second; detect/recover orphan checkpoints.
- Tool side effects have stable idempotency `effect_key`, permission validation, UNKNOWN reconciliation. Never promise external exactly-once where unsupported.
- Outbox + deduplicating consumer for cross-service results and notifications; origin-conversation result backfill.
- Reject/disable writes when authoritative PostgreSQL is unavailable. Redis/ES outage must not compromise durable state.
- Sandbox untrusted HTML/JS in isolated origin and runner with CPU/memory/network constraints. Never run generated JS in the App main origin.
- Do not introduce MinIO/OSS or proxy unauthorized copyrighted audio; future storage backends behind `FileStorage`.
- Never commit actual tokens, cookies, API keys, private music audio, or user data; never modify production database as part of development tests.

## Creative image/diagram/music/video (Phase 1)
- Phase 1 includes image generation/editing, editable system/flow diagrams, original music generation, and text/image-to-video generation. Maintain separate music catalog/playback versus ORIGINAL music generation paths.
- Diagram source (DiagramSpec/Mermaid) is canonical and editable; always validate/sanitize render, preserve source and exports, never execute arbitrary generated HTML in the main origin.
- All media generation uses provider-agnostic capabilities and `MediaGenerationProvider` under Tools. User will supply real model APIs later; until then use deterministic mocked providers and record `BLOCKED_EXTERNAL` for actual image/music/video generation. Do not invent successful real API connections.
- Long media tasks persist Automation Task/Run with lease+epoch and Tools provider effect ledger; store external job ID, validate signed webhook, reconcile UNKNOWN, never blindly resubmit on timeout.
- All generated image/audio/video/diagram files and derivatives persist to ECS LocalFileStorage via App authorized File API, private PG ownership + immutable artifact versions. No OSS/MinIO.
- Generated media safety: user consent/rights for reference images, likeness and voice; no unauthorized protected songs/DRM/voice impersonation. Log budget, model version and provenance without leaking secrets.

## Music and external data
- Separate `MusicCatalogProvider` from `PlaybackProvider`: music metadata search does NOT confer reproduction/streaming rights.
- In-app playback ONLY for user-owned or licensed audio. Mainstream commercial tracks lacking a playback license must deep-link to authorized provider or show unavailable.
- Do not scrape unauthorized music MP3, bypass DRM, or misuse Apple iTunes promotional previews as entertainment streaming.
- Tourism/hotel pricing and availability must be sourced and timestamped; no invented hotel inventory or pricing.

## Per-task workflow
1. Work on only the milestone Mxx requested; never try all of Phase 1 at once.
2. Write/update contracts and migration first, then tests, then production code, then health checks, docs and runbooks.
3. Use language-native formatting/tests; include smoke/contract/e2e/fault test for high-risk features.
4. Call out `BLOCKED_EXTERNAL` where third-party keys/license are missing, rather than faking success.
5. Provide concise commit summary, exact commands run, observed test output, and known limitations.
6. If docs conflict, follow v4.1 approved decisions and propose ADR for unresolved choices; do not silently rewrite service/DB architecture.

## Repository sync preference

After completing and verifying each user-requested change, commit the relevant code/docs and push to the configured GitHub remote. Never include secrets or private data; report any push failure.

## Local IDE preference

Use IntelliJ IDEA for the Java Maven reactor and PyCharm for the two Python service projects. Generate private JetBrains run configurations with scripts/ide.py; never commit .idea environments.

## Backend engineering boundaries

Follow `docs/architecture/engineering.md` and ADR 002. Organize implementations by capability; root service entry points only compose/bootstrap. Keep controllers thin, resolve HTTP authentication before application use cases, and never inject a controller into another controller or worker. Prefer meaningful storage/provider ports and constructor injection; do not create interfaces that only rename a dependency. Explain lock order, fencing, checkpoint commit and crash windows with focused comments. Java uses Google Java Format through Spotless; Python uses Ruff. Run `make check-style` and architecture checks in addition to behavioral tests; preserve service ownership and HTTP contracts during refactors.

## Owner-approved migration (2026-10-30)

The explicit owner request supersedes the Capacitor-only/native-client exclusion.
Follow `docs/adr/006-codex-kernel-native-clients.md` for Codex harness/app-server
integration and native SwiftUI iPhone/macOS clients. Preserve all other service
ownership, storage, memory, approval and recovery invariants.
