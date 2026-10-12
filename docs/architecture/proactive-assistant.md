# Connectors, approvals and proactive assistance / 主动助手

Implemented on the existing four services: App owns user preferences, signals,
notifications and task organization; Tools owns OAuth/credentials/provider adapters
and approvals/effects; Agent performs read-only context assembly and approved Run
execution; Automation remains the only task scheduler/recovery owner.

## Current capabilities / 当前能力

- Google Calendar: primary-calendar event queries, timed-event conflict detection,
  approved time changes using ETag/If-Match and provider readback. Mixed all-day/timed
  events require manual checking. Owned-calendar scopes are requested incrementally.
- Gmail: bounded inbox metadata queries and explicitly approved email sending.
  No automatic reply or mailbox deletion. Send-only consent does not grant read access.
- OAuth: authenticated session-bound state, PKCE, short expiry and single use. Tokens
  and PKCE verifiers use AES-GCM with owner/resource AAD; credentials never enter public
  responses, model prompts or checkpoints. Revocation disables local access first;
  uncertain remote revocation remains REVOKE_PENDING until explicitly retried.
- Unified actions extend existing approvals/effects. Users confirm an immutable request
  hash. Actual execution requires live Automation run/epoch/attempt authorization.
  Unknown writes are reconciled, never blindly resubmitted. Legacy CalDAV routes cannot
  approve these Google actions. Reconciliation updates the action receipt; an original
  UNKNOWN Run is not automatically presented as a newly completed Run.
- Connector sync results flow through existing checkpoints and Automation Outbox.
  App deduplicates provider resource/version observations and persists correlation,
  explainable importance and suggestions. Calendar conflict scores 95, important mail
  scores 80. Notification preferences support threshold, quiet hours and timezone.
- Continuous checks use existing INTERVAL schedules (15 minutes), occurrences, leases,
  fencing and Run recovery. No second scheduler. Reads are bounded snapshots, not full
  Calendar push/Gmail Pub/Sub delta replication; partial results are explicitly marked.
- Task matrix organizes manual tasks by importance/urgency, supports revision-checked
  updates and optional links to existing Runs. Suggestions can be added by the user.
- APNs HTTP/2 adapter uses ES256 provider authentication, encrypted device tokens,
  durable dispatch/acceptance/UNKNOWN state and generic lock-screen text. Payload IDs
  reference notification/conversation/run/action. Authenticated resume validates owner
  before restoring the original conversation and Run. Apple acceptance is not proof of
  device display or reading.

## Google setup / 配置 Google

Configure a Google Web OAuth client with an exact HTTPS callback URI, enable Calendar
and Gmail APIs, and complete the applicable consent/scope verification. Set private
`.env` values: `ADEX_GOOGLE_CLIENT_ID`, `ADEX_GOOGLE_CLIENT_SECRET`,
`ADEX_GOOGLE_REDIRECT_URI`, `ADEX_PUBLIC_WEB_URL`, `ADEX_CONNECTOR_ENCRYPTION_KEY`.
The encryption key is base64-encoded 32 random bytes. Keep it outside Git, back it up
securely, and do not replace it without re-encrypting stored envelopes. This version
uses a single v1 key, not an automatic key rotation service.

Authorization starts in the Web browser; callback must retain the initiating Adex
session. The iOS WebView does not perform Google consent. Connect on Web, then use the
same registered account on iOS. Native OAuth handoff is a remaining acceptance item.
Gmail scopes may require Google review; test fixtures do not satisfy that requirement.
Explicit chat requests can read bounded authorized observations; background signal
assessment is rule-based and does not send mail content to a model. Selected metadata
can enter the configured model provider when the user requests account-aware chat.
Review provider data-use/retention policies before enabling a public integration.

Scopes: `calendar.events.owned.readonly`, `calendar.events.owned`, `gmail.readonly`,
`gmail.send`, under `https://www.googleapis.com/auth/`. Read, calendar write and mail
send are requested separately; no `mail.google.com` or `gmail.modify` scope is requested.

## APNs setup / 配置 APNs

Set `ADEX_APNS_KEY_FILE`, `ADEX_APNS_KEY_ID`, `ADEX_APNS_TEAM_ID`, `ADEX_APNS_TOPIC`
and `ADEX_APNS_DEVICE_ENCRYPTION_KEY` privately. The provider key is a private .p8,
never committed or baked into an image. For Compose, opt into `compose.push.yaml`
and provide `ADEX_APNS_KEY_HOST_FILE` for a read-only mount. Device encryption key is
separate from the Tools connector key.

Use an APNs-capable Apple team, App ID and provisioning profile. The opt-in
`apps/ios/ios/push.xcconfig` supplies the push entitlement; use `development` for
sandbox signing and the matching production entitlement/environment for distribution.
Default Personal Team builds do not claim APNs capability. The current UI registers
sandbox devices; production distribution/environment selection requires its own check.
Users must explicitly authorize/register notifications and enable push preferences.

## Verification and external boundaries / 验证边界

Google and APNs real service acceptance is **BLOCKED_EXTERNAL** without actual OAuth,
provider credentials, appropriate signing and device validation. Isolated tests use a
loopback TEST_FIXTURE provider only when explicitly enabled on an `adex_test_*` DB.
They do not modify real accounts, send real mail, or prove iPhone push delivery.

Observed checks: Java 7 unit tests, Agent 33, Tools 32; OpenAPI 77 operations;
39 PostgreSQL/HTTP integration tests; build, lint, style, architecture and secret gates.
The three required E2Es cover conflict→approval→change→verification; important email
→deduplicated suggestion; no client polling→fixture push→resume original Run/action.
Additional tests cover OAuth replay/wrong session/ownership, scope refusal, immutable
confirmation hashes, stale calendar writes, Gmail UNKNOWN reconciliation, legacy-route
bypass rejection and existing scheduler templates. iOS simulator build succeeded.
Physical reinstall currently requires repair of a revoked development certificate;
no new installation or real APNs delivery is claimed.

See [implementation plan/contracts](proactive-assistant-plan.md),
[engineering conventions](engineering.md), and [implementation status](../IMPLEMENTATION_STATUS.md).

Primary references: [Google OAuth](https://developers.google.com/identity/protocols/oauth2/web-server),
[OAuth security practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices),
[Calendar scopes](https://developers.google.com/workspace/calendar/api/auth),
[Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes),
[APNs connection](https://developer.apple.com/documentation/usernotifications/establishing-a-connection-to-apns).
