# Conditional schedule notifications

Existing CHANGES_ONLY compares answer text, not user predicates. This increment separates conversation backfill from notification eligibility, using existing schedule/Run/checkpoint/outbox only.

Contract: schedule creation/draft accepts notification_policy EVERY_RUN | CHANGES_ONLY | CONDITION_MET and notification_condition `{description,operator,threshold,unit}`. Operator is semantic/lt/lte/gt/gte/eq; threshold is a finite decimal string, empty only for semantic. Numeric unit is required. Ambiguous price instrument/currency/unit must be clarified, never guessed. Model extraction interprets the original user request; ordinary timer parsing must not discard the condition.

Agent freezes tool evidence in the plan checkpoint, evaluates only exact quotations from that evidence, then stores `notification_assessment` in the immutable result checkpoint. Semantic predicates remain model judgments over cited evidence. Numeric predicates use deterministic decimal comparison; price evidence requires an actually rendered page rather than a search snippet, a matching unit and a quoted value. Missing/stale/invalid evidence yields UNKNOWN, never notification. Fetched time is not a guarantee of live exchange quotes; unsupported or ambiguous sources remain UNKNOWN. No real-price/provider acceptance is implied by fixtures. UNKNOWN results do not repeat an unverified model price; the conversation receives the explicit inability-to-verify status.

Automation owns the final notify decision. CONDITION_MET defaults silent unless a matching condition and valid MET assessment exist; numeric comparisons are rechecked by Automation. NOT_MET/UNKNOWN and failures still backfill the originating conversation through the existing outbox, with notify=false (no notification record/APNs). EVERY_RUN and legacy CHANGES_ONLY retain their behavior. Existing tasks are not automatically rewritten from historical prose.

No migration: rules fit existing schedules.task_request / runs.request; assessment and source evidence use existing immutable checkpoints. Tests must cover MET/NOT_MET/UNKNOWN, failed execution, replay dedupe and isolation using test DB only.

## Observed verification

- `make build test check-style`: passed; App 12 Java tests, Automation 5 (including independent notification gate tests), Agent 98, Tools 124, client 27; OpenAPI 100 operations; architecture/format checks passed.
- `uv run python scripts/test_stack.py tests/integration/test_conditional_notifications.py tests/integration/test_chat_productivity.py`: **7 passed in 86.33s**, covering real SQL schedule persistence, checkpoint commits, outbox delivery, conversation backfill, numeric false-positive rejection, MET/NOT_MET/UNKNOWN/missing assessment, failure suppression, replay dedupe and existing one-minute/interval behavior.
- Focused final conditional suite: **3 passed in 14.87s**, adding execution through the actual BackgroundWorker with unavailable search → immutable UNKNOWN assessment → conversation result, zero notification rows. This deliberately missing external service is not a real market-data acceptance test.
- Browser synthetic task list shows the condition policy. Source/model fixtures are explicitly marked TEST_FIXTURE and do not validate live gold quotes.
- No database migration. Local services updated. iOS web bundle built, but device build/install is BLOCKED_EXTERNAL because the connected iPhone became unavailable; existing mobile chat uses the updated backend routing. Existing automatic task policies are not rewritten.

## Updating existing schedules
PATCH /automations/{id} accepts revision plus status and/or notification_policy + notification_condition. Rules replace only notification fields, preserve other task_request fields, require owner and revision validation, and never rewrite immutable Run snapshots. A current conditional schedule rule is an additional completion gate, so an older EVERY_RUN execution without a matching assessment stays silent. No migration required. Operational repairs use authenticated APIs, never test writes against user data.
