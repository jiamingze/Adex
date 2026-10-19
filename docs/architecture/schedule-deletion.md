# Permanent automation deletion

DELETE `/api/v1/automations/{id}?revision=N` forwards authenticated ownership to Automation DELETE `/internal/automations/{id}?revision=N` with schedule:write scope. Owner check and revision CAS precede deletion. Successful/repeated owned deletion returns `{ok:true,id}`; unknown/foreign IDs return 404; stale live revision returns 409.

Migration Automation 008 changes runs.schedule_id to ON DELETE SET NULL and occurrences.schedule_id to ON DELETE CASCADE. The schedule row and occurrence rows are physically removed. Existing execution/effect/checkpoint/outbox evidence is retained; pending/running/waiting runs are fenced and cancelled before detaching. Already completed external effects cannot be undone. A content-free tombstone (ID, owner, creation idempotency key) prevents delayed create retries from resurrecting deleted schedules (410 SCHEDULE_DELETED).

Lock order: owner+creation-key advisory lock, schedule row, Run rows, attempt rows. Scheduler uses schedule-first locking. Never hold a lock during external execution. UI confirms destructive deletion and removes a schedule only after the server receipt. This is separate from pause/cancel.

## Verification

- Focused real App/Automation/PG integration verifies physical schedule and occurrence removal, pending Run cancellation with epoch increment, detached completed history, stale revision rejection, owner isolation, repeat deletion and creation-key resurrection prevention. The isolated test database is required; no user task was deleted during development.
- Web UI test with explicitly synthetic data confirms the destructive confirmation, removal from the active list and absence from the ended list. This fixture test does not stand in for database deletion evidence.
- `make build`, `make test check-style`, OpenAPI generation/validation (99 operations), 26 client tests, architecture and secrets checks pass. Automation 008 applied locally, all four service readiness probes return 200. Existing public HTTPS DELETE rejects unknown IDs (404) and invalid revision (400).
- Signed iPhone overwrite install and launch succeeded with the same application database UUID.
- Full isolated stack regression: `uv run python scripts/test_stack.py` → **81 passed in 317.98s**, including three-scheduler contention, recovery/fencing and the new permanent-deletion test. External providers are deterministic fixtures, not real external execution evidence.
