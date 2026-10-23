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
