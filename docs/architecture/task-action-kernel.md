# Task action kernel — M02/M04 correctness hardening

## Observed gaps

InteractiveTurnService currently gates schedule/todo writes with keyword checks and
has no chat-to-schedule-update tool. A normal model completion is free text. Existing
App receipts do not perform an independent schedule readback. A PATCH retry after a
lost response hits a stale revision instead of replaying the committed command.

## Source study

Reviewed openai/codex at commit `deede7201da27a178c39befa6b4959bb7d451645`:
`codex-rs/core/src/tools/router.rs`, `registry.rs`, `orchestrator.rs`, `parallel.rs`
and `gpt-5.2-codex_prompt.md`. Patterns: named tool registry, typed arguments, explicit
failure/cancellation boundaries, separate execution outputs, bounded orchestration.
[Official harness overview](https://developers.openai.com/blog/codex-as-a-platform).
This is an independent adaptation in Adex, not a vendored Rust runtime or its private
prompts; no OpenAI model/key dependency, shell access or new business service is added.
No source/prompt text is copied; Codex upstream is Apache-2.0, Adex remains MIT.

## Contracts and implementation plan

1. Agent semantic task-tool router receives the authenticated user's request and bounded
   owned task snapshots; tools: schedule.create/update/list, todo.create/update/list.
   Strict schemas, one mutation per turn, ambiguity -> clarification, not guessed IDs.
   Bounded argument-repair round; freeze tool proposal before dispatch using the existing
   immutable interactive plan/result tables. Ordinary chats stay on App->Agent SSE.
2. Agent emits `task.action.requested` with `{tool,target_id,arguments}`. This is only
   a proposal. App authenticates via the current Turn's owner/conversation, checks live
   epoch/attempt/lease, uses capability services, reads back persisted records, and alone
   produces a task success receipt. Model prose is never evidence of success.
3. App migration 028: per-Turn task action request hash and durable receipt; local todo
   changes and receipt commit together; cross-service writes recover through stable
   command keys. No lock held across LLM/browser execution or remote network calls.
4. Automation migration 009: owner+command-key schedule mutation receipt inside the
   same schedule update transaction. Replay returns original receipt before revision
   validation, key/hash mismatch rejects, schedule deletion cascades cached responses.
   Existing occurrence/lease/fencing/checkpoint/outbox is unchanged.
5. Failure/UNKNOWN cannot produce success. Read-after-write mismatch surfaces an error.
   Final free-text task mutation claims without receipts are rejected. Cancellation can
   prevent new dispatch; already-dispatched remote work may commit and must be reconciled
   through the stable key, never represented as rolled back by a model.
6. Tests first: semantic paraphrases, ambiguity, malformed-tool repair, ownership, replay,
   timeout-after-commit, stale epoch, future firing and no fabricated task success. All
   integration mutations use isolated test PG. Live model tests use synthetic data.

## Boundaries

One mutation per conversational turn is intentional; compound unrelated writes require
clarification rather than partial silent execution. Other existing browser/media/skill
workflows keep their own typed adapters and approvals. This increment does not implement
arbitrary code execution or claim a drop-in Codex app-server integration.

## Long-horizon work (same Run, no second scheduler)

`workflow.start` accepts `{goal, acceptance: string[1..12]}` and creates an idempotent
RESEARCH Run with `params.agent_loop=true`. App reads the owned Run back before returning
“started”; this is not a completion receipt. The worker dynamically plans `search/read/finish`
steps, retains a compact working summary plus the actual observation transcript, and saves
an immutable checkpoint before dispatch and after each observation. Automation alone
commits checkpoint references with the existing epoch/attempt fence. Recovery continues a
pending read rather than restarting completed steps. Unknown paid model invocations keep
the existing invocation-ledger reconciliation rules; no blind paid retry is added.

The 24-step budget survives recovery, with a repeated-query breaker and bounded model
context. Final status is PARTIAL unless every requested acceptance item has an observed
source and all cited URLs belong to the transcript. This validates evidence provenance,
not the truth of every assertion. Tool errors and budget exhaustion remain explicit.
Only read tools are admitted here. Arbitrary multi-step write transactions, purchases and
publication are not implemented by this research loop; existing browser Action Approval,
effect ledger and UNKNOWN reconciliation remain required. No automatic “success” fallback.

## Autonomous memory

Every eligible normal turn already uses the semantic memory planner, not a “remember:”
regex. This increment adds bounded schema/evidence repair and semantic recall IDs to the
same proposal, without a second model roundtrip for retrieval. Corrections must bind an
observed ID/revision; automatically learned facts are normalized, atomic, supported by
the latest user statement, and cannot delete memories. App still enforces sensitivity,
consent, ownership and tombstones. Recall re-reads current PG records and checks the
frozen plan's memory revision, so deleted or concurrently forgotten memories cannot return
through a model ID. Up to 200 bounded candidates are considered; this is not unlimited
semantic/vector retrieval. Long-workflow working summaries stay separate from L3 personal
facts. Global conversation compaction remains the existing extractive implementation.

## Database migrations

- App `028.sql`: durable per-Turn action request hash/state/receipt, deleted with conversation.
- Automation `009.sql`: replayable owner-scoped schedule mutation command receipts.
- No new service, schedule store, memory store or checkpoint table.

## Reproduce validation

```sh
make build test check-style
uv run python scripts/test_stack.py
# Explicit paid Qwen calls; synthetic inputs only, no application DB writes:
uv run --project services/adex-agent python scripts/evaluate_agent_kernel.py --live
uv run python scripts/check_secrets.py
```

The isolated stack uses deterministic model/search/browser fixtures and real PostgreSQL,
HTTP authorization, task/Run records, checkpoints and outbox. Fixture runs prove internal
execution/recovery behavior, never real external publication, shopping, calendar changes
or media generation. The live evaluator separately checks real semantic routing, normalized
learning/correction and recall against synthetic snapshots. It does not prove arbitrary
real-site long workflows. Missing external credentials/services remain BLOCKED_EXTERNAL.

Task editing also uses an inset grouped mobile layout, top cancel/save navigation,
bounded date/time controls, no autofocus and an independently scrolling form. Synthetic
390×844 browser checks cover save/reopen, scrolling and no horizontal overflow; they are
not a substitute for iPhone keyboard/device testing.
