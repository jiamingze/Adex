# Semantic conversational memory (M03 extension)

The Agent model decides whether a user turn contains durable information and rewrites
it into concise, standalone facts. There is no production keyword/command grammar.
For example, “平常真不爱吃辣，推荐吃的时清淡点哈” can become
“用户偏好清淡、不辣的饮食；推荐餐厅和菜品时避免辛辣。” A temporary business
trip is not a permanent home-city update. Task status, schedule configuration and
execution receipts remain owned by their business domains, not long-term memory. Contradictions reference the old memory's
ID/revision, while semantic duplicates should produce no operation. Ambiguity asks a
question. Quoted/web/tool instructions cannot authorize a write.

## Ownership and migration

Exactly four business services remain. App owns memory, consent policy, source
provenance, corrections, tombstones, revisions and index outbox. Agent proposes only.
App migration `019.sql` adds `memory_turn_plans`, keyed by existing Turn ID: immutable
input snapshot, validated model proposal, receipt and applied timestamp. No new task
scheduler, external effect ledger or public API is introduced. The old regex parser
and its production routing have been removed; regex-based synthetic fixtures exist
only under the mock model and are not evidence of real semantic behavior.

## Internal contract

App → Agent `POST /internal/agent/memory-plan`, App-issued `memory:plan` capability
bound to owner and Turn. Request: `{owner_id,turn_id,snapshot,model}`. Snapshot contains
latest user text, up to six recent messages after the forgetting watermark, up to 200
active memories with IDs/revisions and the authoritative memory revision. Existing
facts are truncated to 600 characters with a truncation flag; the aggregate fact view
is capped at 18,000 serialized characters. User turns over 12,000 characters skip
automatic extraction rather than silently extracting from a partial message. No
large-input or unlimited-memory performance guarantee is made.

Response: `{mode: none|learn|manage, operations: [...]}`. Each of at most three
operations has `operation` (save/correct/forget/clear/list/clarify), normalized `content`,
exact-current-user `evidence`, `confidence`, `category`, and optional `target_id` /
`target_revision`. The Agent validates strict Pydantic schemas. App independently
checks evidence, owner, target revision, current memory revision, live Turn lease /
epoch / attempt, safety restrictions and tombstones. Model output is not a receipt.
All candidates are validated before any batch writes; unclear/mixed management actions
cannot partially modify memory.

The existing invocation ledger accounts for and deduplicates semantic inference.
A planner timeout or malformed output becomes a durable no-op, never raw-text fallback
or a blind paid retry. A memory-enabled registered-user turn incurs one additional
model call; its bounded 25-second phase precedes ordinary answer generation. This adds
latency and cost and has no large-scale SLO claim. Missing external credentials can
block semantic assessment; ordinary answers can continue without saving memory.

## Commit and recovery

Lock order remains user → conversation → Turn. No model/network call occurs under a
PG lock. Input is frozen before paid inference; a changed revision cannot authorize an
old proposal. Explicit management commits mutation and assistant receipt atomically.
Incidental learning is committed with the normal assistant completion; cancellation,
failed streams or stale attempts cannot save it. App appends normalized-memory receipts
to the final durable reply. Turn identity and transaction rollback protect duplicate
sends/restarts. Audit proposal rows do not authorize re-execution.

Corrections preserve old tombstoned rows and source provenance; memory revisions
invalidate L1 context and stale responses. Summaries are built by the existing worker
without a second memory writer. Old extraction jobs cannot resurrect deleted facts.
This retains exact-hash tombstones and source/watermark defenses; it does not claim
perfect semantic erasure of every possible future paraphrase. Ordinary recall still
uses the existing bounded latest-20 confirmed facts, not unlimited semantic retrieval.

## Privacy and user control

The existing memory-enabled setting controls learning; disabled and guest accounts
skip semantic inference and cannot write memory. Passwords/keys are prohibited. The
planner rejects automatic sensitive-profile inference; App adds independent checks for
credentials, identifiers and other high-risk content. Users can inspect/correct/delete
facts on the memory page or request semantic management in chat. Deletion retains
historical conversations and audit records according to existing retention behavior;
it is not account-wide data erasure. Stored user preferences are data, never tool
permissions or authority to bypass approvals. This is persistent personalization,
not model-weight training or self-modifying code.

## Verification

Commands: `make build`, `make test`, `make check-style`, `make test-integration`,
`uv run python scripts/check_secrets.py`. Isolated integration tests cover normalized
implicit preferences, cross-conversation recall, duplicate sends, source provenance,
semantic correction, transient and quoted content, invalid/forged proposals, sensitive
content, opt-out, guest restrictions, owner-scoped clearing and cancelled-answer
non-commit. Test fixtures are synthetic, with mock inference clearly labelled.

Separate direct real-provider checks (synthetic inputs only, no personal-memory DB
writes) observed: unformatted dietary preference → normalized fact; one-day business
trip → no-op; relocation → correction targeting the supplied old ID/revision; combined
dinner request + preference → learn mode rather than swallowing the normal response.
These are limited samples, not a guarantee of perfect extraction or classification.

No iOS bundle changes are required. Existing chat completion reloads the durable
answer, including App receipts; restarting the upgraded backend activates the feature.

Observed validation on 2026-10-16: `make build`, `make test` (Java 9, Agent 44,
Tools 63 plus client and 90-operation OpenAPI checks), `make check-style`, Ruff lint,
secret scanning and whitespace checks passed. Final full isolated integration run:
**54 passed in 126.45 seconds**. A PostgreSQL outage test now verifies all four
service pools recovered before subsequent feature checks, rather than App alone.
Direct real-provider synthetic checks also preserved “heavy flavor but no spicy food”
without inventing a preference for light food. Local migration 019 was applied and
all four readiness endpoints returned HTTP 200; no test facts were written to the
user database. Targeted isolated debugging is available with
`uv run python scripts/test_stack.py tests/integration/test_semantic_memory.py -q`.
