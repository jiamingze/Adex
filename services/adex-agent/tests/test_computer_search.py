"""Search planning must not inspect unrelated tabs or expose account/footer data."""

import json
from types import SimpleNamespace
from adex_agent.computer.workflow import ComputerWorkflow


async def test_search_reads_only_after_checkpoint_and_summarizes_result_evidence():
    calls, checkpoints, messages = [], [], []

    async def call(*args, **kwargs):
        calls.append(args[4])
        assert checkpoints and args[4]["search_query"] == "CET版"
        return {
            "nodes": [
                {"role": "AXButton", "title": "TEST_FIXTURE private account"},
                {"role": "AXLink", "title": "CET 官方", "url": "https://cet.neea.edu.cn/"},
                {"role": "AXStaticText", "title": "TEST_FIXTURE 考试信息"},
                {"role": "AXButton", "title": "TEST_FIXTURE private location"},
            ]
        }

    async def save(*args):
        checkpoints.append(args)
        return "fixture-checkpoint"

    async def write(*args):
        assert args[1] == "checkpoint"

    async def invoke(key, owner, value):
        messages.append(value)
        plan = (
            {"action": "search", "text": "CET版"}
            if len(messages) == 1
            else {"action": "done", "text": "CET 官方 https://cet.neea.edu.cn/"}
        )
        yield {"type": "completed", "content": json.dumps(plan, ensure_ascii=False)}

    worker = SimpleNamespace(
        core=SimpleNamespace(call=call),
        checkpoints=SimpleNamespace(save_checkpoint=save),
        run_write=write,
        runtime=SimpleNamespace(invoke=invoke),
    )
    run = {
        "id": "run",
        "owner_id": "owner",
        "epoch": 1,
        "attempt_id": "attempt",
        "instruction": "Chrome 搜索CET版",
        "request": {"params": {"app_name": "Chrome"}},
    }
    result = await ComputerWorkflow(worker).run(run, {"memory_revision": 1}, None)
    assert len(calls) == 1
    assert json.loads(messages[0][1]["content"])["observation"]["status"] == "not_observed"
    assert "private account" not in messages[1][1]["content"]
    assert "private location" not in messages[1][1]["content"]
    assert "TEST_FIXTURE 考试信息" in messages[1][1]["content"]
    assert result["artifact"]["computer_status"] == "DONE"


def test_search_report_is_structured_and_uses_only_verified_named_links():
    from adex_agent.computer.results import search_report

    rows = [
        {
            "title": "上海景点指南",
            "url": "https://example.com/shanghai",
            "snippet": "  外滩、豫园与博物馆。 ",
        },
        {"title": "重复", "url": "https://example.com/shanghai"},
        {"title": "坏链接", "url": "javascript:alert(1)"},
    ]
    text = search_report("上海怎么玩", rows, "2026-10-23 22:00")
    assert text.startswith("### “上海怎么玩”的搜索结果\n\n")
    assert "1. **[上海景点指南](https://example.com/shanghai)**\n   外滩" in text
    assert "重复" not in text and "javascript:" not in text
    assert "桌面操作已停止" not in text
    assert "查询时间：2026-10-23 22:00" in text


def test_result_extracts_heading_and_real_excerpt_instead_of_repeating_link_label():
    from adex_agent.computer.results import observed_results

    result = observed_results(
        [
            {
                "id": "0.1",
                "role": "AXLink",
                "title": "上海景点 网站 https://example.com",
                "url": "https://example.com",
            },
            {"id": "0.1.0", "role": "AXHeading", "title": "上海景点"},
            {"id": "0.1.0.0", "role": "AXStaticText", "value": "上海景点"},
            {"id": "0.2", "role": "AXButton", "title": "更多"},
            {"id": "0.3", "role": "AXStaticText", "value": "外滩与豫园适合首次来访的游客。"},
            {"id": "0.4", "role": "AXLink", "title": "下一条", "url": "https://example.org"},
        ]
    )
    assert result[0]["title"] == "上海景点"
    assert result[0]["snippet"] == "外滩与豫园适合首次来访的游客。"


async def test_operator_repairs_wrong_search_fields_without_any_execution():
    from adex_agent.computer.planner import plan_operation

    calls = []

    class Runtime:
        async def invoke(self, key, owner, messages):
            calls.append(messages)
            yield {
                "type": "completed",
                "content": json.dumps(
                    {"action": "search", **({"query": "CET版"} if len(calls) == 1 else {"text": "CET版"})}
                ),
            }

    result = await plan_operation(
        Runtime(),
        "owner",
        "fixture-plan",
        [{"role": "system", "content": "COMPUTER_OPERATOR_V1"}, {"role": "user", "content": "TEST_FIXTURE"}],
        {"status": "not_observed"},
    )
    assert result.action == "search" and result.text == "CET版" and len(calls) == 2
    assert "extra_forbidden" in calls[1][-1]["content"]


