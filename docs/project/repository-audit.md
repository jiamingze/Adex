# Repository onboarding audit · 2026-10-16

## Evidence before changes

Public GitHub metadata: repository created 2026-10-11; 1 star, 0 forks, no topics,
no homepage, no releases and no open issues at audit time. These are a snapshot,
not evidence of why an individual chose not to use the project. Traffic/referrer
analytics and user interviews have not been collected; no growth guarantee is made.

The last five CI runs failed. The latest
[verify job](https://github.com/jiamingze/Adex/actions/runs/38821311905/job/116718281021)
failed during `make setup`: pnpm invoked the iOS package's automatic `prepare`
lifecycle hook, which required the maintainer's ignored `.local-data/public-url.txt`.
A fresh Web/backend contributor hit the same failure without needing iOS at all.
All four image-build jobs succeeded, but that does not validate application tests.

## Repair scope and acceptance

1. Make iOS bundling explicit, preserve endpoint validation, and make a fresh
   dependency installation work without `.env`, a tunnel, Xcode or signing.
2. Put product value, mobile examples and two distinct entry points (synthetic UI
   preview versus real self-hosting) near the top of both README languages.
3. Give contributors bounded starter tasks, clear reporting paths and community
   expectations. Improve About/topics using implemented capabilities only.
4. Verify clean-install/build/test gates locally and observe the resulting GitHub
   CI. Keep fixture demos and unvalidated external execution clearly labelled.

No business API or database migration; four-service architecture is unchanged.
A release is not a substitute for a passing fresh-install workflow. External account
publishing, APNs delivery and merchant compatibility retain their existing blockers.

## Follow-up measurement

Use GitHub Insights → Traffic to compare unique visitors/clones and referring sites
before/after an announcement, respecting GitHub's limited retention. Track first-run
failures and contributor response time as well as stars. Publish a short real workflow
recording and a source-only prerelease once CI is green and limitations are reviewed.
Promotion to outside communities needs a separate publication decision; this audit
neither posts unsolicited messages nor manufactures engagement.

## Reproducible local checks

- A clean `git archive` checkout, with the iOS lifecycle fix applied, completed
  `pnpm install --frozen-lockfile` and `pnpm --dir apps/web build` without `.env`,
  `.local-data`, Xcode or signing. No private runtime data was copied.
- `uv run pytest tests/scripts -q`: 6 passed, covering missing endpoint guidance,
  explicit endpoint precedence and rejection of credential/query/path origins.
- `make demo-ui`: served the synthetic Today page at loopback port 18117 and was
  exercised in a browser. This is a UI preview, not a functioning model demo.
- 97 local documentation/image link targets checked with no missing paths.

## Intended repository metadata

About: “Self-hosted personal AI assistant for Web & iOS. Semantic memory, daily
planning, durable tasks and approval-based browser actions. Java + Python + React.”

Topics: `ai-assistant`, `personal-assistant`, `self-hosted`, `llm`, `agents`,
`long-term-memory`, `task-automation`, `browser-automation`, `react`, `capacitor`,
`ios`, `java`, `python`, `postgresql`.

Website: the repository's `#try-the-interface` entry point (there is no hosted demo domain).
These settings require an authenticated GitHub session and are not applied by this
Markdown file. Confirm them on GitHub before claiming the metadata was changed.

Full local regression: `make build`, `make test`, `make check-style` passed;
Agent 45 / Tools 67 / Java 9 / bootstrap 6 tests, OpenAPI 91 operations.
`make test-integration`: **55 passed in 180.45 seconds**. Ruff, architecture checks,
secret scan and `git diff --check` passed. GitHub Linux CI is checked separately;
local macOS success alone must not be presented as a passing remote workflow.


## Linux CI follow-up

The installation repair let Linux CI reach the browser tests, exposing a second
failure: `Chromium sandboxing failed` at `Broker.start` on Ubuntu 24.04. Added
bounded failure context to CI annotations so this does not stay hidden behind a
single exit-code message. CI now grants user-namespace access only to the exact
installed Playwright Chrome/headless-shell paths, following the
[Chromium AppArmor guidance](https://chromium.googlesource.com/chromium/src/+/main/docs/security/apparmor-userns-restrictions.md).
The global AppArmor restriction and `chromium_sandbox=True` remain enabled.
The helper refuses local/non-Linux invocation, rejects escaping symlinks and emits
no wildcard attachment. Bootstrap/profile regression tests: 8 passed.

The README sources on GitHub were byte-checked against the local committed files;
all four mobile gallery image URLs returned HTTP 200 with image/jpeg content.
About description and the preview homepage link were saved through the authenticated
Chrome session and verified through the public repository API. Topic `ai-assistants`
was verified; the longer candidate list above has not all been applied. Chrome page
rendering/capture was intermittent; do not claim a screenshot was captured when it
returned blank. GitHub CLI has no authenticated session; no private tokens were
extracted or created.


## Non-root PostgreSQL startup

A disposable Ubuntu 24.04 container reproduced the next Linux bootstrap failure:
`could not create lock file /var/run/postgresql/.s.PGSQL.55432.lock: Permission denied`.
The default package socket directory belongs to the system PostgreSQL account.
`local_infra.py` now uses project-local `postgres-socket/` (0700), validates the port
and quotes paths for pg_ctl. A second fresh Ubuntu container started PostgreSQL 16
and Redis and created the development database successfully as a non-root user.
No host production database was used or changed. Bootstrap/helper tests: 12 passed.


## Remote acceptance

[GitHub Actions run 38824689772](https://github.com/jiamingze/Adex/actions/runs/38824689772)
on code revision `16e44bc` completed successfully: all four service images and the
`verify` job, including clean setup, exact-path sandbox profile, build, unit/contract
checks, formatting/lint, non-root infrastructure startup and full integration tests.
No test gate was removed or converted to an allowed failure. Local integration:
55 passed; local bootstrap/CI-helper tests: 12 passed.

About now describes semantic memory, daily planning, durable tasks and approved
browser actions. The Website links to the UI preview instructions. `ai-assistants`
is saved as a topic; the remaining candidate topics are follow-up suggestions,
not claims of applied settings. No release or outside promotion was published.
Traffic/referrer conversion is still unmeasured; repository improvements cannot
establish the cause of low attention or promise more stars.
