# ADR 005 — Owner-bound Mac computer runner (M17 extension)

User explicitly requested Mac application operation beyond the original Phase-1 exclusion.
Keep four business services. Tools owns the native runner, allowlist, observations and
existing effects/approvals. Agent plans bounded steps. Existing Automation Run, lease,
fencing, checkpoints, waiting/outbox and App-origin result attachment remain authoritative.
No second scheduler, shell/AppleScript tool or arbitrary script execution.

Contract: `computer.start {goal, app_name}` creates COMPUTER Run. Tools internal
`POST /internal/computer/observe` and `/step` require Agent delegation + live COMPUTER
run/epoch/attempt, configured local owner and app allowlist. Observations are immutable,
private and run-bound. Native actions require the same fresh AX tree hash and bundle/PID.
Open/observe are read operations; press/set_value require an immutable, expiring action
approval in the current conversation. Reuse approvals/effects for exact snapshots and
UNKNOWN; never auto-repeat an interrupted mutation. Global host command lease serializes
commands across service replicas; do not hold PG transactions across native execution.

Tools migration 009 adds private computer observations and a host command mutex only.
No Run/scheduler migration. Extend existing Run kind contracts and wait/resume endpoints.
Default disabled; explicit local owner and bundle allowlist required. macOS Accessibility
permission is controlled by the user in system settings. Linux/headless/locked/TCC denial
must report BLOCKED_EXTERNAL or a specific permission blocker, never success. No screenshots
or arbitrary filesystem access in this first adapter. Password fields are redacted and
cannot be written. Unsupported/custom-drawn controls require human operation.

Tests: schema/owner/allowlist/stale observations, approval and effect replay/UNKNOWN,
lease fencing, actual isolated PG/API wait-approve-resume and native Swift compilation.
Fixture execution is not evidence of real app operation. Real desktop validation must
use disposable content and report missing OS authorization honestly.

## Wire contracts

- App `GET /internal/conversations/{id}/computer-access`: Tools issuer,
  `computer:access`, delegated owner and conversation resource; returns
  `{allowed:true}` only for an owned, non-deleted conversation.
- Tools `GET /internal/computer/status`: App issuer, `computer:read`, owner;
  `{availability:"READY"|"COMPUTER_ACCESSIBILITY_PERMISSION_REQUIRED",apps:[alias]}`.
- Tools observe body: `{run_id,epoch,attempt_id,app_name}`; returns
  `{observation_id,bundle_id,pid,tree_hash,nodes,receipt:"OBSERVED"}`.
- Tools step adds `{observation_id,command_key,step:{action:"press"|"set_value",
  element_id,text},approval_id?}`. Extra fields are forbidden. No approval returns
  `{status:"APPROVAL_REQUIRED",action_id}`. Approved dispatch returns
  `{status:"COMMAND_APPLIED",action_id,receipt}` or `{status:"UNKNOWN",action_id}`.
- Existing App `/api/v1/actions/{id}/approve|revoke` uses the immutable request hash.
  Approval resumes the SAME waiting COMPUTER Run with a new execution epoch/attempt.
  No model-generated success string becomes an effect receipt.
- Result delivery uses `run_id + delivery_key` for individual wait cards and the
  canonical final result key; waiting notifications cannot deduplicate away final output.

Implementation order: migration and closed contracts → isolated fault/flow tests →
native runner and Tools dispatch → Agent checkpoint integration → App approvals and
result delivery → chat UI and local setup → actual Calculator acceptance. M17 is an
explicit scope extension; M01–M16 service ownership remains unchanged.

### Chrome read/search extension

Chrome aliases resolve to the configured bundle before creating a Run. Public status
accepts an optional app_name preflight; a missing app grant must fail before task creation.
A separate closed `ComputerObservation` adds optional `search_query` (1..500 characters).
Only Chrome supports it. Native code constructs a Google HTTPS search URL itself and
opens it in the installed Chrome; no arbitrary URL, JavaScript, profile extraction or
remote-debugging port. Search is a read operation and does not require a write approval.
Only the focused Chrome window is inspected. Native page text/URL provide result evidence;
blocked/unreadable results must be reported, not guessed. Agent persists pending search
on the existing checkpoint path and limits/rejects duplicate searches. No DB migration.

### 2026-10-23 follow-up: explicit whole-Mac authorization and routing repair

The owner explicitly authorized all installed Mac applications. Host configuration can
set `ADEX_COMPUTER_APP_POLICY=all_installed` while retaining exact owner binding and
existing action approvals. Resolve names against installed application bundles on the
host, not arbitrary executables or generated shell. Default for other deployments remains
`allowlist`. Status preflight resolves the requested app before claiming a task started.
Task planner repair includes bounded schema validation details; final parameter failures
must not tell browser users to supply a task time. Browser queries remain plain text,
including ambiguous phrases such as “CET版”; never silently rewrite to ChatGPT.

### File return to the originating chat

A Finder click cannot transfer a host file to an iPhone. Add a closed
`POST /internal/computer/export-file` contract (same live Run/owner delegation,
`file_path`, stable `command_key`). Only explicitly configured host file roots apply;
all-installed app policy does not grant unconstrained filesystem access. Read one
regular file through no-follow directory descriptors, bounded to 25 MiB; reject hidden
and credential paths, symlink escapes and directories. No document body is sent to the
model. Upload through the App private File API with a Run/step idempotency key, verify
READY/hash/size using owned metadata readback, then return a file card in the original
conversation through existing Run completion/outbox. App's documented idempotent file
import permits safe retry of an identical body; changed content must conflict. No DB
migration, scheduler, unmanaged persistent file write or public share URL.

The entry `computer.start` contract adds optional `file_path` only for an explicit
user file-return request. App freezes it in Run.params; Automation effect authorization
returns the exact `computer_file_path`. Tools rejects any absent/mismatching grant
before opening a file. Browser/operator output cannot expand this initial scope.
File completion is rendered from App metadata, never from model prose.

Search completion uses an evidence renderer: named Markdown links, observed headings
and nearby excerpt text, at most five items, query timestamp and search-page provenance.
Ignore free-form model URL dumps and do not label successful search “desktop stopped”.
