# Vendored Codex

Repository: https://github.com/openai/codex
Commit: a4b4082b5f14a8a037386d823ddb96a85fd25975
Imported: 2026-10-30 via `git archive HEAD` from a verified SSH clone.
License: Apache-2.0; preserve `codex/LICENSE` and `codex/NOTICE`.
Local modifications: none at import. The snapshot excludes upstream .git data.

This is upstream source, not a built runtime or a completed Adex integration.
Build from `third_party/codex/codex-rs` using the pinned rust-toolchain.toml and
Cargo.lock: `cargo build --locked -p codex-app-server`.
Do not execute upstream development/install scripts implicitly during Adex startup.
Review upstream updates and keep their provenance separate from Adex patches.

The upstream contains public synthetic credential strings and test-only RSA keys.
Adex's scanner uses reviewed exact file hashes in
`codex-public-test-fixtures.json`, so edits invalidate those exceptions. Never use
those public test keys as application credentials. All 9,792 imported files were
byte-compared with the pinned upstream checkout.
