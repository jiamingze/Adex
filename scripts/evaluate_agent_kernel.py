"""Opt-in paid-model evaluation using synthetic snapshots; never writes application DBs."""

import argparse
import asyncio
import json
import os
from uuid import uuid4
from datetime import datetime
from zoneinfo import ZoneInfo

from config import load
from adex_agent.models.provider import provider
from adex_agent.actions.planner import plan_task
from adex_agent.memory.planner import propose

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--live",
    action="store_true",
    required=True,
    help="Explicitly enable paid Qwen calls with synthetic input",
)
parser.parse_args()

for k, v in load().items():
    if k.startswith(("DASHSCOPE_", "ADEX_MAX_OUTPUT")):
        os.environ[k] = v


class Runtime:
    provider_mode = "qwen"
    provider = provider("qwen")

    async def invoke(self, key, owner, messages):
        async for e in self.provider.stream(messages):
            yield e


async def main():
    runtime = Runtime()
    sid = str(uuid4())
    mid = str(uuid4())
    base = {
        "now": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "history": [],
        "todos": [],
        "schedules": [
            {
                "id": sid,
                "title": "每日新闻",
                "revision": 2,
                "status": "ACTIVE",
                "kind": "DAILY",
                "local_time": "08:00",
                "timezone": "Asia/Shanghai",
                "instruction": "整理最新新闻",
            }
        ],
    }
    for query in [
        "10分钟后发我下最新的新闻",
        "以后新闻放到每天晚上19点发吧",
        "每10分钟检查上海黄金交易所Au99.99现货价格，低于800元/克才通知我",
        "把两个数据库的官方文档都研究一下，从一致性、备份恢复、运维成本比较PostgreSQL和SQLite，给出有来源的报告",
    ]:
        result = await plan_task(
            runtime, "synthetic", "live-" + str(uuid4()), {**base, "request": query}
        )
        print(
            json.dumps(
                {
                    "query": query,
                    "tool": result["tool"],
                    "arguments": result["arguments"],
                },
                ensure_ascii=False,
            )
        )
        if query.startswith("以后"):
            assert (
                result["tool"] == "schedule.update"
                and result["arguments"]["local_time"] == "19:00"
            )
        elif query.startswith("每10"):
            assert (
                result["tool"] == "schedule.create"
                and result["arguments"]["notification_policy"] == "CONDITION_MET"
            )
        elif query.startswith("把两个"):
            assert result["tool"] == "workflow.start"
        else:
            assert result["tool"] == "schedule.create"
    for query in [
        "我平时真受不了辣的，推荐餐厅注意点哈",
        "我搬去杭州长期住了，以后按杭州推荐吧",
    ]:
        result = await propose(
            runtime,
            "synthetic",
            str(uuid4()),
            {
                "latest": query,
                "memories": [
                    {
                        "id": mid,
                        "revision": 1,
                        "content": "用户常住上海。",
                        "truncated": False,
                    }
                ],
                "recent": [],
            },
        )
        print(json.dumps({"query": query, "plan": result}, ensure_ascii=False))
        assert result["mode"] == "learn"
    recall_id = str(uuid4())
    recalled = await propose(
        runtime,
        "synthetic",
        str(uuid4()),
        {
            "latest": "帮我推荐适合我的晚餐",
            "recent": [],
            "memories": [
                {
                    "id": recall_id,
                    "revision": 1,
                    "content": "用户不吃辣；推荐餐厅和菜品时避免辛辣。",
                    "truncated": False,
                }
            ],
        },
    )
    assert recall_id in recalled["recalled_ids"] and recalled["mode"] == "none"
    print(
        "Semantic recall: PASS; seven synthetic live-model cases passed. No application DB writes."
    )


asyncio.run(main())
