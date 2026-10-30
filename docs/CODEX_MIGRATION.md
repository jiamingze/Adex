# Codex migration work log

See [ADR 006](adr/006-codex-kernel-native-clients.md) for the approved direction.

M19 is the source import and integration-contract milestone. It precedes runtime
cutover and native client delivery. Existing Adex functionality remains active
until the replacement passes the existing acceptance suite.

Pending deliverables:

- Pinned upstream source import with license and provenance, local Rust build and
  app-server initialize smoke without model credentials.
- Protocol bridge tests (events, interruption, EOF, timeout, approvals), then
  owner-bound runtime integration and checkpoint migration.
- SwiftUI shared models and iPhone/macOS apps with real App API authentication,
  conversation streaming, tasks, artifacts, settings and rich card parity.
- Paired Mac operation through Tools, mobile approvals and effect reconciliation;
  ordering requires concrete provider/account, quote and execution approval.

No real purchase, trade or production database mutation is part of development.

## Observed evidence: 2026-10-30

- Imported all 9,792 upstream files at
  `a4b4082b5f14a8a037386d823ddb96a85fd25975` into `third_party/codex`.
  Byte comparison against the pinned checkout passed; no upstream edits.
- HTTPS `git clone --depth 1 https://github.com/openai/codex.git` timed out.
  `git clone --depth 1 git@github.com:openai/codex.git /tmp/adex-codex-ssh`
  succeeded. LICENSE and NOTICE preserved.
- `make check-style`: passed; 134 Python files already formatted; architecture
  ownership/composition checks passed (before source import; Adex sources unchanged).
- `uv run python scripts/check_contract.py`: passed, 101 operations.
- `uv run python scripts/check_secrets.py`: passed after audit of upstream
  synthetic credential/redaction fixtures and public test RSA keys. Exact file
  SHA-256 exceptions are recorded in `third_party/codex-public-test-fixtures.json`;
  no directory-wide exclusion. A temporary edit to an allowlisted fixture was
  rejected by the scanner, then restored byte-for-byte.
- `cargo build --locked -p codex-app-server` was attempted from the vendored
  Rust workspace. Dependency resolution fetched Git/V8/Chromium dependencies;
  stopped before compilation completion. Installed Homebrew Cargo is 1.94.0,
  while upstream pins Rust 1.95.0. Build and protocol smoke remain UNVERIFIED;
  provision the pinned toolchain before retrying. No claim of runtime readiness.

Runtime adapter, production cutover, SwiftUI apps and phone-to-Mac operation are
still pending. Model/provider access and actual device/order acceptance have not
been tested. This commit is source acquisition and migration groundwork only.

## Installation follow-up: 2026-10-30

Installed Rust/Cargo 1.95.0 with rustfmt, clippy and rust-src. The official Rust
manifest checksum matched the rsproxy mirror used to complete the slow download.
Homebrew Cargo still precedes rustup in the interactive PATH; use explicit
`rustup run 1.95.0` (or prepend `$HOME/.cargo/bin`) for reproducible builds.

Source build attempted:

```sh
cd third_party/codex/codex-rs
PATH="$HOME/.cargo/bin:$PATH" CARGO_INCREMENTAL=0 CARGO_BUILD_JOBS=2 cargo +1.95.0 build --locked --profile dev-small -p codex-app-server --bin codex-app-server
```

Dependency acquisition is BLOCKED_EXTERNAL: the pinned V8 dependency requests
`https://chromium.googlesource.com/chromium/src/buildtools.git`, which times out
from this machine. The build was stopped; no source-built binary is claimed.

Installed the official **prebuilt** Apple Silicon app-server release
`rust-v0.166.0` in `.local-data/codex/bin/codex-app-server`. This release is separate
from the vendored development commit. Release asset ID `689702267`, compressed
SHA-256 `50ea739230a917af485c4fac0b0f3c9b5b25e06fa687bfd613aeab8d531bccb5`,
verified against GitHub's release asset metadata before extraction. Local install
provenance and binary hash are in `.local-data/codex/installation.json` (ignored).
No existing Codex executable, credentials or global shell config were replaced.

Observed commands/results:

- `rustup run 1.95.0 rustc --version`: rustc 1.95.0.
- `rustup run 1.95.0 cargo --version`: cargo 1.95.0.
- `.local-data/codex/bin/codex-app-server --version`: codex-app-server 0.166.0.
- `make test-codex-runtime`: PASS, actual stdio initialize/initialized handshake
  with a temporary HOME/CODEX_HOME, no model call or personal credentials.
- `uv run python scripts/smoke_codex_runtime.py --binary /usr/bin/false`:
  correctly fails for process EOF before initialize (negative smoke case).
- `make check-style`: PASS, 134 Python files formatted, architecture checks pass.
- `uv run ruff check scripts/smoke_codex_runtime.py`: all checks passed.
- `uv run python scripts/check_contract.py`: 101 operations validated.
- `uv run python scripts/check_secrets.py`: PASS.

The executable is installed and protocol-ready. It is launched on demand, not as
an unauthenticated network daemon. Adex runtime routing/cutover, model inference,
native clients and remote Mac actions remain separate uncompleted integration
work; this installation does not imply feature parity or production readiness.

## Protocol transport contract

The Agent transport owns one app-server subprocess per isolated session. It must
correlate responses by request ID, preserve notifications and server requests,
bound input frames/event buffering, and fail pending calls on EOF or malformed
frames. RPC timeout is an uncertain outcome: never resend a turn automatically.
Closing the session terminates and reaps the child, including cancellation paths.
A transport is not an authorization gateway; server approval requests must be
surfaced to the Tools integration, never auto-accepted. No database migration is
required for this transport layer; durable owner/thread bindings precede cutover.

## Agent transport and existing-provider compatibility

The bounded asynchronous transport now lives in
`services/adex-agent/src/adex_agent/codex/transport.py`. It is not selected by the
production runtime yet. Six subprocess tests cover concurrent correlation,
notifications, EOF, invalid JSON, uncertain timeout, approval request delivery
and cancellation/reaping. The existing Agent suite reports **187 passed**.
`make check-style` passes (136 formatted Python source files, architecture pass).

The owner selected the existing Adex model interface. A bounded real probe using
existing private environment configuration confirmed Qwen `qwen3.8-flash` returns
HTTP 200 for both `/responses` and `/chat/completions`. More importantly, the
installed app-server 0.166.0 completed a real turn through the Qwen Responses
endpoint: initialized, ephemeral thread started, text delta received,
`turn/completed.status=completed`, no terminal error. The probe used an isolated
HOME/CODEX_HOME, read-only sandbox, shell disabled and web search disabled. It did
not use personal Codex authentication or execute a business action. Credentials
and response bodies were not saved to source or logs.

This demonstrates basic real text-stream compatibility, not tool-call parity,
images, budgets, long-turn recovery or complete kernel replacement. Remaining
cutover gates include mapping business tools to the existing authorization/effect
ledger, invocation bookkeeping, cancellation and checkpoint/fencing integration.
