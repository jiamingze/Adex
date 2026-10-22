# Push registration lifecycle

Logout intentionally revokes the current owner/device association and removes the local
`adex.pushDevice` hint. The old startup effect incorrectly required that hint before
registering, so a later login could leave notifications in PG without any active recipient.
System authorization alone does not restore a revoked server association.

On authenticated native startup, account change and foreground:

1. Read current account notification preferences. Never turn opt-out back on.
2. Call the native `AdexPush.request({prompt:false})` bridge. Check existing iOS permission;
   only authorized/provisional status calls APNs registration. No permission dialog.
3. With the authentication effect still current, submit the newly obtained token through
   the existing authenticated `/api/v1/push/devices` endpoint. Save its returned device ID.
4. Logout still revokes; stale callbacks cannot initiate registration or save a device hint.
   Offline/denied attempts may retry on a later foreground, without a persistent error banner.

Explicit user enablement continues to use `request({prompt:true})` and the existing settings
flow. Device token rotation and reinstallation do not rely on browser local storage.
Server re-registration advances its eligibility time after revocation, avoiding a burst
of older missed notifications. Existing preferences/quiet hours/conditional policy and
APNs delivery ledger remain authoritative. No new scheduler, endpoint or migration.

Validation: 29 client tests, Web/Java build, style/architecture gates and signed Xcode build
passed. Two isolated real-PG/API tests passed in 8.66s: revoked-device registration and new
notification delivery without old backlog, plus offline push/origin-Run recovery. APNs in
these tests is explicitly a fixture, not proof of actual iPhone delivery. Real acceptance
requires the unavailable phone to re-register; an Apple HTTP 200 means accepted, not shown.
