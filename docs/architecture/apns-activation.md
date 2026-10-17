# Native scheduled-task push activation

The user now has an Apple Developer Program team and requests native notifications
for scheduled-task results. This explicitly enables the existing optional APNs path;
it does not replace Automation scheduling, leases, fencing, checkpoints or outbox.

Gaps: push signing is opt-in and not enabled locally; native registration returns no
APNs environment and Web hardcodes sandbox; registration does not enable preferences;
there is no obvious Settings entry/status/test notification; APNs provider credentials
and device receipt have not been verified. Existing results already become durable
App notifications with conversation/run/action correlation.

Contracts: native `AdexPush.request` returns token + sandbox/production derived from
the signed build configuration. `/push/devices` retains its token/environment shape.
New owner-scoped `/push/status` exposes configuration/device/delivery metadata without
tokens, and `/push/test` creates an idempotent generic test notification using an
explicit event_id. The latter is rate-limited and does not fabricate a Run. Existing
notification preferences and delivery ledger remain authoritative. No DB migration
is required. Test acceptance distinguishes APNs ACCEPTED from device display/tap.

Implement native/build configuration, shared registration/UI and provider diagnostics,
then regression tests/build/sign/install and real device registration/send/tap. Keep
.p8, developer team settings, device tokens and signing credentials private. If Apple
membership, portal access, signing or provider key is unavailable, report
BLOCKED_EXTERNAL. Never present fixture delivery as real APNs success.

## Local activation

1. Enroll/sign in to a Developer Program team in Xcode. In ignored
   `apps/ios/ios/Signing.local.xcconfig`, set `ADEX_DEVELOPMENT_TEAM` and include
   `push.xcconfig`. Debug builds use `APNS_ENVIRONMENT=development`.
2. Enable Push Notifications for the App ID and refresh the automatic profile.
   Inspect the built app's signed `aps-environment`; a successful generic build is
   insufficient. The Info.plist environment must match the signing entitlement.
3. Configure the four ADEX_APNS_* provider fields and separate 32-byte base64
   ADEX_APNS_DEVICE_ENCRYPTION_KEY in the private server environment. Use a .p8
   scoped to the required environment and, where available, the individual topic.
4. Install the signed app. Settings -> Notifications -> Enable iPhone task push
   requests system permission, registers the native environment and enables the
   owner's push preference. Send test notification and verify phone display/tap.
5. For TestFlight/App Store, use production signing plus a production-capable key.
   Do not relabel a sandbox device token or assume the development key is valid.

The app/server must be running and externally reachable for task execution and
notification-tap content retrieval; APNs does not execute tasks on the iPhone.
Protect the Mac/server from sleep if it hosts scheduled work.
