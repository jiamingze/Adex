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


## 2026-10-18 refresh

A later full-suite CI failure was not a product reminder failure: the reminder
integration test asserted a global zero invocation count after preceding tests had
already made model calls. The assertion now scopes `agent.invocations` to the
current reminder Run and still requires zero calls both before and after outbox
redelivery. No failure is suppressed and no runtime quota is loosened.

Local verification on the corrected code:

- `uv run python scripts/test_stack.py`: **73 passed in 274.05s**, isolated database.
- `uv run pytest tests/scripts -q`: **12 passed**.
- `make check-style`: passed, including architecture checks.
- `uv run ruff check services/adex-agent/src services/adex-tools/src packages/python-kernel/src`: passed.
- `uv run python scripts/check_contract.py`: passed.
- `uv run python scripts/check_secrets.py` and `git diff --check`: passed.

Actions are pinned to verified upstream release commits. CI retains build, unit,
contract, style, lint, integration and four Docker image gates; adds a secret scan,
manual dispatch, timeouts and cancellation of superseded runs. Dependency update
PRs are grouped and rate-limited; they do not auto-merge. `JAVA_HOME` supplied by
contributors is respected instead of being overwritten with a macOS-only path.

Applied through the authenticated repository UI: refreshed About, 13 relevant
topics, enabled Discussions, a pinned [bilingual welcome](https://github.com/jiamingze/Adex/discussions/1),
[first contribution issues](starter-tasks.md), branch-update suggestions and automatic
merged-branch cleanup. A synthetic 1280×640 social preview is uploaded; its editable
source is in `docs/assets`. README banners use the same light mountain/sun identity.
No user content is used in these images. The homepage still points to the documented
local UI preview, not a nonexistent hosted service.

These changes improve discoverability and onboarding. GitHub traffic and conversion
need measurement over time; no manufactured stars, followers or external messages
are part of this work. Real merchant execution and external provider availability
retain the limitations documented in IMPLEMENTATION_STATUS.md.


Remote acceptance for the CI repair: [run 39049363749](https://github.com/jiamingze/Adex/actions/runs/39049363749)
on `8ff0fd1` completed successfully: `verify` and all four image builds. Additional
packaging checks parsed all changed GitHub YAML and verified 70 local README/starter
link targets. The final packaging commit is checked by the same CI workflow.


Security settings verified in GitHub: private vulnerability reporting, dependency
graph, Dependabot alerts, Dependabot security updates and grouped security updates
are enabled. Existing secret scanning and push protection remain enabled. No
credentials, wider contributor permissions or automatic dependency merges were
created. See [SECURITY.md](../../SECURITY.md) for the private reporting entry point.


Version-update PRs are limited to one per ecosystem and grouped; automatic major
runtime/framework upgrades are excluded from version updates and require a focused
migration. This does not disable vulnerability alerts or security-update PRs.
GitHub CodeQL default setup is configured for Actions, Java/Kotlin,
JavaScript/TypeScript and Python. Swift requires a separate reproducible Xcode build
configuration and is not claimed as covered by this default scan. The native build
and signing acceptance remain separate from Linux CI and static analysis.


### Imported dependency alerts and remediation

The initial empty Dependabot list was observed before dependency graph import
finished; it was not a final clean security result. Once imported, the graph
reported vulnerable Vite, terminal regex, UUID, KaTeX, Starlette and pytest versions.
Updated Vite to 6.4.3 and Mermaid to 12.2; refreshed compatible transitive patches.
A scoped `xcode>uuid` override uses 11.1.1 (CommonJS), preserving the parser's v4 API;
the actual project parses and generates a valid 24-character Xcode identifier.
FastAPI 0.143.3 with Starlette >=1.3.1 and pytest 9.1.1 / pytest-asyncio 1.4.0
resolve the Python findings. All three lockfiles are regenerated. Major runtime
upgrades such as Python 3.14 or Spring Boot 4 are not part of this repair.

Local `pnpm audit --registry https://registry.npmjs.org`: zero known advisories in
all severity categories. `uv tool run pip-audit` against each installed root,
Agent and Tools environment: no known vulnerabilities. The same npm and pinned
pip-audit checks are added to CI; registry/service availability failures remain
visible. Current known-advisory audits do not constitute a general security proof.

After the dependency changes: `make test` passed (bootstrap 12, client 22,
Agent 81, Tools 103, Java tests and OpenAPI 93 operations); Web build, style and
architecture checks passed. A signed iPhone build and installation also passed.
The repository history was additionally checked across 1,185 blobs for the existing
credential patterns without printing values; none matched. The production database
was not used as a development test fixture.


### CodeQL text-processing hardening contract

The initial CodeQL scan also identifies polynomial backtracking on untrusted chat,
model output and diagram text. Replace wildcard intent scans with ordered literal
searches that preserve same-line ordering; cap numeric/whitespace fields to the
actual scheduling/media contract; strip JSON fences with string boundaries. Browser
host validation must check individual DNS labels and length rather than ambiguous
repeated groups. Diagram validation must tokenize arrow/angle characters without
using HTML-removal substitutions. Keep existing routes, owner checks and approvals.
Tests cover long near-misses, JSON/code preservation, duration overflow, bad DNS
labels and diagram tags. Fix test URL assertions to compare hosts exactly; reject
invalid synthetic cookie flags rather than reflecting them into response headers.
No database migration or service contract change is needed.


Hardening verification: Agent 87 tests, Tools 119 policy/provider tests plus three
loopback fixture/header/asset regressions, client 22 tests, Java 11 tests and OpenAPI
93 operations passed. `make build`, `make check-style`, Ruff and architecture checks
passed. Full isolated integration after text hardening: **73 passed in 286.67s**.
CodeQL is left enabled so the final commit is rescanned rather than dismissing
findings manually. Its remote result is checked separately before release.


The next remote scan automatically closed 27 findings and isolated two remaining
parser patterns. Fenced HTML/Mermaid source extraction now scans canonical header
lines and closing delimiters with string indexes; malformed/missing fences remain
unchanged. Diagram angle validation uses a literal character scanner, not a regex
that resembles HTML filtering. Additional Java tests preserve source bodies and
exercise long malformed headers. Neither finding is manually dismissed.


Remaining-parser checks: `make build`, `make test`, `make check-style`, Ruff and
secret scan passed (Java 14, Agent 87, Tools 122, client 22; OpenAPI 93 operations).
`uv run python scripts/test_stack.py tests/integration/test_workspace.py -q`:
**14 passed in 3.82s**, including fenced sequence-diagram edits, private file readback
and active-content rejection. App and Tools recognize all six supported arrow tokens
consistently, including `-->>`. The preceding full isolated suite passed 73 tests;
the final GitHub workflow runs it again on the parser commit.
