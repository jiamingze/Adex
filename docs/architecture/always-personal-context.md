# Personal context without phrase gates

Authenticated chat reads the bounded owner-scoped task/note projection on every turn,
not only prompts matching a keyword list. Automation observations remain a bounded
owner-scoped HTTP read outside the App transaction; unavailable is distinct from empty.
Guest context remains excluded. No migration, no new state owner or scheduler.

Native authenticated chat attaches its already-authorized read-only 7-day/40-event
calendar observation regardless of wording. No implicit OS permission request. Device
calendar stays turn-scoped, excluded from L1/L3, and cleared on terminal states as before.
Missing calendar must not turn known tasks/notes into a blanket access refusal. Existing
context/source bounds, deletion filtering and owner authorization remain unchanged.

Tests: exact natural-language priority prompt, unrelated wording, owner boundary/deletion,
and prompt evidence for available tasks plus unavailable calendar. Fixtures do not prove
real iPhone calendar access or model compliance for all prompts.

## Observed verification — 2026-10-21

- `make format` and `make build test check-style`: passed (App 12, Automation 5, Agent 108, Tools 132; client tests, contracts and architecture checks passed).
- `uv run python scripts/test_stack.py tests/integration/test_personal_context.py`: **2 passed in 2.14s** after rebuilding service artifacts. Real isolated PG verifies the exact priority phrase, owner-scoped records, deleted-note exclusion, calendar idempotency/terminal cleanup and cross-owner rejection.
- Live qwen3.8-flash with explicitly synthetic two-task context used both tasks and did not return the blanket access refusal. This is one observed model sample, not a guarantee for every response.
- iOS signed build, overwrite installation and launch succeeded with existing app data retained. Real private calendar contents were not printed or copied into tests. Device calendar event selection still depends on OS authorization/data availability; no claim that an unauthorized calendar was read.
- Secret scan and whitespace checks passed. No migration. App and Agent restarted after verification.
