# Browser reliability audit — 2026-10-17

## Research and actual gaps

Meta Muse publicly describes a persistent isolated Chromium browser with narrow
broker operations, user-visible takeover and a separate permission authority:
https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse
Manus separately offers an extension operating inside a local browser session:
https://manus.im/en/blog/manus-browser-operator
These are different deployment models; neither promises universal merchant access.

Local macOS proxy discovery showed HTTPS uses a loopback HTTP proxy; Adex's pinned
CONNECT broker dials destination IPs directly. This proves a routing difference,
not that proxy alignment alone resolves site risk controls. Adex also uses separate
cookie/storage state, not the user's normal Chrome profile. Existing cross-host GET
approvals can mistakenly present telemetry/bootstrap traffic as user actions.
Browser lookup retains only the final page, losing evidence needed for comparison;
query stripping also drops product identifiers from source links.

## Contract / implementation

No database migration, business service or scheduler. Keep existing Browser sessions,
approval/effect ledger, profile vault and Automation checkpoints/leases/outbox.
- Optional trusted ADEX_BROWSER_UPSTREAM_PROXY accepts an explicit credential-free
  loopback HTTP origin. The broker CONNECTs the validated pinned public IP through
  it. It never delegates target DNS, disables TLS validation, or permits private IPs.
  Child receives only this setting and allowed browser settings, no provider secrets.
- ADEX_BROWSER_CHANNEL selects bundled full chromium or installed stable chrome.
  No existing user profile is read/copied, no fingerprint spoofing, stealth flags,
  rotating proxies or CAPTCHA bypass. Configuration errors fail closed.
- Bounded network diagnostics distinguish failed transports, denied hosts and
  pending actions. Unsolicited cross-site requests cannot create write approvals.
- Read-task evidence notebook preserves bounded observed page evidence across steps
  and checkpoint/resume, with source URLs, observation IDs and timestamps. Pages are
  untrusted data; login fields, cookies and credentials are excluded. Public product
  identifiers may survive URL sanitization; secret parameters never do.
- Comparison results retain multiple page observations and state unverified SKU,
  region, coupon, shipping or login constraints; model text is not a purchase receipt.

## Acceptance

Unit tests cover pinned proxy routing/denial, bad proxy settings, source redaction,
notebook bounds/dedupe/resume and access-block classification. Existing fixture
login/search/approval/UNKNOWN tests remain labelled TEST_FIXTURE. Separate real
browser probes record actual title/content/login/block results, never fake prices.
Native Chrome capture recovered after the Mac was unlocked, but subsequent navigation
returned stale/incomplete content; UI completion was not established. Do not report
website-login success until actual login and an authenticated page are observed.

## Verified results and remaining external blocks

- Agent unit suite: 71 passed. Tools suite: 93 passed; final focused controls suite:
  23 passed (including a search box after 350 feed paragraphs); config/security suite:
  19 passed. Proxy shutdown now cancels and awaits open tunnels rather than leaving
  transports alive after loop shutdown.
- Isolated PG/four-service browser integration: 11 passed, including inline login,
  credential non-persistence, approval/receipt, UNKNOWN non-replay and guest ownership.
  These are TEST_FIXTURE, not real merchant execution.
- Real isolated Chromium + explicitly configured local proxy: Xiaohongshu returned
  title and 167 AX nodes. The unsolicited GET `data/sem_sdk` no longer causes a
  read approval. Clicking its real login entrance still raised a security-service
  request before a usable login form: **BLOCKED_EXTERNAL for completed login/search**.
- Taobao returned HTTP 200 but no usable AX controls after bounded settling:
  **BLOCKED_EXTERNAL**. Do not label it a verified search or offer.
- Apple's real product page returned the correct product title and 176 AX nodes;
  a cross-site asset still required a read grant. This is page access only, not a
  verified purchase/price comparison.
- No real account, CAPTCHA, publication, order or payment was submitted. No verified
  cross-merchant price comparison was obtained in these probes.

## Read and search policy

Independent AX text/link/control budgets preserve late search controls. `key: Enter`
is limited to an observed unprotected search field; arbitrary keys and login submit
remain outside Agent control. Every resulting write retains the approval gate.
Same-site non-navigation GET/HEAD uses the bundled Public Suffix List including
private suffixes; different github.io tenants do not share read permission. Every
host still passes DNS/public-IP pinning. Generic telemetry is denied, not approved.

Run a real probe without credentials:

```sh
uv run --project services/adex-tools python scripts/verify_browser_operator.py \
  --url https://www.xiaohongshu.com/explore --open-login \
  --output .local-data/browser-check.json
```

An optional private `ADEX_BROWSER_UPSTREAM_PROXY` may align a trusted loopback
proxy with the local browser route. It is never auto-discovered or enabled for
other deployments; empty configuration keeps direct pinned egress. Separate browser
profiles and site risk controls remain different from an already logged-in Chrome.

