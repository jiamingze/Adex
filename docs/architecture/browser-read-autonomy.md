# Browser read autonomy

Ordinary public HTTPS GET/HEAD/OPTIONS reads, including cross-site search result navigation,
are automatic after the existing public-DNS, pinned egress, port and resource checks.
They do not grant writes, credential access, private-network access or action success.
Critical gestures and known action URLs remain gated even with GET. Telemetry is denied
rather than converted into an approval. POST search endpoints remain gated unless a
future trusted adapter can establish read-only semantics; model labels alone cannot.
No migration or new scheduler. Existing UNKNOWN writes are never replayed automatically.

Verification must distinguish deterministic route-policy tests from actual external Google
reachability. Login/challenge pages are not successful search results.

A blocked Google /search read-only lookup may use the existing authenticated search
provider once, preserving the original query from the actual URL. The result explicitly
states Google was blocked and identifies alternate search snippets, never merchant quotes
or successful access to Google. No fallback is permitted for pending writes, human login,
non-search sites or write workflows. No repeated challenge requests or CAPTCHA bypass.

## Observed validation (2026-10-20)

- `make build test check-style` passed; subsequent final Agent suite: 105 passed; Tools full suite: 132 passed. Architecture and secret checks passed.
- `uv run python scripts/test_stack.py tests/integration/test_browser_operator.py`: 6 passed in 97.90s; isolated PG and Chromium fixtures, not real publication/merchant acceptance.
- Live credential-free Google operator returned a real unusual-traffic challenge with no pending approval; Google search results remain BLOCKED_EXTERNAL on that egress. Existing authenticated Tavily live search returned 5 results. No CAPTCHA bypass, successful Google search or personal browser session reuse is claimed.
- Existing UNKNOWN writes remain preserved and are never silently replayed. Backend deployment requires no iOS bundle change.
