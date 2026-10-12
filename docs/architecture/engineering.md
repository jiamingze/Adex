# Backend engineering conventions

Adex remains four independently deployable business domains. Within each service, organize code by capability, with explicit transport, application, domain and infrastructure responsibilities where these exist. Adding packages is not a reason to add business services or duplicate state owners.

- HTTP adapters authenticate and translate requests. Application services own use cases and transaction boundaries. Repositories/ports isolate persistence where multiple use cases share an invariant; avoid interfaces with no meaningful substitution or testing boundary.
- App owns identity, conversations, memory, workspace and notifications. Automation owns schedules, runs, attempts and outbox. Agent owns model invocation/checkpoint execution. Tools owns provider adapters, approvals and effect reconciliation.
- A controller must not be injected into another controller or background worker. Cross-module use goes through an application service, storage port or authenticated service gateway.
- Python entry points compose the application and lifecycle only. Route modules are grouped by capability, with schemas separate from execution. Provider clients cannot import HTTP route modules.
- Keep transaction scope short. Preserve owner checks, lock ordering, stable idempotency keys, lease/epoch/attempt fencing, immutable checkpoints and UNKNOWN reconciliation during refactoring.
- Document why an invariant exists and which transaction protects it. Do not add comments that repeat statements, catch-and-ignore business failures, or generate speculative abstractions.
- Use constructor injection in Java and explicit dependency injection at Python composition boundaries. Dependencies point toward use cases/ports, never back toward web entry points.
- Java formatting and architecture checks are build gates. Python formatting/lint and architecture checks run in CI. Functional/fault regression remains necessary; package structure alone proves no reliability or capacity claim.

This refactoring preserves public/internal HTTP contracts and database schemas. It is engineering groundwork, not evidence of Codex/Doubao-scale capacity. Load, security, deployment and recovery acceptance remain separate gates in `docs/ACCEPTANCE.md`.

## Source map

| Service | Capability modules | Composition / important ports |
| --- | --- | --- |
| App | `identity`, `account`, `conversation`, `memory`, `workspace`, `notification`, `integration`, `config` | `AppMain`; `ConversationStore` → `PostgresConversationStore`; `UploadedFile` → `MultipartUpload`; kernel `FileStorage` → `LocalFileStorage` |
| Automation | `schedule`, `run`, `monitor` | `AutomationMain`; scope-checked controllers → `ScheduleService`, `RunService`, `RunExecutionService` |
| Agent | `api`, `routing`, `execution`, `models`, `skills` | `main.create_app`; `Runtime` composes `ContextService`, `InvocationService`, `CheckpointStore`, `BackgroundWorker`; `InteractiveTurnService` handles chat intents; `ModelProvider` is the streaming port |
| Tools | `api`, `retrieval`, `creation`, `creation/providers`, `approvals`, `runners`, `workspace` | `main.create_app`; provider factory selects submission adapters; `MediaSubmissionProvider` separates submission from optional cancellation/catalog capabilities |

The Java packages use capability-first organization: controller, application service and adapter names expose the responsibility inside each module. Python separates HTTP composition from capability implementations. Neither arrangement requires a separate deployable service for each feature.

## Change checklist

1. Identify the state owner and invariant before writing code.
2. Keep request parsing/authorization at the transport edge; pass explicit owner/claims to the use case.
3. Put shared storage behavior behind a meaningful port, not a controller call.
4. Document transaction lock order, fencing, UNKNOWN or crash recovery when relevant.
5. Run `make format`, `make build test check-style`, and `make test-integration` for reliability changes. Integration tests create isolated databases and never mutate user data.
6. Update contracts/docs and push verified changes. A formatting pass does not replace review or tests.

## Remaining explicit engineering debt

Workspace preview/Range streaming and some file/artifact endpoints still combine HTTP response handling with persistence checks. Preserve their authorization and crash-recovery tests when extracting them further. Maps remain in parts of the legacy wire contract; convert to typed DTOs incrementally with contract tests. Central kernel JDBC helpers are infrastructure, not domain entities. Additional load/SLO, tracing, vulnerability and deployment evidence is required before describing this as a production system at large-company scale.

## Skill boundaries

See [Skill architecture](skills.md) and [ADR 003](../adr/003-skills-and-transaction-boundaries.md). Skills are versioned, trusted execution policies, never permission grants. Booking adapters remain disabled until concrete quotes, user approval and durable effect reconciliation are implemented.

## Connectors and proactive assistance

See [the implementation and external acceptance boundaries](proactive-assistant.md).
App capability modules now include `connector`, `proactive`, `productivity` and
notification push adapters. Tools adds `connectors` (contracts/vault/registry/Google)
and common `approvals/actions`. New Run kinds and connector polling templates extend
existing Automation; no new scheduler or state owner is introduced. Credential
material remains in its owning service, and all writes require human approval plus
provider receipts rather than model output.
