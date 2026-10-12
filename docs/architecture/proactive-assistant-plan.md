# Proactive assistant implementation plan — 2026-10-12

## Actual gap audit

Four existing business services remain App/Agent/Automation/Tools. PostgreSQL owns
state, Redis is a rebuildable context cache, Elasticsearch is an optional asynchronous
index. Existing CalDAV approval/effect tables, Automation leases/fencing/checkpoints
and result Outbox are implemented. No Google OAuth/connectors, common action approval,
APNs, proactive signal domain or user task matrix exists at the start of this change.
Travel Skill is read-only; no model output can constitute an external action receipt.

## Migration list (service-owned)

- tools/006.sql: connector connections (encrypted credential envelope, revision),
  expiring single-use OAuth state with PKCE and session binding; extend existing
  approvals with common kind/connector/execution binding; reuse existing effects.
- app/016.sql: proactive signals with owner/connection/resource/version dedupe,
  correlation and deterministic importance reasons; user notification preferences;
  APNs devices and per-notification delivery state; notifications add run/action refs;
  matrix tasks (importance/urgency/manual status/due date, optional existing Run ref).
- No new task scheduler or recovery engine. Connector sync and approved actions use
  two new kinds on existing Automation runs. Signal/notification delivery leverages
  existing durable result Outbox and App consumption, not a second message broker.

## Interface contracts

All public routes authenticate through App; registered accounts only for connectors,
actions, push devices and matrix. App→Tools validates issuer/scope/owner/resource.
OAuth callback requires initiating session binding, short-lived state and PKCE.

| Public App endpoint | Contract |
| --- | --- |
| GET /api/v1/connectors | redacted connection list and availability |
| POST /api/v1/connectors/google/authorize | service calendar/gmail; access read/write/send; returns consent URL, no token |
| GET /api/v1/connectors/google/callback | state+code bound to initiating authenticated session; redirects to UI |
| POST /api/v1/connectors/{id}/revoke | local access disabled first; remote revoke confirmation or pending, then credential erasure |
| POST /api/v1/connectors/{id}/query | calendar interval or Gmail bounded search; owner/scopes enforced |
| POST /api/v1/connectors/{id}/sync | original conversation + idempotency key → existing CONNECTOR_SYNC Run |
| POST /api/v1/actions | immutable calendar.update or gmail.send snapshot; registered connection + conversation |
| GET /api/v1/actions | owner-scoped drafts and receipts |
| POST /api/v1/actions/{id}/approve | exact request hash confirmation → approved action → existing CONNECTOR_ACTION Run |
| POST /api/v1/actions/{id}/revoke | pending/approved only; dispatched writes cannot be undone locally |
| GET /api/v1/signals | correlated, importance-rated suggestions; no automatic writes |
| GET/PUT /api/v1/notification-preferences | enabled/min importance/quiet hours/timezone/push |
| POST/DELETE /api/v1/push/devices | token registration/revocation; no token readback |
| GET /api/v1/notifications/{id}/resume | verify owner and refs → conversation/run/action snapshot |
| GET/POST/PATCH/DELETE /api/v1/matrix | manual task CRUD and quadrant grouping; optional link to authoritative existing Run |

Read-only calendar conflict analysis compares actual overlapping timed events. Gmail
sync uses bounded metadata reads and changes are deduped by resource/version; connector
sync is explicit or scheduled via existing Automation. No unverified webhook accepts
arbitrary external events. Initial implementation polls bounded snapshots, not full
mailbox Pub/Sub/history replication; this limitation must be documented.

## Execution invariants

Write draft captures exact request and calendar ETag. User confirms immutable hash;
expiry/revocation/scopes are checked again before dispatch. Agent must provide live
Automation run/epoch/attempt, and Tools authorizes the stable action effect key.
Effects commit IN_FLIGHT before network I/O. Calendar update uses If-Match and verifies
readback. Gmail send is not safely idempotent: timeout/crash becomes UNKNOWN, never
blindly resend; reconciliation searches stable Message-ID and requires a real receipt.
Recovery reuses original action/run identifiers. Stale ETag requires a new draft.

OAuth tokens use AES-GCM with external encryption key and connection/owner AAD.
OAuth state verifier is also encrypted. Plaintext keys/tokens never reach browser,
model, checkpoints, public responses, logs or Git. Revocation prevents new I/O before
attempting provider revocation. Connection revision gates post-network commits.

App consumes connector result signals inside existing result transaction; owner/
conversation/memory revision guards still apply. Importance is explainable rule-based
assessment (calendar conflict, IMPORTANT email), not instructions from email text.
Preferences suppress pushes without losing durable signals. APNs payload uses generic
lock-screen text plus IDs; server resume verifies ownership. APNs acceptance is not
proof of device display or user reading. Personal Team APNs may be unavailable.

## Module implementation and verification order

1. Contracts/migrations and isolated database tests.
2. Connector registry, Google provider/OAuth/encrypted vault and App gateway.
3. Common approval and effect dispatch on existing Automation/Agent chain.
4. Signal consumption, preferences, task matrix and client controls.
5. APNs transport/device registration and native notification navigation.
6. Three fixture-backed E2Es: conflict→approve→update→verify; important email→signal;
   offline→push delivery→resume original Run. Add security/ownership/replay/fencing
   tests and run build/unit/integration/lint/style/secret gates after each module.

Fixture providers/APNs in isolated tests must be labelled TEST_FIXTURE and disabled
outside explicit isolated-test configuration. Real Google requires OAuth client,
verified redirect and user consent; real APNs requires eligible signing/topic/device
and provider credentials. Missing prerequisites return BLOCKED_EXTERNAL. Mock E2E
passes are never reported as real Google changes or real phone notifications.

Sources: Google OAuth web-server/best-practices, Calendar events API, Gmail scopes;
Apple APNs HTTP/2/token authentication documentation. Product comparison awaits exact
Muse/today.ai URLs rather than guessing a same-name product.
