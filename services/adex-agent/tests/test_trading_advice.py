from decimal import Decimal
import pytest
from adex_agent.skills.trading_advice import Advice, validate_order, render_advice


def test_order_research_handles_colloquial_request_and_explicit_negation():
    from adex_agent.skills.trading_advice import wants_advice
    for text in ("帮我下一台黄金订单", "不用图表，直接下单黄金", "不要问我，直接下单黄金"):
        assert wants_advice([{"role": "user", "content": text}])
    assert not wants_advice([{"role": "user", "content": "不要下单，解释一下XAUUSD"}])


def frozen_messages():
    import json
    from adex_agent.skills.trading_advice import EVIDENCE_PREFIX
    e = evidence()
    e.update({"mode": "TERMINAL_READ_ONLY", "account_mask": "PRIVATE_ACCOUNT", "orders": [{"ticket": 12345}],
              "frames": {name: [{"time": i+1, "open": 2600, "high": 2602, "low": 2598, "close": 2600}
                                for i in range(30)] for name in ("M1", "M5", "H4")}})
    return [{"role": "system", "content": EVIDENCE_PREFIX + json.dumps(e)}]


async def test_automatic_analysis_uses_closed_bars_and_excludes_private_account_data():
    import json
    from adex_agent.skills.trading_advice import automatic_advice
    class Runtime:
        prompts = []
        async def invoke(self, key, owner, messages):
            self.prompts.append(messages)
            yield {"type": "completed", "content": advice().model_dump_json()}
    runtime = Runtime()
    result = await automatic_advice(runtime, "owner", "turn", frozen_messages(), "帮我下一单黄金的交易")
    assert "2590" in result and "0.01" in result and "未提交" in result
    payload = json.loads(runtime.prompts[0][1]["content"])
    assert len(payload["market"]["frames"]["M1"]) == 29
    assert payload["market"]["frames"]["M1"][-1]["time_raw"] == 29
    assert "PRIVATE_ACCOUNT" not in json.dumps(payload) and "ticket" not in json.dumps(payload)


async def test_invalid_analysis_repaired_once_then_fails_without_asking_parameters():
    from adex_agent.skills.trading_advice import automatic_advice
    class Runtime:
        count = 0
        async def invoke(self, *args):
            self.count += 1
            yield {"type": "completed", "content": "已下单成功"}
    runtime = Runtime()
    result = await automatic_advice(runtime, "owner", "turn", frozen_messages(), "帮我下单")
    assert runtime.count == 2
    assert "没有产生可用草案" in result and "请补充" not in result


def test_malformed_candles_and_false_execution_claims_are_rejected():
    from adex_agent.skills.trading_advice import market_evidence, EVIDENCE_PREFIX
    import json
    data = json.loads(frozen_messages()[0]["content"].split(EVIDENCE_PREFIX)[1])
    data["frames"]["M1"][-1]["high"] = 1
    with pytest.raises(ValueError):
        market_evidence([{"role": "system", "content": EVIDENCE_PREFIX + json.dumps(data)}])
    with pytest.raises(ValueError):
        advice(reason="已下单成功")
    with pytest.raises(ValueError):
        advice(reason="请补充买卖方向")
    with pytest.raises(ValueError):
        advice(reason="English only")


def evidence():
    return {"symbol": "XAUUSD", "bid": 2600, "ask": 2601, "specification": {
        "trade_tick_size": 0.01, "volume_min": 0.01, "volume_step": 0.01,
        "trade_stops_level": 10, "point": 0.01,
    }}


def advice(**changes):
    return Advice.model_validate({"decision": "SETUP", "reason": "TEST_FIXTURE 多周期观察",
        "invalidation": "TEST_FIXTURE 结构失效", "order": {
            "kind": "BUY_LIMIT", "entry": "2590", "sl": "2580", "tp": "2610",
        }, **changes})


def test_generated_draft_contains_all_parameters_without_asking_user():
    a = advice()
    validate_order(a, evidence())
    text = render_advice(a)
    assert all(s in text for s in ("2590", "2580", "2610", "0.01", "未提交"))
    assert "？" not in text and "请补充" not in text


@pytest.mark.parametrize("order", [
    {"kind": "BUY_LIMIT", "entry": "2590", "sl": "2595", "tp": "2610"},
    {"kind": "BUY_STOP", "entry": "2590", "sl": "2580", "tp": "2610"},
    {"kind": "BUY_LIMIT", "entry": "2590.001", "sl": "2580", "tp": "2610"},
])
def test_invalid_model_prices_cannot_become_a_draft(order):
    with pytest.raises(ValueError):
        validate_order(advice(order=order), evidence())


def test_no_setup_and_insufficient_data_are_distinct_and_never_cancel_orders():
    for state in ("NO_SETUP", "INSUFFICIENT_DATA"):
        a = advice(decision=state, order=None)
        assert "未提交" in render_advice(a)
    with pytest.raises(ValueError):
        advice(decision="NO_SETUP")
    e = evidence()
    e["specification"]["volume_min"] = Decimal("0.1")
    with pytest.raises(ValueError):
        validate_order(advice(), e)
