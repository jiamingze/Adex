# Qwen Flash default

The default Qwen chat/background/memory provider uses qwen3.8-flash. UI and new
message contracts send that identifier. The historical qwen3.8-max selector remains
accepted as a compatibility alias to the configured Qwen provider for installed clients;
it must never accidentally select MiniMax. MiniMax remains an explicit option.
No database migration. Model IDs do not grant credentials or override deployment URLs.

Mobile API URLs are bundled at build time. An expired Quick Tunnel requires a new
healthy URL and a rebuilt iOS app. Quick Tunnels are temporary, not a stable hosting SLA.

## Verification — 2026-10-21

`pnpm generate:contracts`, `make format`, `make build test check-style` passed:
App 12, Automation 5, Agent 107, Tools 132; formatting/architecture checks passed.
Provider transport tests cover Flash, configured Max, and Flash default. Secret scan passed.
iOS bundle and signed generic-device build passed. Public login, account read and logout
returned HTTP 200 after restoring the expired tunnel. Real qwen3.8-flash invocation returned
HTTP 400 / Arrearage, including the retry after the user reported recharge; external
model execution remains BLOCKED_EXTERNAL until the account/provider accepts a request.
No successful model execution is inferred from configuration or fixture tests.
