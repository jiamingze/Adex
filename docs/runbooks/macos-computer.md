# Mac application operation (M17)

This optional adapter runs on the Mac hosting Tools, in an unlocked interactive
login session. It is not a new business service or scheduler. See
[ADR 005](../adr/005-macos-computer-use.md). Remote users cannot grant themselves
access to the server desktop.

## Enable locally

1. Build: `uv run python scripts/build_computer_runner.py` (Xcode command-line tools).
2. Bind an existing local account: `uv run python scripts/configure_computer.py --enable --owner YOUR_LOCAL_ACCOUNT`.
   This writes private `.env`, never Git. Initial allowlist: Calculator, TextEdit and Chrome. To explicitly authorize all installed applications for this bound owner, add `--all-apps` to the configure command. This changes host policy, not other accounts' access.
3. In System Settings → Privacy & Security → Accessibility, add the compiled helper
   `.local-data/computer-runner/AdexComputerRunner` and enable it. In Finder's file
   picker press Command+Shift+G and paste its absolute path to reach the hidden directory.
4. Apply migrations with `uv run python scripts/migrate.py`, then restart the four
   services with the normal development/deployment procedure. Other accounts remain denied.
5. Ask the assistant to operate the calculator or open Chrome and search. Chrome search opens a real Google tab, reads the document and returns source links without write approval. Each press or text replacement returns
   an exact action card in the original conversation; approve or cancel there.

To disable, set `ADEX_COMPUTER_ENABLED=false` and restart Tools. macOS Accessibility
can also be revoked in System Settings. Do not expose the helper as a public daemon.
Changing the binary signature/path may require macOS authorization again.

## Supported boundary

- Open/inspect one allowed app's bounded accessibility tree, press AXPress controls,
  replace writable AXValue fields. Password fields are redacted and denied.
- No shell, AppleScript, coordinates, arbitrary generated code, screen capture,
  unrestricted filesystem APIs, keychain, system settings or terminal applications in this adapter.
- All-installed policy resolves installed app bundles rather than requiring a per-app list. It does not add unsupported control methods. Custom-drawn controls and inaccessible UI are explicitly blocked. This is not yet
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

## Chrome regression acceptance

```sh
# Real Chrome + Qwen, only a random isolated test database. Uses the configured
# model key; public search query is CET版, not personal application content.
ADEX_TEST_REAL_CHROME=1 uv run python scripts/test_stack.py tests/integration/test_computer.py::test_actual_chrome_search_returns_to_original_conversation -q
```

This opt-in test sends the original Chinese request, creates a COMPUTER Run, executes
search, verifies source links in the original conversation and asserts no mutation
approval was needed. It is separate from deterministic fixture tests. Search data
passed to the model excludes Google account/navigation and location footer. Native
reads only the focused document, not unrelated tab titles. A missing installed app
fails preflight before a task-start receipt; a blocked search fails explicitly.

## Return a Desktop document to chat

Explicitly enable document access for the bound owner:

```sh
uv run python scripts/configure_computer.py --enable --all-apps --desktop-files
```

`ADEX_COMPUTER_FILE_ROOTS` is independent of installed-app access and defaults empty.
The optional flag permits Desktop documents; configure other roots deliberately.
Ask “send the Desktop file fixture-document.pdf to this chat” using your actual file
name. Semantic entry planning freezes `file_path` in the Run request. Tools rechecks
that exact grant from Automation before reading. A later browser page cannot grant
itself document access or change the requested file.

Only a single regular file up to 25 MiB is supported. Directories, app bundles, hidden
paths, credential extensions and symlink escapes are rejected. Document bytes never
go to the model. App owns the uploaded copy, READY metadata, private ownership and
stable Run/step import key; Tools verifies hash and size by readback. A changed file
after interrupted upload conflicts rather than silently replacing the first import.

The original chat gets a private attachment card. Web downloads via authenticated
blob access; the updated iOS client opens the system share sheet, including Save to
Files. iOS uses a temporary local copy removed after share completion/cancellation.
A client update is needed for this new card/native plugin. Physical-device installation
is verified separately from the user completing the share/save flow.

### Direct webpage navigation

The computer operator supports `navigate` with a public HTTPS URL in `text`, besides
Google `search`. Tools validates public address admission, then the native helper
opens it in the user's installed Chrome/profile and reads the focused page AX tree.
Opening/reading does not need an action approval. Arbitrary scripts, local/private
network URLs and shell commands are outside this capability. Mutating controls keep
the existing effect/approval/fencing path. `blocked` plans must have a user-facing
reason; blank completion text is invalid and receives bounded schema repair.
No migration or second task engine is needed; navigation intent uses existing immutable
checkpoint + authoritative Run checkpoint-ref commit before native dispatch.