async def test_navigation_is_allowed_as_first_action_and_empty_block_is_repaired():
    from adex_agent.computer.planner import plan_operation
    import json
    class Runtime:
        def __init__(self, plans): self.plans=iter(plans)
        async def invoke(self,*args):yield {'type':'completed','content':json.dumps(next(self.plans))}
    runtime=Runtime([{'action':'navigate','text':'https://www.youtube.com/'}])
    plan=await plan_operation(runtime,'owner','key',[{'role':'system','content':''}],{'status':'not_observed'})
    assert plan.action=='navigate'
    runtime=Runtime([{'action':'blocked','text':''},{'action':'blocked','text':'页面显示网络连接失败'}])
    plan=await plan_operation(runtime,'owner','key',[{'role':'system','content':''}],{})
    assert plan.text=='页面显示网络连接失败'


async def test_navigation_is_checkpointed_before_dispatch_and_returns_observed_link():
    calls, checkpoints = [], []
    async def call(*args, **kwargs):
        assert checkpoints
        assert args[4]['navigate_url']=='https://example.com/'
        calls.append(args)
        return {'nodes':[{'role':'AXLink','title':'Example','url':'https://example.com/item'}]}
    async def save(*args):checkpoints.append(args);return 'checkpoint'
    async def write(*args):pass
    plans=iter([{'action':'navigate','text':'https://example.com/'},{'action':'done','text':'[Example](https://example.com/item)'}])
    async def invoke(*args):yield {'type':'completed','content':json.dumps(next(plans))}
    worker=SimpleNamespace(core=SimpleNamespace(call=call),checkpoints=SimpleNamespace(save_checkpoint=save),run_write=write,runtime=SimpleNamespace(invoke=invoke))
    run={'id':'run','owner_id':'owner','epoch':1,'attempt_id':'attempt','instruction':'打开网站返回链接','request':{'params':{'app_name':'Chrome'}}}
    result=await ComputerWorkflow(worker).run(run,{'memory_revision':1},None)
    assert result['artifact']['computer_status']=='DONE'
    assert len(calls)==1
    assert 'https://example.com/item' in result['content']


async def test_stale_pre_dispatch_refusal_reobserves_instead_of_failing_or_replaying():
    calls=[]
    async def call(*args,**kwargs):
        calls.append(args[3])
        if args[3].endswith('/step'):return {'status':'REOBSERVE_REQUIRED','action_id':'old'}
        return {'nodes':[{'role':'AXStaticText','title':'Fresh page'}]}
    async def save(*args):return 'checkpoint'
    async def write(*args):pass
    async def invoke(*args):yield {'type':'completed','content':json.dumps({'action':'done','text':'已重新读取页面'})}
    worker=SimpleNamespace(core=SimpleNamespace(call=call),checkpoints=SimpleNamespace(save_checkpoint=save),run_write=write,runtime=SimpleNamespace(invoke=invoke))
    current={'id':'run','owner_id':'owner','epoch':1,'attempt_id':'attempt','instruction':'Read page','request':{'params':{'app_name':'Chrome'}}}
    saved={'phase':'computer_waiting','completed_steps':[],'pending':{'approval_id':'old','step':{'action':'set_value','element_id':'1','text':'test'}}}
    result=await ComputerWorkflow(worker).run(current,{'memory_revision':1},saved)
    assert result['artifact']['computer_status']=='DONE'
    assert calls==['/internal/computer/step','/internal/computer/observe']
    assert result['completed_steps'][0]['receipt']=='NOT_APPLIED_STALE'


async def test_identical_observations_stop_before_exhausting_model_budget():
    calls, plans = [], []
    async def call(*args, **kwargs):
        calls.append(args[3])
        return {"observation_id": str(len(calls)), "nodes": [{"role": "AXStaticText", "title": "Loading"}]}
    async def invoke(*args):
        plans.append(args)
        yield {"type": "completed", "content": json.dumps({"action": "observe"})}
    worker = SimpleNamespace(core=SimpleNamespace(call=call), runtime=SimpleNamespace(invoke=invoke))
    run = {"id": "run", "owner_id": "owner", "epoch": 1, "attempt_id": "attempt", "instruction": "读取行情", "request": {"params": {"app_name": "TEST_FIXTURE"}}}
    result = await ComputerWorkflow(worker).run(run, {"memory_revision": 1}, None)
    assert result["artifact"]["reason"] == "NO_OBSERVATION_PROGRESS"
    assert len(plans) < 8
    assert all(path.endswith("/observe") for path in calls)


