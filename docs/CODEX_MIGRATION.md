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
