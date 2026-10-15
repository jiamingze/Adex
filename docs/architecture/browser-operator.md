# Generic browser operator — implementation contract

## Actual gap

Before this change browser access was stateless/read-only. This implementation adds
interactive sessions, secure takeover, a page-action broker, request approvals and waiting Runs.
Existing shared action approvals/effects, Agent checkpoints, Automation leases and
outbox are authoritative and must be extended, not replaced. No per-site Skills.

## Migration list

- Tools 007: owner/Run-bound browser sessions, encrypted browser state and pending
  request material, revision and runtime binding. Existing approvals/effects reused.
- Automation 006: outbox logical delivery keys so waiting and final events can both
  reach the original conversation. WAITING_INPUT uses the existing Run/attempt tables.
- No new business service, task scheduler, credential service or artifact filesystem.
  Screenshots are transient authenticated responses; browser state is encrypted JSON,
  not a public file. App still owns persistent files and media.

## Contracts

App endpoints: GET `/browser/sessions`; POST `/browser/sessions/{id}/control`
with bounded human operations; POST `/browser/sessions/{id}/resume`; POST
`/browser/sessions/{id}/close`. Owner authentication precedes Tools calls.
Session snapshots expose URL/title/screenshot and redacted AX observations, never
cookies, passwords, raw CDP or arbitrary JavaScript. Human mode pauses Agent actions.

Agent uses Tools `/internal/browser/operator/ensure`, `/{session}/observe`, `/{session}/step`; dispatch uses existing `/internal/actions/execute`;
all Agent mutations require live Automation Run/epoch/attempt authorization. Step
handles bind to a current observation and backend DOM node, not site-specific XPath.
Model output is constrained JSON, not executable code. Supported actions are navigate,
click, type, select, scroll, back, upload, switch_tab and handoff. No site scripting tools.

Every non-read HTTP request in Agent mode is held before sending. The immutable
request digest, originating page/form preview and destination become an existing
Action Approval. User approval resumes the same Run. Effect IN_FLIGHT and approval
UNKNOWN are committed before the held request is released. Lost browser requests are
not replayed. HTTP success alone is submitted/unverified; business success requires
independent response/readback evidence. Unknown results remain UNKNOWN and block
blind re-execution. Critical GET gestures are also gated; ambiguous actions require
human review. This is defense in depth, not proof that all websites implement GET safely.

Browser contexts are per owner/Run. Secure manual input goes only to the broker, not
model/checkpoint/logs. Login may be done by the user in takeover mode; user can resume
or revoke the session. Cookies persist only in an encrypted vault envelope. Public-DNS
pinned egress rejects private destinations; login/navigation domains remain visible.

## Implementation and acceptance

1. Contracts/migrations and policy tests.
2. Controlled persistent Chromium broker and encrypted Tools session service.
3. Existing Run suspend/resume/outbox and generic Agent observation/action loop.
4. App authenticated gateway and mobile takeover/approval interface.
5. Isolated PG/HTTP and local-browser tests, build/style/security gates, public-page
   smoke, then device packaging where available.

Real Xiaohongshu publication, Taobao orders and payment remain BLOCKED_EXTERNAL until
an authorized account/merchant flow has been exercised and a verifiable receipt obtained.
Mock/local fixture success is never evidence of real publication, purchase or payment.
There is no universal success guarantee: CAPTCHA, merchant policy, MFA and unusual
widgets can require human takeover. Existing read-only browsing remains independent.

## Operating guide and boundaries

Open Assistant → Browser, provide a public HTTPS URL and instruction, or ask in chat
(e.g. “帮我在这个网址准备并发布文章 …”). Browser tasks require a registered user.
Select the task to see its page, take over login, and return control after the Run
has suspended. Secure input is sent to the broker; do not put passwords in chat.
The model receives redacted accessibility observations, never credentials or screenshots.
Popups are bounded to six tabs. Native browser dialogs require explicit human input.
Uploads use owner-authorized App File API content (5 MB maximum).

Set `ADEX_BROWSER_ENCRYPTION_KEY` to a dedicated random base64 32-byte key before
starting Tools; setup generates it for new installations. Missing key disables operation.
Keep the key in the deployment secret store. Rotation requires re-login; do not delete
it while sessions are expected to remain recoverable. “Remember login” is explicit,
encrypted and expires after seven days; one profile per user/domain. Revocation fences
stale saves and closes linked sessions. This clears Adex access, not the website’s own
server-side login session. Context storage may contain authentication cookies, not passwords.

Session runtimes are process-local and capped at four contexts, with 20-minute idle
cleanup on allocation. Multi-instance Tools deployments need session-affine routing.
A lost runtime requires explicit restore/takeover; an UNKNOWN write is never replayed.
A resource-command CAS prevents simultaneous controls; Automation remains the sole
Run scheduler and recovery authority. Headless Chromium uses sandboxing, the pinned
public-egress proxy and existing runner resource limits. Use container isolation in
production; local development is not a hardened hostile multi-tenant browser sandbox.

All mutating requests can include website analytics and intermediate writes, so complex
sites may require several approvals or human takeover. Binary/unparseable payloads
cannot be approved by the automated path. Request digests bind exact bytes, but generic
semantic understanding and readback verification are conservative heuristics, not a
universal payment or website adapter. GET side effects cannot be ruled out generically.
Only recognized business IDs newly present in independent same-site readback yield a
verified receipt; HTTP 2xx alone remains unverified. No payment-settlement verification
is implemented. MFA, CAPTCHA and payment authentication are human responsibilities.
Prompt-injected pages cannot approve requests or access a JavaScript/shell tool.

## Verification

`make test`, `make check-style`, `make test-integration`, web build and secret scanning
cover routing, narrow tool contracts, credential redaction, stale-page rejection,
real local Chromium request holding/release, owner isolation, profile revocation,
same-Run suspend/resume, outbox backfill and UNKNOWN reconciliation without resubmit.
The three operator integration scenarios use isolated PostgreSQL, mock planning and
an explicitly labelled local publisher fixture. They are not real merchant tests.

Real external publication/purchase/payment: **BLOCKED_EXTERNAL**. An operator must
validate each target flow with an authorized account and explicit final approval
before representing that integration as supported in production.

### Observed validation (2026-10-15)

- `make build`: Java package and TypeScript/Vite production build passed.
- `make test`: client suite, Java 9 tests, Agent 42 tests, Tools 62 tests and
  OpenAPI 90 operations passed. Subsequent Tools regression including malformed
  request-body handling: **63 passed**.
- `make check-style`: Spotless, Ruff formatting and architecture checks passed.
- `make test-integration`: **48 passed in 98.54 seconds**, including three operator flows.
- `uv run ruff check services/adex-tools/src/adex_tools/browser services/adex-tools/src/adex_tools/api/browser.py services/adex-agent/src/adex_agent/browser`: passed.
- `uv run python scripts/check_secrets.py` and `git diff --check`: passed.
- Direct real Chromium observation of `https://docs.python.org/3/`: title
  “3.15.0 Documentation”, 213 accessibility nodes, no pending write. This verifies
  public navigation only, not any login or merchant transaction.
- Mobile UI at 390×844: document/body width stayed 390px with normal and zoomed
  preview. iOS device build/install/launch succeeded; on-device merchant flows untested.

Reproduce the synthetic screenshot UI without private data:
`pnpm --dir apps/web build`, then
`uv run --project services/adex-tools python tests/fixtures/browser_operator_server.py`.
Open `http://127.0.0.1:18118/assistant` → Browser → synthetic session.

![Synthetic mobile browser takeover](../images/browser-operator-mobile.jpg)
