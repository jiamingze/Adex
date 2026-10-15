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

Website: the repository's installation guide (there is no hosted demo domain).
These settings require an authenticated GitHub session and are not applied by this
Markdown file. Confirm them on GitHub before claiming the metadata was changed.

Full local regression: `make build`, `make test`, `make check-style` passed;
Agent 45 / Tools 67 / Java 9 / bootstrap 6 tests, OpenAPI 91 operations.
`make test-integration`: **55 passed in 180.45 seconds**. Ruff, architecture checks,
secret scan and `git diff --check` passed. GitHub Linux CI is checked separately;
local macOS success alone must not be presented as a passing remote workflow.
