import json
from datetime import datetime, timezone, timedelta
from adex_agent.execution.notification import validate_assessment
from adex_agent.routing.notification import notification_plan

RULE = {"description": "TEST_FIXTURE 黄金低于800元/克", "operator": "lt", "threshold": "800", "unit": "CNY/g"}


def source(value="790"):
    return {
        "url": "https://example.test/quote",
        "text": f"TEST_FIXTURE 黄金现价 {value} 元/克，仅测试数据",
        "source_kind": "BROWSER_RENDERED_PAGE",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def test_numeric_condition_recomputes_verdict_and_rejects_missing_or_snippet_evidence():
    observed = source("810")
    raw = {
        "status": "MET",
        "value": "810",
        "unit": "CNY/g",
        "evidence": [{"url": observed["url"], "quote": observed["text"]}],
    }
    assert validate_assessment(RULE, [observed], raw)["status"] == "NOT_MET"
    raw["value"] = "790"
    assert validate_assessment(RULE, [observed], raw)["status"] == "UNKNOWN"
    observed = source("790")
    raw["evidence"][0]["quote"] = observed["text"]
    assert validate_assessment(RULE, [observed], raw)["status"] == "MET"
    assert (
        validate_assessment(RULE, [{**observed, "source_kind": "SEARCH_SNIPPET"}], raw)["status"] == "UNKNOWN"
    )
    assert validate_assessment(RULE, [], raw)["status"] == "UNKNOWN"
    old = {**observed, "fetched_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()}
    assert validate_assessment(RULE, [old], raw)["status"] == "UNKNOWN"
    raw["unit"] = "USD/oz"
    assert validate_assessment(RULE, [observed], raw)["status"] == "UNKNOWN"


async def test_semantic_notification_plan_preserves_condition_and_fails_closed():
    class Runtime:
        output = {"notification_policy": "CONDITION_MET", "notification_condition": RULE}

        async def invoke(self, *args):
            yield {"type": "completed", "content": json.dumps(self.output)}

    runtime = Runtime()
    assert (await notification_plan(runtime, "owner", "key", "TEST_FIXTURE"))[
        "notification_condition"
    ] == RULE
    runtime.output = {"notification_policy": "CONDITION_MET"}
    assert "clarification" in await notification_plan(runtime, "owner", "key", "TEST_FIXTURE")
