# Muse comparison and assistant workspace increment (2026-10-19)

This is an M11/proactive-workspace extension, not a new execution architecture.
Read the published product/security descriptions as vendor claims, not independent
acceptance evidence: https://introducing.muse.ai/ and
https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse

## Code gaps and scope

| Capability | Current Adex | This increment / remaining boundary |
| --- | --- | --- |
| Durable background work | Schedules, leases, fencing, checkpoints, outbox | Keep the existing system; unified activity projection |
| Long-running goals | Independent todos/schedules only | Owner-scoped goals, editable AI plan drafts, real linked todos and derived progress |
| Proactive feedback | Resource/version signals, threshold/quiet hours | Resolve, dismiss and snooze feedback with CAS; no parallel timers |
| Activity transparency | Runs/actions split across pages | Cached activity view with true Run states and original conversation links |
| Memory | Semantic extraction, 3 layers, tombstones, user CRUD | Preserve; not self-modifying agent code |
| Browser + credentials | Controlled browser broker, approval/effect ledger | Real XHS/Taobao login/purchases remain BLOCKED_EXTERNAL until accepted |
| Connectors | Google Calendar/Gmail adapters | OAuth configuration/review and real account acceptance remain external |
| Host isolation | Runner/network boundaries and service-scoped credentials | Not Muse's per-user VM, eBPF taint tracking or confidential VM; separate deployment/security work |
| Notifications | APNs, preferences, identical-result suppression | No claim of general semantic novelty detection or always-online Mac hosting |
| Personal avatar/wallet/multi-agent | Not implemented | Cosmetic avatar is lower priority; payment wallet/licensing/infra are not faked |

## Contracts and migration first

App migration 024 adds `assistant_goals`, `goal_tasks` (links to existing matrix_tasks),
and signal feedback status/snoozed_until/revision. Goals own organization, never Runs.
POST /goals accepts client UUID, title, outcome and up to 12 step titles; publishes
real todos atomically and idempotently. GET /goals includes owned task rows and
computed totals. PATCH /goals/{id} uses revision CAS for edits/archive; archive
preserves todos. POST /goals/plan returns a schema-validated model proposal only;
user edits/confirms before publishing. No external action is implied by a plan.
PATCH /signals/{id} uses revision CAS for OPEN/RESOLVED/DISMISSED/SNOOZED;
GET /signals hides closed/snoozed items by default, with include_closed for history.
Snooze is a read/dispatch eligibility timestamp, never a second scheduler.

## Implementation and acceptance

1. Add schemas/contracts and isolated owner/CAS/idempotency/progress tests.
2. Implement App organization and Agent read-only planning within four services.
3. Add compact white Goals / Activity / Suggestions navigation and cached reads.
4. Verify builds, native style/architecture/security gates, isolated integrations,
   synthetic responsive UI and signed iOS install. External fixture tests are not
   real OAuth/browser/payment/APNs acceptance. Publish actual limitations in docs.

Gmail metadata additionally filters obvious verification-code/password-reset/magic-link
subjects before ordinary agent context. This bounded deterministic filter does not
establish complete secret/prompt-injection detection and does not read mail bodies.
Snooze defers an observation in the UI and any not-yet-dispatched notification;
already accepted APNs cannot be recalled and are not automatically sent again.

When the user asks about goals, the ordinary App context includes a bounded,
owner-scoped active-goal progress projection. It is not L3 memory and cannot
resurrect archived goals or deleted todos. Agent may explain actual progress and
suggest next steps; it cannot mark work completed or authorize external actions.

## Observed acceptance (2026-10-19)

- `make build test check-style`: passed; Agent 95, Tools 124, Java App 11 /
  Automation 4, client 22; generated OpenAPI validates 98 operations.
- Owner/idempotency/CAS/goal-context/feedback integration: 13 passed in 26.56s.
- Final isolated full regression: **78 passed in 305.56s**, including existing
  scheduler/lease/fencing/recovery/approval/browser/file/memory tests.
- Full regression initially exposed cross-module use of the same loopback register
  rate window. Module-scoped test-only quota isolation now guards adex_test_* DBs;
  production registration limits are unchanged. Authentication inside each module
  still passes through the real HTTP limiter.
- Browser synthetic-data smoke at 375×812: one-line 54px tabs, 339px goal card,
  document/scroll width 375; activity opens the original /c/<id> conversation.
- Signed iOS Debug build succeeded. App migration 024 applied to local development.
  New external OAuth/browser/payment execution is not claimed by these fixtures.

Initial goals are user-confirmed plans and real todo progress. Autonomous pursuit,
automatic cross-domain replanning and generalized semantic novelty detection are
remaining work; existing explicitly requested schedules can run background reports.
