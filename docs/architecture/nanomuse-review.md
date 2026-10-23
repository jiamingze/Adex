# Agent reliability: nanoMuse comparison and Adex implementation plan

Reviewed 2026-10-23 against nano-muse/nanoMuse revision
`bfbe5edf67e2804802faccfdaad7c85c49694a79` (retrieved GitHub tree and individual source
files into ignored local research storage). Repository: https://github.com/nano-muse/nanoMuse.
This is a code review, not evidence of running nanoMuse or universal device support.

## License and architecture boundary

nanoMuse declares GPL-3.0-or-later. Adex remains MIT. No source, prompts, assets or
runtime dependencies from nanoMuse are copied into the implementation. The mechanisms
below motivate independent changes inside the four existing service domains. Existing
PG ownership, immutable checkpoint/reference CAS, lease/attempt fencing, effect ledger,
outbox and deletion invariants remain authoritative. No second scheduler or agent daemon.

## Actual differences and contracts

| Concern | Reviewed nanoMuse evidence | Adex evidence / gap | Implementation in this milestone |
| --- | --- | --- | --- |
| Bounded execution | `nanomuse/agent/core.py`, `Agent.run`: model/tool loop, empty-output retry, stuck nudge, final wrap-up at step limit | `execution/agent_loop.py` already journals read intents and evidence, but malformed calls consume steps without useful correction; equivalent queries can evade the exact repeat guard | Strict schema included in planning; one bounded model-output correction at the same decision; normalized repeat signatures and journaled progress feedback; never replay an UNKNOWN write |
| Proactive surfacing | `nanomuse/prompts.py` separates explicit reminder/routine reports from quiet goal passes | Automation already owns durable result delivery and condition evaluation; CHANGES_ONLY currently compares final prose, so rewriting identical evidence may notify repeatedly | Compare a server-derived observation fingerprint where available; retain durable chat results, fall back compatibly when evidence is absent |
| Memory quality | `nanomuse/memory/consolidate.py`: bounded proposed consolidation, validation, change history | App already validates semantic memory proposals, revisions, evidence and deletion; planner repair omits the actual invalid proposal/error details | Improve bounded repair with observed validation details, without loosening consent/deletion policy or introducing automatic destructive consolidation |
| Approval / handover | `nanomuse/sentinel/policy.py`, `agent/holds.py`: risk gates and a fresh observation after human handover | Adex already has frozen approval payloads, UNKNOWN reconciliation, browser login in chat and scoped Mac access | Preserve these stronger durable boundaries; do not replace them with a mode toggle or model-only success |
| Live input reliability | Cross-device execution motivates independent client transport lifecycles | iOS audio depended on network-ready and per-buffer WebView delivery | Native bounded URLSession PCM transport, immediate capture, cancel fencing, live acceptance requiring a nonempty partial before release, and device-first transcript selection following real user accuracy feedback |

## Migration and interface list

- No new business service, public task route or required request field.
- Agent checkpoint state gains optional planning-feedback/observation fingerprint fields;
  older checkpoints remain readable and no recovery grants a fresh tool budget.
- Automation migration `010.sql`: optional result evidence fingerprint on Runs, with
  existing schedule-result readback for change-only surfacing. No new task lifecycle.
- Notification payload remains `notify` plus the original conversation/run identifiers.
  A suppressed push never suppresses authoritative Run results or chat backfill.
- Memory proposal contract remains unchanged; corrections use the existing invocation journal.

## Implementation and acceptance order

1. Finish native realtime ASR repair; unit/lifecycle, signed iOS build, synthetic native
   WebSocket integration proving interim text arrives before release; install on connected iPhone.
2. Agent loop: tests for invalid JSON repair, semantically equivalent repeated calls,
   cancellation propagation, crash resume and preserved budget. Run existing isolated Run recovery tests.
3. Proactive surfacing: tests for identical evidence with changed prose, changed source facts,
   missing evidence fallback, silence conditions, and conversation backfill. Keep user-requested
   ALWAYS notifications unchanged. Parallel occurrences retain existing fencing/transactions.
4. Memory repair: evidence/ID/revision validation tests and no deletion resurrection regression.
5. Build, language formatting, architecture/security checks, document observed results and
   limitations, commit and push. Real external integrations remain BLOCKED_EXTERNAL if unavailable.

Automatic memory-store consolidation, a universal device-control vocabulary, multi-agent
execution, autonomous purchases and additional connectors are not claimed implemented by
this bounded milestone. Each needs its own contracts, external acceptance and privacy tests.


## Shipped scope and evidence

The first milestone is implemented: schema-guided bounded planning repair, normalized
repeat detection with novelty feedback, source-derived notification identity (including
serialized concurrent schedule completions), improved memory-proposal correction, and
native/local-first iOS speech. See `docs/IMPLEMENTATION_STATUS.md` for exact commands,
observed results, external-test distinctions and remaining limits. No nanoMuse implementation
or prompt text is vendored, and the MIT license is unchanged. The delayed 23:25 automation
was deleted when the user requested immediate execution, so no duplicate job remains.
