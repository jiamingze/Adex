# Notes interaction verification — 2026-10-15

Scope: Today spacing, reply-to-note control and mobile note actions. No service,
contract or migration changes. The note APIs retain their revision checks and ownership.

## Commands

```bash
pnpm --dir apps/web build
make test-client
make check-style
uv run ruff check tests/fixtures/experience_server.py
uv run python scripts/check_secrets.py
uv run python tests/fixtures/product_gallery_server.py
```

Client tests: 21 passed. TypeScript/Vite build, style, architecture and secret checks passed.
Vite retains its existing large-chunk advisory; no bundle splitting is claimed here.

## Browser checks (synthetic data only)

- 390 × 844 viewport: measured 14px between all Today sections, including the
  result feed and automation card. Desktop uses 18px grid row gaps.
- Chat action order: quote → regenerate → copy → note. The note control has no
  visible text, but retains accessible labels/title and pending status.
- Visit the demo conversation with `?fault=notes-read-timeout`: detail reads delay
  12 seconds. Convert the static fixture reply, open it, return to the list and
  reopen. Both opens immediately show editable cached content, without “处理中…”.
  Uncached reads retain the existing bounded 8-second resource deadline.
- Hold a note for 650ms: the action sheet opens without navigating. Pin succeeds;
  reopening the menu shows “取消置顶”. Delete removes the fixture note from the list.

## Implemented safeguards (source review)

- Scroll movement over 10px, pointer cancel/leave and unmount cancel the hold timer.
  Right-click and Shift+F10 also expose the menu; Escape/backdrop dismiss it.
  Keyboard focus wraps among the menu buttons.
- New-note/back navigation advances the read epoch so late detail responses cannot
  replace the active view. Pinning a saved note updates its server copy and revision,
  preserving any independent unsaved editor text.

Evidence: [note action sheet](../images/notes-actions-mobile-fixture.jpg),
[Today module spacing](../images/today-module-spacing-mobile-fixture.jpg).
All pictured content is fictional. These UI checks do not establish live AI/provider
execution or physical iPhone touch acceptance; device build/install is separate.

## Device packaging

Rebuild with `uv run python scripts/prepare_ios.py`, then Xcode Debug build and
`xcrun devicectl device install app` using the currently paired device. Bundles and
signing material remain ignored local outputs. Never publish the private API endpoint
or device identifiers in this document.

Observed device result: signed Debug build succeeded; installation on the paired iPhone succeeded.
