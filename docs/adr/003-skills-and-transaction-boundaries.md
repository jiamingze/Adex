# ADR 003 — Versioned skills and transaction boundaries

Status: accepted, 2026-10-11. Scope: Agent capability extension, Travel Skill v1,
future Tools-owned booking adapters. No new business service or public API.

## Decision

A Skill is a trusted, versioned definition plus a typed plan compiler. It describes
stages, capability requirements and quality policy. It does not grant permissions,
load remote code, bypass budgets, or replace the existing runtime. Built-ins ship
inside the Agent package; arbitrary uploaded SKILL.md files are not executable.

`SkillRegistry` selects a skill from user requests. `SkillPlan` contains bounded
read queries and trusted policy. `ContextService` compiles the plan into the model
prompt and executes reads through existing owner-scoped Tools calls. Existing
interactive plans freeze the actual prompt, skill ID/version and collected evidence
before paid model invocation; background plan checkpoints retain the same compiled
messages. Retries reuse stored messages, rather than silently applying a new skill.
Deleting memory still changes the authoritative revision and fences stale execution.

Travel v1 uses two sequential, budget-checked search reads for guides/routes and
opening/reservation/transport requirements. If the second fails, the first remains
usable, with explicit partial/unverified metadata. Requested day counts replace the
old fixed four-day policy. Explicit follow-up edits can retain recent travel context;
unrelated conversation does not inherit travel policy. Preferences come only from
the existing owner-scoped memory context. Planning stays in ordinary chat unless the
user explicitly requests background work.

## Quality boundary

Route grouping, travel buffers, opening hours, accessibility and weather alternatives
are required planning policy. This version does not have a map routing solver,
structured itinerary persistence or an independent semantic itinerary evaluator;
prompt instructions are not proof that every generated itinerary satisfies them.
The compiler tests enforce day-count handling, bounded reads, permission rejection,
continuation and failure behavior. Real supplier/map acceptance remains separate.

## Transactions: research is not purchase authority

Current hotel/attraction transaction capabilities are `BLOCKED_EXTERNAL` and false.
Tools travel evidence exposes this explicitly. Agent policy prohibits claiming orders,
reservations, charges or order IDs and offers verified official entry points instead.
No browser checkout automation or payment/identity forwarding is enabled.

`BookingQuote` / `BookingProvider` define the future adapter boundary. A quote binds
owner, supplier, product, verified inventory, currency, total, expiry and terms hash.
These types alone do not enable submit or constitute user approval.

Before enabling any supplier, implement and test this state-owner workflow:

1. Tools fetches a concrete supplier quote including dates, party/room selection,
   cancellation terms, fees and availability; normalize and hash the complete payload.
2. App displays a review card. The human approves the specific immutable snapshot;
   chat text or model assertions must not count as approval. Approval is owner-scoped,
   expiring, revocable, and bound to quote/payload hashes. Repricing requires new consent.
3. Tools checks that approval and quote are current, permissions valid, and budget
   acceptable, then atomically consumes/dispatches the effect under a stable effect key.
   Reuse existing durable approval/effect invariants, not in-memory confirmation flags.
4. Submit happens outside database locks. Persist supplier request/order IDs and use
   Automation lease/epoch/attempt fencing for background work. Timeout yields UNKNOWN;
   query supplier status before resubmitting. Unsupported external exactly-once is never
   promised. Post-dispatch cancellation is a separate supplier operation, not rollback.
5. Provider receipt—not model prose—creates the order result, App artifact/audit and
   Outbox delivery. Sensitive identity/payment material stays out of prompts, logs and
   checkpoints; add explicit retention and authorized supplier transport.

The current CalDAV approval implementation is calendar-specific. Do not send booking
payloads into it or expose BookingProvider.submit until a booking-specific durable
approval and effect path passes these gates.

## Evolution

Next: typed itinerary schema and constraint evaluator → map/travel-time adapter →
licensed availability/quote adapters → review/approval UI and supplier sandbox tests →
booking submission/reconciliation/cancellation. Multi-agent collaboration should be
added only when measured quality or parallelism benefits justify it. Skills are not
an excuse to split more microservices or allow unrestricted tool loops.
