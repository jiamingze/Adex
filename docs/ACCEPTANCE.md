# Adex 1.0 · Acceptance / Fault Test Gates

Source: `Adex_Product_Technical_Design_v4.1.md`, subsection **P1-10 / P1-15**. The following cases are release gates; each must get automated tests where feasible plus a manual test note for iOS/music/licenses.

| ID | Test | Expected result |
| --- | --- | --- |
| ACC-01 | Same client_message_id repeated in same/different processes | Exactly one user message and no duplicate submitted agent turn |
| ACC-02 | Disconnect SSE, refresh Web, kill iOS App | Reconnect/snapshot provides committed state and task progress |
| ACC-03 | L1/L2/L3 memory recall and deletion | Cross-conversation recall, no deleted fact resurrection through summary/ES |
| ACC-04 | Kill Redis, kill ES, block PG separately | Redis recover/rebuild; ES graceful degrade/reindex; PG blocks unsafe writes |
| ACC-05 | Start three Automation scheduler replicas, one due occurrence | Unique schedule occurrence and one logical task run |
| ACC-06 | SIGKILL Agent background worker after checkpoint | New attempt, higher fencing epoch, resume from committed checkpoint |
| ACC-07 | External side effect happened but client timeout | UNKNOWN/reconciliation; no blind duplicate action |
| ACC-08 | Kill Outbox publisher after transaction commit | Duplicate-safe redelivery to user/origin conversation |
| ACC-09 | Music: real catalog listing + licensed sample + provider link | At least one legitimate playable audio; authorized commercial fallback, no pirate source |
| ACC-10 | Travel: dates, hotel, attraction, map | Grounded source/time/geo and editable itinerary |
| ACC-11 | Malicious generated HTML tries to read main-origin cookie | Blocked by sandbox policies, not just string filters |
| ACC-12 | Xcode Personal Team device build | Installs on own iPhone, syncs with Web, caveat re-sign after 7 days |
| ACC-13 | Backup PG + local file directory and restore to fresh sandbox | Account history, memories, tasks, artifacts restore, integrity checked |
| ACC-14 | Replay same monitor observation/notification-intent | Exactly one user-visible event per dedupe key |
| ACC-15 | API other-user access + over-budget tool call | Forbidden / paused with reason, no secret leakage |
| ACC-16 | Deep research / game generation iteration | Versioned artifacts, references, downloadable/previewable, can revise |
| ACC-17 | Unlicensed song clicked as inline player | Rejected; UI shows official link/unavailable |
| ACC-18 | Restart whole ECS then app containers | Data is durable; tasks resume after lease expiry; no claim of zero downtime |
| ACC-19 | Recreate App container, upload media/archives to mounted volume | Files/metadata/artifacts still accessible with correct SHA-256; Range/206 for authorized audio/video |
| ACC-20 | Crash mid-upload, path traversal, cross-user access, disk exhaustion | No half-file exposed; orphan/PENDING reconciled; unauthorized access denied; controlled disk-full failure |
| ACC-21 | DiagramSpec/Mermaid text→source→safe SVG/PNG→new editable revision | Valid source round-trip, export parses, malicious SVG/HTML does not execute |
| ACC-22 | Image text generation / reference edit / provider missing | Mock flow complete; real provider tests gated, BLOCKED_EXTERNAL without valid API |
| ACC-23 | Original music generation, file playback, storage/version | Generated or licensed fixture audio plays, downloads and passes auth/license tests |
| ACC-24 | Text/image to video, resume, playback/Range | New attempt recovers without blind resubmit; 206 range / poster / revisions work |
| ACC-25 | Duplicate/out-of-order webhook, provider timeout, old lease | Signature verified, stable effect key, one artifact version per job, UNKNOWN reconcile |
| ACC-26 | Unauthorized media access, dangerous input URL, file size/disk-full, recovery | SSRF blocked; no cross-user streaming; controlled storage failure + verified restore |

**Release evidence template:** Test ID, date/time, source revision SHA, command steps, output snippets, provider region and capability, result PASS/FAIL/BLOCKED_EXTERNAL, reviewer, and recovery note.
