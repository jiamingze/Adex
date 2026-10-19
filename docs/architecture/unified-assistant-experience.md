# Unified assistant experience

## Gap and implementation contract (2026-10-20)

The existing Today projection knows tasks/calendar, while ordinary chat receives memories and selected goals only. Navigation separates todos and automation; duplicate approvals consume the Today list. Notes and generated artifacts are disconnected in navigation.

This increment keeps the four services and all existing persistence/recovery contracts. It introduces no scheduler; the only migration (025) adds transient native calendar observation fields: all new information is an owner-scoped, bounded **read projection** over existing records. Existing `/matrix`, `/tasks`, `/notes`, and conversation links remain valid.

- Navigation: 今日 / 对话 / 任务 / 资料. Tasks share a sub-navigation for todos, automation, and execution history. Materials expose notes and existing generated artifacts.
- Today: group pending actions by kind and uncertainty state for display only. Expand groups to inspect individual actions; never aggregate consent. Evening planning targets tomorrow and reads the matching calendar window.
- Chat: display Adex as the brand, with model choice in a secondary control. Relevant questions receive current owner-scoped todo and note projections; automation is read through its owning service outside the App transaction. Snapshot data is untrusted reference material, never authorization or proof of execution. Failed reads remain unknown.
- Calendar: connected Google Calendar remains permission-scoped. iPhone calendar is read on relevant chat requests only when OS permission was already granted; missing access is unknown rather than an empty calendar.
- Tasks: local-day deadline groups, restrained priority badges, active/history separation. Existing revision CAS remains authoritative.

## Verification

Client tests cover routing, deadline groups, approval grouping and evening calendar boundaries. Integration tests check owner isolation and bounded personal context. Run build, tests, style and architecture checks, then inspect mobile layouts with synthetic data. Mock browser/provider tests do not demonstrate real external execution.

## Follow-up boundaries

Gesture sorting, tags/favorites, cross-domain autonomous replanning require separate contracts. They must not be advertised as complete in this increment.

### Native calendar bridge

Migration `app/025.sql` adds transient `turns.client_calendar` and permanent payload hash `calendar_hash`. `MessageInput.client_calendar` is optional: source=device, observed_at, IANA timezone, partial flag and at most 40 events (title/start/end/all_day/location/organizer). Unknown fields and invalid intervals are rejected. A relevant user question on iPhone reads **previously granted** Calendar permission without prompting. No access means no observation, never an invented empty calendar. Server validates payload; Agent uses observations at most 15 minutes old. Terminal/cancel/delete clears the turn payload; the idempotency hash remains. The snapshot bypasses Redis L1. Model invocation evidence follows existing Agent retention; this is not an L3 memory write. Google Calendar still uses the existing connector path.

## Observed checks

- `make build test check-style`: successful; App 12 Java tests, Automation 4, Agent 96, Tools 124, client 24. OpenAPI 98 operations; architecture check passed.
- `uv run python scripts/test_stack.py`: **80 passed in 323.92s** against isolated PostgreSQL/Redis, three schedulers and deterministic external fixtures. This is not evidence of real third-party browser execution.
- Focused context/goal integration: 5 passed. Native payload retry hash, terminal cleanup, invalid payload rejection, and wrong-owner context access verified.
- Mobile browser 375×812 with synthetic records: five uncertain browser actions aggregate into one expandable row with five individual links; navigation and automation filters remain visible; document scroll width is 375px.
- Local and existing public HTTPS login, matrix, notes, automations, artifacts and files: HTTP 200. App 025 applied to local development environment.
- Signed iOS device build succeeded. Actual Calendar OS access remains dependent on the user's existing permission; automated fixture tests do not substitute for that device interaction.
- Final iPhone overwrite installation and launch succeeded; device application database UUID remained unchanged. The native calendar permission interaction itself was not simulated as real device evidence.
