# ADR 004: Optional native APNs with a Developer Program team

Status: accepted for the user's explicit 2026-10-17 deployment request.

Phase 1's free Personal Team baseline remains supported and does not promise APNs.
The owner has now enrolled a paid Developer Program team and explicitly requests
native scheduled-task notifications. Enable the existing APNs adapter for this
installation through ignored Signing.local.xcconfig and private server credentials.
Do not change Automation scheduling or create a second execution/recovery system.

Result outbox -> App notification -> durable push delivery is authoritative. Alert
payloads remain generic and owner-scoped IDs resolve the conversation/run/action on
tap. Apple acceptance is not proof of display or read. Development Sandbox and
production delivery must match the signed app and authentication key environment;
this deployment initially verifies Sandbox only. Existing user preferences, quiet
hours, revocation, encrypted tokens and UNKNOWN handling remain intact.

New device enrollment/re-enrollment must not flood the phone with historical
notifications. Refresh already-enabled device tokens on login, but never silently
re-enable a user's disabled push preferences. Signing team IDs, .p8 files, device
tokens and all credentials stay out of Git.
