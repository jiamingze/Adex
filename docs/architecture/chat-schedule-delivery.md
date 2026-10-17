# Chat schedule delivery

Chinese delivery requests such as `10分钟后发我下最新的新闻` and
`每天晚上19点发我最新的新闻` route to the existing schedule proposal path
before ordinary chat. Colloquial 发我 / 发给我 must not fall through to a model
that can merely claim a schedule exists.

App anchors one-shot deadlines to the durable turn timestamp, calls Automation
with the stable chat-schedule turn key, and renders a success card only from the
persisted schedule response. No new database migration or scheduler is required.

Verification: `uv run python scripts/test_stack.py tests/integration/test_chat_productivity.py -q`
passed four tests (68.32s), including the exact two user requests, schedule ownership,
600-second offset / daily 19:00 timing, retry deduplication, and a one-minute
occurrence → worker → outbox → original conversation result. Model/search and APNs
in this isolated test are fixtures; this does not assert a real news provider or
physical notification was exercised.
