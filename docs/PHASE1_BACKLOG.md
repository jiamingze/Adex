# Adex 1.0 · Milestone Backlog

| Milestone | Deliverables | Required verification |
| --- | --- | --- |
| M00 | Four services, Monorepo, independent builds and Docker, PG/Redis/ES dev + bind-mounted LocalFileStorage (no OSS/MinIO), OpenAPI, CI, health, env sample, local runbooks | Fresh clone environment smoke, SDK spec lint, health integration |
| M01 | User/auth/conversation/message persistence, SSE, Web chat, idempotent send | Same client_message_id one message, reconnect/final snapshot |
| M02 | Agent Router, Model Provider, Tool Gateway/WebSearch, source citation | API authenticated search, output citations, provider timeout |
| M03 | L1/L2/L3 Memory, user CRUD, async extraction, tombstones, ES re-index | New chat memory hit; deletion does not resurrect via re-index |
| M04 | Automation scheduler, task/run, lease/epoch, checkpoint, outbox and recovery | 3 competing schedulers, SIGKILL, stale-epoch CAS refusal |
| M05 | Notification center, original-conversation result, email, PWA push optional | Duplicate event one notification; iOS closed still task persisted |
| M06 | MusicCatalogProvider, PlaybackProvider, playlist/player card, uploaded licensed audio and link adapter | Real artist metadata; licensed fixture inline playback; commercial song open-provider |
| M07 | Travel plan, hotels/POI/weather/maps adapters, editable artifact | Two-day grounded itinerary, correct geo, updated revision |
| M08 | Deep research, Workspace/Files, report output, artifact versions | Background research and restart resume; downloadable report |
| M09 | Sandboxed code-runner, HTML game generation/iteration | Game plays; cross-origin and network isolation test |
| M10 | Capacitor iOS free-install, image upload and speech-to-text | Physical device tests with 7-day re-sign caveat |
| M11 | Calendar or mail approved side-effect tool and effect reconciliation | Duplicate/UNKNOWN callback and permission revocation tests |
| M12 | Editable architecture/flow/sequence diagrams: DiagramSpec/Mermaid validator, secure renderer, source/version, SVG/PNG export | Source round-trip and script-safe export |
| M13 | Provider-agnostic image generation/editing, uploaded reference images, creative jobs, versions, Mock + real API integration hook | Deterministic tests pass; real generation marked BLOCKED_EXTERNAL until credentials supplied |
| M14 | Original music generation: audio formats, licensed artifacts, playback, versions, reliable job completion | Audio playable; retries/webhook duplicates do not double-publish |
| M15 | Video generation: text/image→video, async provider poll/webhook, cancel, progress, thumbnails, local disk, Range/206 | Web/iPhone video play; restart recovers without duplicate submits |
| M16 | Alibaba ECS TLS + PG/local-files backup restore + E2E + chaos + cost/security | Complete ACC-01..ACC-26 evidence, report BLOCKED_EXTERNAL honestly |

**Rule:** Begin next milestone only after previous milestone tests pass or external blockers are clearly recorded. Required infrastructure correctness is never optional or moved to future just because the application is for a single personal user.

## External-blocker policy

- A Mock Provider is mandatory for deterministic contract/e2e simulation but does not count as a real-world data-provider integration.
- Mark `BLOCKED_EXTERNAL` when keys, contract, media license or internet reachability are missing. Never simulate a fake 'verified real hotel price' or 'full-song playable' response for release evidence.
- Real tests should be opt-in via environment variables, cost-limited, and must not run in CI using personal data by default.

## Explicit user-requested extension

| M17 | Owner-bound macOS application operation via native Accessibility runner under Tools; existing Automation checkpoints, fencing, approvals and effects | Real Calculator observation → per-action approval → 1+2=3 readback; fail closed for other owners, deleted conversations, stale observations and UNKNOWN effects. Explicit owner app policy, Chrome search and bounded document return; custom controls remain limited. See ADR 005 and the macOS runbook; broader custom UI remains unsupported. |
| M18 (incremental) | Local MT5 research Skill, owner-bound read bridge, broker preflight and explicitly synthetic order simulator | Installed Mac MT5 read and order_check observed; no real order submission. Durable trading proposals, chart/analysis handoff and client cards remain pending. See `architecture/mt5-trading.md`. |
