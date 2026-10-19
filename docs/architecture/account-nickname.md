# Account nickname

App owns `users.nickname`, an optional, non-unique display name (empty string means use login username). Migration App 026 adds a non-null string, at most 40 Unicode code points. Nickname changes never rename login identifiers, tokens, ownership, memories or conversations.

GET `/api/v1/me` includes `nickname`; PATCH `/api/v1/me` accepts only `{nickname:string}` and returns the updated profile. Authentication resolves the current owner; request-supplied owner/username/role fields are rejected. Guests cannot modify account nicknames. Trim edge whitespace; reject control characters and more than 40 code points. Clearing is supported. Single-field updates use last-write-wins, without overwriting other user settings.

The greeting, sidebar identity and avatar use nickname first and username as fallback. Settings → 常规 exposes an independently loaded account nickname editor. Profile snapshots are session-local, reset on authentication changes, and updated from a successful server receipt; failures leave existing data intact. Nicknames are escaped React text, not HTML or instructions.

Verification: isolated PG account update/reload/login persistence, clearing, validation, owner isolation and guest denial; browser test with synthetic profile data; build/style/contracts and native device build/install. Never modify the user's actual nickname in tests.

## Observed checks

- `make build`, `make test check-style`: passed (App 12 / Automation 4 Java tests, Agent 96, Tools 124; OpenAPI 100 operations; formatting and architecture checks).
- `node scripts/test_client.mjs`: 27 passed, including nickname/fallback/guest display behavior.
- `uv run python scripts/test_stack.py tests/integration/test_account_nickname.py tests/integration/test_core.py`: 6 passed in 8.24 seconds. A final focused nickname run also verifies the other account's entire profile remains unchanged.
- Synthetic browser flow: save 星河 → sidebar updates immediately → Today displays 早上好，星河. Only disposable fixture data was changed.
- App 026 applied locally; all four readiness probes return 200; existing public HTTPS profile read returns 200 with the nickname field. Real user's nickname was not modified by tests.
- Signed iPhone build and overwrite install succeeded. Launch was blocked by the device lock; unlock and open Adex to use Settings → 常规 → 昵称.
