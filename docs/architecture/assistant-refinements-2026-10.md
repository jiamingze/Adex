# Assistant refinements: notes, schedules and proactive delivery

## Gaps and contract

- Notes currently render Markdown source in an always-active editor. Default to the
  existing safe Markdown renderer; explicitly switch between source editing and preview.
  Stored source and revision-based save API remain unchanged.
- Chat routing handles only ONCE/DAILY, although Automation supports INTERVAL.
  Add bounded minute/hour interval grammar (including min/h), and carry validated
  interval_seconds through the same durable schedule creation path. A successful
  response must carry an Automation schedule ID; model text is never a receipt.
- Notification resume currently waits for history pagination. Paint each received
  page immediately and retain owner-scoped in-memory snapshots during navigation;
  revalidate asynchronously. Authentication and resume ownership checks remain mandatory.
- Existing connector signals deduplicate resource/version and apply importance and
  quiet-hour preferences. Add explicit unchanged-result notification policy for
  interval checks, preserving origin-conversation results and durable outbox delivery.
  User-requested recurring reports still notify on every execution by default.

## Migration and safety

No new service, scheduler or database migration is planned: schedule task_request
JSON carries notification policy; existing result/notification transaction deduplicates
Run results. Credentials stay outside prompts, writes retain action approval and
UNKNOWN reconciliation. External website text cannot grant permissions.

## Verification

Parser/negative tests, durable chat schedule and duplicate-submit integration tests,
notification-policy integration tests, Web build, Java/Python tests, style/architecture
and secret checks. Real APNs display/tap latency requires a connected physical device;
fixture delivery is not proof of Apple delivery.

References: https://introducing.muse.ai/ and
https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse

## Implemented limits

The interval chat path now accepts `每10min` / `每隔十分钟` / `每2小时`.
Unusual timing uses a schema-validated semantic proposal, not a plain model claim.
Unsupported/ambiguous timing asks for clarification. All writes remain in App →
Automation with a turn-stable idempotency key and the existing occurrence uniqueness.
`巡检` / explicit change requests select `CHANGES_ONLY`; other reports use `EVERY_RUN`.
Change-only currently suppresses *identical consecutive result text* (trimmed), not
semantic equivalence of arbitrary web pages; reworded model results can still notify.
Both executions remain in chat. Existing connector resource/version deduplication,
importance thresholds, quiet hours and approval enforcement are preserved.

Resume adds optional `include_run=false` (default true for compatibility), returning
owned conversation/run/action IDs without an Automation round trip. Message reads
add `latest=true` (default false), returning the latest bounded page in ascending
order. UI paints it before asynchronously loading earlier history. Up to five
conversation snapshots stay in memory only, clear on session changes and local
delete, and always revalidate. This is not a cross-account persistent cache.

## Observed verification (2026-10-19)

- `make build`, `make test`, `make check-style`: passed; Agent 94, Tools 122,
  client 22, Java App 10 / Automation 4; OpenAPI 93 operations.
- `uv run python scripts/test_stack.py`: 74 passed in 307.17 seconds on isolated
  PostgreSQL + Redis + three scheduler instances and explicit external fixtures.
- After scheduled evidence-routing refinement, chat interval/receipt integration
  rerun: 2 passed in 10.72 seconds (3 unrelated cases deselected).
- Browser synthetic-data smoke: Markdown heading/table, source/preview toggle,
  no script nodes in preview, no document horizontal overflow at 541px width.
- Signed iOS Debug build and overwrite install succeeded; actual push tap latency
  and external-source semantic quality remain device/provider acceptance work.
- Markdown toggle is an icon immediately before Save, with accessible label/title;
  reading uses a pencil icon and editing uses an eye/preview icon.
