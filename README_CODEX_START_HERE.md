# Adex · Codex First Read (v4.1 Phase 1)

> Implementation update (2026-10-11): see [README.md](README.md) and [implementation status](docs/IMPLEMENTATION_STATUS.md) for the implemented application and observed checks. The original kickoff contract below is retained for reference; Phase 1 scope follows ADR 001.

> This is **documentation + development contract**, NOT pre-built running application code. Start with Phase 1 milestone **M00**, then advance one milestone per PR. Do not claim that `make doctor`/`docker compose up` already work until you implement and test them.

## Read in order

1. `AGENTS.md` — immutable architectural/quality rules.
2. `docs/Adex_Product_Technical_Design_v4.1.md` — approved Phase 1 product requirements, followed by the entire earlier v3.1 architecture and reliability design.
3. `docs/PHASE1_BACKLOG.md` — dependencies and deliverables per milestone.
4. `docs/ACCEPTANCE.md` — E2E/fault-injection gates.
5. `docs/PROVIDER_AND_MUSIC.md` and `docs/MULTIMODAL_CREATION.md` — source/licensing/runtime rules.
6. `docs/SERVICE_CONTRACTS.md` and `packages/contracts/openapi-phase1.yaml` — API candidate contracts; evolve via contract-first changes.
7. `docs/DEPLOY_MAC_IOS_ALIYUN.md` — local and ECS operating profile.

## Suggested initial task to send to Codex

> Read `AGENTS.md` and all v4.1 Phase-1 specs. Implement **milestone M00 only** as a working, secure multi-language monorepo skeleton: 4 services with independent Dockerfiles and /health/live /health/ready; React Vite web + shared UI package + Capacitor project skeleton; PostgreSQL/Redis/Elasticsearch dev Compose profiles and bind-mounted local file directory (`./.local-data` on Mac; `/data/adex/files` on ECS); service-specific migrations/DB credentials; OpenAPI schemas and client generation; Makefile `doctor`, `test-contract`, `up-dev`, `down-dev`; CI checks and .env.example; no production secrets. Run the commands, include actual test logs, and list external/provider blockers. Do NOT implement M01+ yet.

## Done means

- A fresh developer can clone and start the skeleton with documented dependencies/versions, and tests actually run.
- Services refuse unsafe configurations and secrets stay local; no host-wide root shell requirements.
- Each service is separately runnable and deployable.
- M00 tests exist and are executed; no dummy `echo success` substitutions.

## Newly added creative milestones

After M11, implement M12 (editable diagrams), M13 (image generation/editing adapters), M14 (original music creation), M15 (video generation), then M16 full cloud release and recovery verification. Real provider integration is blocked pending user-supplied APIs; mocks and contracts MUST still work. Read `docs/MULTIMODAL_CREATION.md` and `docs/PROVIDER_INTEGRATION_CHECKLIST.md`.

## Working topology

- macOS: VS Code/Codex, Xcode Personal Team, Web/iOS, unit tests.
- Alibaba Cloud ECS: Docker Compose / data services / Linux integration test. Git/CI deploy. Codex is not required on cloud host.
- For full ES + 2 JVMs + 2 Python services + sandbox, 8vCPU/32GiB is a **planning suggestion**, not a proven capacity requirement; 4vCPU/16GiB may require selective Compose profiles.
