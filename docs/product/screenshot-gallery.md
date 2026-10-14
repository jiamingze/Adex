# Product screenshot gallery / 产品演示截图

The README gallery uses only hand-written synthetic data. All accounts, conversations,
calendar events, tasks, approvals, results and notes are fictional. Every image carries
an “演示数据 · Synthetic demo” badge. No production database, model, OAuth account or
personal media is accessed. Model names in the UI identify selector options; the
pictured reply is a static fixture, not a live model response.

## Reproduce locally

```bash
pnpm --dir apps/web build
uv run python tests/fixtures/product_gallery_server.py
```

Open **http://127.0.0.1:18117/** in a separate browser profile if an old fixture session
exists. The server binds only to loopback and must never be deployed or exposed through
a tunnel. It imports the existing experience fixture, modifies only its own process
memory, and has no database/provider client. Fixture edits disappear when it stops.
Stop with Ctrl+C. Do not run alongside the experience fixture on the same port.

Capture Today, Chat, Todo and Notes in light mode. Open the synthetic note to show the
editor. Desktop screenshots use the normal browser viewport (1280 × 720 at capture time).
Mobile screenshots use an explicit 390 × 844 viewport; reset the override afterwards.
Use the same fixture and save these as `*-mobile.jpg`. Mobile captures show responsive
Web UI, not a physical iPhone or its native keyboard.
To include synthetic calendar examples, visit `/today?fault=calendar-plan`; this cookie
activates only the fixture calendar query. Never log in with a real account here.

Save JPEGs under `docs/images/gallery/`, visually inspect each image, and update both
README versions together. Avoid real browser tabs, notifications, device screenshots,
profile names, credentials, private URLs and personal artifacts. Do not substitute an
old screenshot whose data provenance is unknown. The current gallery replaces the old
README screenshots; historical files elsewhere are not part of this gallery.

## Scope / 展示边界

- Today: priority tasks, pending approval, synthetic calendar agenda and result feed.
- Chat: static Markdown answer, model selector and reply-to-note action.
- Todo: flat list, separate importance/urgency tags and status filters.
- Notes: synthetic private-note list and editor.

Both desktop and mobile images are Web UI illustrations. They establish neither real external action
success nor native iPhone keyboard, voice, photo or notification acceptance. Missing
real Google/APNs/provider configuration remains `BLOCKED_EXTERNAL` as documented in
the implementation status.

全部图片均使用人工编写的虚构内容，仅展示现有界面，不使用真实用户数据，
也不将演示服务的返回值当作模型生成或第三方执行成功的证据。
