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


## Relative-time grammar correction

The reported `1分钟之后帮我整一下重要的新闻` previously passed the duration
parser but not the preceding intent gate: the gate only recognized 后 while the
parser recognized both 后 and 之后. This fell through to a model-generated promise
without a schedule row. Both now use the same compiled RELATIVE_TIME grammar, so
the routing and parsing languages cannot drift for these duration suffixes.
Negated requests remain excluded. Regression cases include the exact spoken request,
整理 variant, two/ten-minute 之后 requests and negative requests. The one-minute
integration case uses the user's exact wording and checks the occurrence, worker,
outbox, notification and original conversation backfill.
