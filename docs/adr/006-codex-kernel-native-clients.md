# ADR 006: Codex kernel and native Apple clients

Status: accepted direction; implementation pending. Date: 2026-10-30.
Authority: explicit owner request to import openai/codex, replace the execution
kernel/server, retain Adex capabilities, and build native iPhone and Mac clients.

This decision supersedes ADR-P1-02's Capacitor-only restriction and the exclusion
of a Mac client/device control. Other v4.1 ownership and reliability rules remain.

## Target

- Vendor a pinned, licensed snapshot of https://github.com/openai/codex under
  `third_party/codex`, retaining LICENSE, NOTICE and upstream provenance. Keep
  local changes reviewable separately from the upstream import.
- Use the Rust Codex harness and `app-server` as the execution engine behind
  `adex-agent`. The Python service remains the authenticated Adex integration
  boundary. App, Automation and Tools remain their existing business domains.
  A Codex child process/container is a runtime, not a fifth business service.
- App owns identities, messages, L1/L2/L3 memory and files. Automation continues
  to own durable runs, lease/attempt/epoch, checkpoints refs and outbox. Tools
  owns permissions, provider effects, UNKNOWN reconciliation and device runners.
- Native SwiftUI iPhone and macOS clients share typed App API/UI Schema models.
  Web remains React. Keep the working Capacitor client until native parity is
  demonstrated. Use restrained typography, chat/sidebar navigation, streaming
  activity, composer attachments and contextual approval cards inspired by the
  requested products, with Adex branding and independently implemented UI.
- iPhone commands travel through authenticated App/Automation/Tools to an
  owner-bound, paired Mac runner. Clients never expose app-server publicly.
  Device revocation, stale observation rejection, local permission denial and
  offline state must be visible. A general request to build ordering features
  does not authorize an actual purchase or trade during development.

## Integration contract and migration

1. Initialize the app-server protocol; start/resume a scoped thread; start and
   interrupt turns; translate streamed output and terminal status to Adex events.
   Confirm field names against the pinned upstream schema before implementing.
2. Bind every thread to owner/conversation and every background attempt to
   run/epoch/attempt. Never share a global CODEX_HOME across users. Codex history
   is execution state, not authoritative Adex memory. Deletion invalidates and
   purges derived thread state before reuse to prevent memory resurrection.
3. Route business tools through the existing Tools permission/effect gateway.
   Do not allow built-in shell/network tools to bypass approvals, budgets or
   file ownership. Codex approval alone is not an Adex authorization record.
4. Preserve immutable-checkpoint-first, fenced-ref-commit-second ordering.
   Restart/resume must reconcile uncertain effects before new submission.
   A successful Codex turn is not a durable Adex commit.
5. Roll out behind an explicit runtime selector after parity tests. Do not
   silently fall back after a possibly executed side effect. Preserve the old
   runtime until acceptance succeeds; no production data migration in tests.

This first source-import milestone has no database migration. Persistent thread
bindings and device protocol changes require reviewed migrations before runtime
cutover. Native client implementation and runtime cutover are not claimed here.

## Acceptance before cutover

Existing ACC-01..26 remain gates: chat/reconnect/cancel; all existing tool/card
capabilities; memory deletion; isolated file access; automation crash recovery;
stale epoch refusal; duplicate/UNKNOWN effects; provider failure reporting.
Additional gates: process EOF/timeout never reports completion, protocol mismatch
fails closed, cross-owner resume is rejected, revoked Mac cannot act, repeated
mobile commands do not create duplicate orders, native clients render unknown
cards safely and restore committed history after reconnect.

## Source and blockers

Official integration rationale:
https://developers.openai.com/blog/codex-as-a-platform

Open-source harness integration does not supply model credentials, managed
services, or the native ChatGPT/Codex application UI. Real model/media/device and
ordering-provider acceptance must be recorded separately; missing external
access remains BLOCKED_EXTERNAL. Source acquisition, build and tests are recorded
in the migration runbook, not inferred from this architecture decision.
