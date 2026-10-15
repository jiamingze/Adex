# Public browser access

## Gap and scope

The existing Chromium subprocess only admits hard-coded GitHub hosts, and the Agent
silently falls back to search for other links. Extend the existing Tools runner, not
the number of business services. Ordinary chat remains App → Agent → Tools. Existing
interactive evidence/checkpoint persistence and background Run recovery remain owners
of recovery; this capability creates no new scheduler or execution ledger.

## Contract and migrations

No database migration. Keep Agent → Tools `POST /internal/browser/read`, owner-bound
`search:read` capability and existing per-owner retrieval quota. JSON:
`{"url":"https://public.example/page","query":"question","max_pages":3}`.
`max_pages` defaults to 3 and is bounded 1–3. Results retain `provider`, `fetched_at`,
`items[].{url,title,snippet,extracted_text,fetched_at,evidence_level}`. Add bounded
`links` to each page. Source cards and persisted interactive plans use this response.
Errors are explicit `BROWSER_URL_NOT_ALLOWED`, `BROWSER_DNS_BLOCKED`,
`BROWSER_UNAVAILABLE`, `BROWSER_TIMEOUT`, or `BROWSER_BUSY`. No successful page means
no browser evidence; search snippets must never be relabelled as rendered pages.

## Implementation plan

1. Extend destination policy to admit an explicitly requested public HTTPS hostname
   in `public` mode; retain exact-host `allowlist` mode for restricted deployments.
2. Resolve all admitted hosts before launch, reject any private/reserved DNS answer,
   and pin admitted IPv4 addresses in a per-run CONNECT egress proxy. Unknown hosts fail closed. Same-host
   links may be followed, but arbitrary cross-origin redirects are blocked.
3. Use fresh credential-free contexts, GET-only interception, disabled service
   workers/WebSockets/downloads, Chromium sandbox, bounded concurrency/deadline,
   rendered-text size and request count. Do not expose arbitrary JS or browser actions.
4. Route explicit links to browser reads irrespective of GitHub. Explicit requests
   to open a website without a URL first search and then read one candidate. Preserve
   honest failure evidence and ordinary search behavior.
5. Add policy/SSRF/Agent routing tests and opt-in real Chromium smoke; run service
   tests, contract/style/security checks, restart local Agent/Tools and verify health.

## Access boundary

Read public pages and bounded same-host links only. No user Chrome profile, cookies,
login, CAPTCHA bypass, forms, booking or purchasing. Future browser write actions
must use Action Approval and the existing tool effect ledger. Page text is untrusted
input, never executable assistant instructions. GET-only does not prove every remote
website is semantically read-only; never supply account sessions or action URLs.

The child receives no service/model/database credentials. DNS is pinned once for the
run; host allowlists are not suffix matching. TLS validation stays enabled. Chromium
is not a substitute for OS/container isolation: production must run non-root with
sandbox support and the deployment's CPU/memory/PID/network controls. Public browsing
can contact the explicitly requested public destination; use allowlist mode when this
is inappropriate. Only configured extra hosts may serve cross-origin assets.

## Verification and external boundaries

Real Chromium smoke on 2026-10-15 obtained `https://docs.python.org/3/` and
`https://docs.python.org/3/about.html`, with actual rendered text, titles and UTC fetch
timestamps. This test did not call a model, use an account, or modify a database.
Run `uv run --project services/adex-tools python scripts/verify_browser.py` to repeat
against the live public website; its availability is external, not guaranteed by unit tests.

Playwright network interception and service-worker blocking follow its
[official network documentation](https://playwright.dev/python/docs/network).
The CONNECT proxy separately checks every target even after server redirects.

The GitHub repository smoke did not obtain a rendered page in this environment
(`NAVIGATION_TIMEOUT`, `BROWSER_UNAVAILABLE`); that destination is recorded as
`BLOCKED_EXTERNAL` for real-access acceptance, not replaced with fabricated evidence.

Validation: Tools 55 tests, Agent 40 tests, 45 isolated HTTP/PG integration tests and
83 OpenAPI operations passed. Integration tests exercise auth/scopes and destination
rejection; they do not claim real public-network rendering. The live Python-documentation
smoke above is the separate real rendering evidence.

Commands run for this change:

```bash
uv run --project services/adex-tools pytest services/adex-tools/tests -q
uv run --project services/adex-agent pytest services/adex-agent/tests -q
make test-integration
make check-style
make test-contract
uv run python scripts/check_secrets.py
uv run --project services/adex-tools python scripts/verify_browser.py
uv run python scripts/dev.py status
```

The first integration attempt expected 401 for a valid issuer with the wrong scope;
the actual contract correctly returned 403. The assertion was corrected and the full
isolated suite rerun successfully (45 passed). GitHub's separate direct HTTPS
network diagnostic also timed out; no TLS validation or private-address safeguards
were weakened to bypass this condition. Existing iOS clients use the updated server
capability without a new application bundle.
