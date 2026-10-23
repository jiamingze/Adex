# Mac application operation (M17)

This optional adapter runs on the Mac hosting Tools, in an unlocked interactive
login session. It is not a new business service or scheduler. See
[ADR 005](../adr/005-macos-computer-use.md). Remote users cannot grant themselves
access to the server desktop.

## Enable locally

1. Build: `uv run python scripts/build_computer_runner.py` (Xcode command-line tools).
2. Bind an existing local account: `uv run python scripts/configure_computer.py --enable --owner YOUR_LOCAL_ACCOUNT`.
   This writes private `.env`, never Git. Initial allowlist: Calculator and TextEdit.
3. In System Settings → Privacy & Security → Accessibility, add the compiled helper
   `.local-data/computer-runner/AdexComputerRunner` and enable it. In Finder's file
   picker press Command+Shift+G and paste its absolute path to reach the hidden directory.
4. Apply migrations with `uv run python scripts/migrate.py`, then restart the four
   services with the normal development/deployment procedure. Other accounts remain denied.
5. Ask the assistant to operate the calculator. Each press or text replacement returns
   an exact action card in the original conversation; approve or cancel there.

To disable, set `ADEX_COMPUTER_ENABLED=false` and restart Tools. macOS Accessibility
can also be revoked in System Settings. Do not expose the helper as a public daemon.
Changing the binary signature/path may require macOS authorization again.

## Supported boundary

- Open/inspect one allowed app's bounded accessibility tree, press AXPress controls,
  replace writable AXValue fields. Password fields are redacted and denied.
- No shell, AppleScript, coordinates, arbitrary generated code, screen capture,
  direct filesystem APIs, keychain, system settings or terminal applications in this adapter.
- Custom-drawn controls and inaccessible UI are explicitly blocked. This is not yet
  a universal computer operator; scroll, menus and keyboard shortcuts need further adapters.
- Ordinary observation can include non-secret visible document content. Enable only
  apps whose contents you authorize the configured model provider to process.
- Native command acceptance proves only that the OS accepted the command. It does
  not prove a purchase, publication, delivery or overall goal completion.

## Execution and recovery

`computer.start` persists an existing Automation COMPUTER Run and reads it back.
Agent uses existing immutable checkpoints, Run epoch/attempt/lease fencing and
WAITING_INPUT resume. Tools checks owner, allowlist, live Run and non-deleted origin
conversation before dispatch. Tools migration 009 adds observations and one host mutex.
The mutex expires after 35 seconds; native watchdog is 15 seconds and parent timeout
20 seconds. No transaction or row lock spans native execution.

Observations are private, run-bound and usable for ten minutes. The next observation
request removes that owner's observations older than one day; idle accounts do not
have an immediate retention deadline. Approval records retain bounded action details
for the existing audit policy. Stale UI/PID/hash fails closed. Re-observe and prepare a
new action rather than reusing the old snapshot.

An effect is recorded IN_FLIGHT before native dispatch. A crash, timeout or ambiguous
reply becomes UNKNOWN and cannot be automatically replayed. Inspect the real app
manually before starting new work. Reconciliation does not manufacture success.

## Verify

```sh
make build test check-style
uv run python scripts/test_stack.py tests/integration/test_computer.py -q
# Optional: real Calculator only, isolated test DB; changes its disposable display.
ADEX_TEST_REAL_COMPUTER=1 uv run python scripts/test_stack.py tests/integration/test_computer.py::test_actual_calculator_with_isolated_effect_ledger -q
```

Default tests use an explicitly marked synthetic AX fixture, never evidence of native
execution. Missing macOS/helper/permission is BLOCKED_EXTERNAL or a named permission
error; it is never replaced by a fake production success.