async def test_visual_evidence_reaches_planner_without_becoming_an_action_target():
    async def call(*args, **kwargs):
        return {"nodes": [], "visual_status": "OBSERVED", "visual_text": "TEST_FIXTURE 09961 BOLL MID:307.520"}
    async def invoke(key, owner, messages):
        view = json.loads(messages[1]["content"])
        if view["observation"].get("status") == "not_observed":
            action = {"action": "observe"}
        else:
            assert "09961" in view["read_only_visual_evidence"]["text"]
            assert view["read_only_visual_evidence"]["status"] == "OBSERVED"
            assert view["observation"]["nodes"] == []
            action = {"action": "done", "text": "TEST_FIXTURE 已读取"}
        yield {"type": "completed", "content": json.dumps(action)}
    worker = SimpleNamespace(core=SimpleNamespace(call=call), runtime=SimpleNamespace(invoke=invoke))
    run = {"id": "run", "owner_id": "owner", "epoch": 1, "attempt_id": "attempt", "instruction": "读取行情", "request": {"params": {"app_name": "TEST_FIXTURE"}}}
    result = await ComputerWorkflow(worker).run(run, {"memory_revision": 1}, None)
    assert result["artifact"]["computer_status"] == "DONE"


async def test_native_search_preserves_visual_evidence_without_requiring_web_links():
    calls, checkpoints = [], []
    async def call(*args, **kwargs):
        assert checkpoints
        calls.append(args[4])
        return {"bundle_id": "fixture.native", "nodes": [], "visual_status": "OBSERVED", "visual_text": "TEST_FIXTURE 09961 BOLL MID:307.520"}
    async def save(*args): checkpoints.append(args); return "checkpoint"
    async def write(*args): pass
    async def invoke(key, owner, messages):
        view = json.loads(messages[1]["content"])
        action = {"action": "search", "text": "09961"} if not calls else {"action": "done", "text": "TEST_FIXTURE 09961 BOLL MID:307.520"}
        if calls: assert "BOLL" in view["read_only_visual_evidence"]["text"]
        yield {"type": "completed", "content": json.dumps(action)}
    worker = SimpleNamespace(core=SimpleNamespace(call=call), runtime=SimpleNamespace(invoke=invoke), checkpoints=SimpleNamespace(save_checkpoint=save), run_write=write)
    run = {"id": "run", "owner_id": "owner", "epoch": 1, "attempt_id": "attempt", "instruction": "读取行情", "request": {"params": {"app_name": "TEST_FIXTURE"}}}
    result = await ComputerWorkflow(worker).run(run, {"memory_revision": 1}, None)
    assert result["artifact"]["computer_status"] == "DONE"
    assert calls[0]["search_query"] == "09961"


async def test_conflicting_evidence_cannot_be_reported_as_successful_analysis():
    from adex_agent.computer.planner import plan_operation
    plans = iter([{"action": "done", "evidence_status": "conflicting", "text": "TEST_FIXTURE forecast"}, {"action": "blocked", "evidence_status": "conflicting", "text": "TEST_FIXTURE conflicting instruments"}])
    async def invoke(*args): yield {"type": "completed", "content": json.dumps(next(plans))}
    result = await plan_operation(SimpleNamespace(invoke=invoke), "owner", "key", [{"role": "system", "content": ""}], {})
    assert result.action == "blocked" and result.evidence_status == "conflicting"


async def test_indicator_value_cannot_replace_native_spatial_quote_readback():
    from adex_agent.computer.planner import plan_operation
    plans = iter([{"action": "done", "text": "TEST_FIXTURE", "quote_instrument": "09961", "quote_price": "307.520"}, {"action": "done", "text": "TEST_FIXTURE", "quote_instrument": "09961", "quote_price": "314.8"}])
    async def invoke(*args): yield {"type": "completed", "content": json.dumps(next(plans))}
    result = await plan_operation(SimpleNamespace(invoke=invoke), "owner", "key", [{"role": "system", "content": ""}], {"primary_numeric_readback": {"context": "09961", "value": "314.800", "line_ids": [1]}})
    assert result.quote_price == "314.8"
