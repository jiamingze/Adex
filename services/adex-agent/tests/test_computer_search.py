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
