# Browser login and read recovery

## Observed gaps

- An approved cross-host GET returning HTTP 3xx lacks a transport receipt and stalls as UNKNOWN.
- The conversation card has no takeover control for an AGENT session, and collapses the page at the moment users need it.
- `open_login_frame` and `frame_id` are used by the client but absent from the Control request schema.
- Follow-up messages lack current browser state; old assistant capability disclaimers can dominate the answer.

## Contracts and implementation sequence

1. Verify a reviewed read-host GET on HTTP 2xx/3xx as transport only, never business success. Add regression tests first.
2. Add existing `open_login_frame`/`frame_id` to Control. Add explicit `recover_read` for UNKNOWN read-host GET only. In a short PG transaction, lock session then approval; retain an auditable FAILED effect/REVOKED approval, clear the session reference, then reopen in HUMAN mode. Never retry writes or claim the discarded read succeeded.
3. Expose takeover, expanded login page and a contextual read-recovery CTA in the conversation card; retain publish/order approval and unknown-write reconciliation.
4. Add an owner/conversation-scoped browser context endpoint for Agent containing state/IDs only (no screenshot, URL query, cookies or credentials). Ground follow-up instructions in this actual state without creating another Run or granting approval.
5. Run Python unit/integration checks, client/build/style/security checks and signed iOS build. Real merchant login and CAPTCHA remain BLOCKED_EXTERNAL until the user completes them; local Chromium fixtures are regression evidence only.

No database migration: reuse browser_sessions, approvals, effects, Automation leases/checkpoints and existing ownership controls. No new service, scheduler or per-site skill.

Reference: [Meta's published Muse safety design](https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse) describes visible browser takeover and credentials isolated from the main agent. This does not establish Muse's private implementation or guarantee access to merchant sites.
