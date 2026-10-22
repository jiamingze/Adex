import copy
import json
from types import SimpleNamespace
import pytest
from adex_agent.execution.agent_loop import DurableAgentLoop, Step


class Worker:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.saved = []
        self.calls = []
        self.runtime = SimpleNamespace(invoke=self.invoke)
        self.checkpoints = SimpleNamespace(save_checkpoint=self.save)
        self.core = SimpleNamespace(call=self.call)

    async def invoke(self, key, owner, messages):
        yield {"type": "completed", "content": json.dumps(next(self.outputs))}

    async def save(self, run, key, state, revision):
        self.saved.append(copy.deepcopy(state))
        return str(len(self.saved))

    async def run_write(self, *args):
        pass

    async def call(self, *args, **kwargs):
        self.calls.append(args)
        return {"items": [{"url": "https://example.com/report", "content": "Observed source"}]}


def run():
    return {
        "id": "run",
        "owner_id": "owner",
        "instruction": "compare sources",
        "request": {"params": {"acceptance": ["source"]}},
    }


async def test_loop_commits_before_dispatch_and_verifies_observed_evidence():
    worker = Worker(
        [
            {"tool": "search", "query": "source", "summary": "查找一手来源"},
            {"tool": "read", "url": "https://example.com/report", "summary": "来源待核对"},
            {
                "tool": "finish",
                "content": "Report",
                "citations": ["https://example.com/report"],
                "checks": [
                    {"criterion": "source", "met": True, "evidence_urls": ["https://example.com/report"]}
                ],
            },
        ]
    )
    result = await DurableAgentLoop(worker).run(run(), {"memory_revision": 1})
    assert worker.saved[0]["pending"]["tool"] == "search"
    assert len(worker.calls) == 2 and result["artifact"]["workflow_status"] == "VERIFIED"
    assert worker.saved[-1]["pending"] is None


async def test_resume_pending_read_and_keep_prior_work_without_restart():
    worker = Worker([{"tool": "finish", "content": "Partial report"}])
    saved = {
        "schema_version": 1,
        "phase": "agent_loop",
        "goal": "goal",
        "acceptance": ["source"],
        "summary": "已有发现",
        "steps": [{"observation": {"items": [{"url": "https://example.com/report", "content": "source"}]}}],
        "pending": Step(tool="read", url="https://example.com/report").model_dump(),
    }
    result = await DurableAgentLoop(worker).run(run(), {"memory_revision": 1}, saved)
    assert len(worker.calls) == 1 and len(saved["steps"]) == 2
    assert result["artifact"]["workflow_status"] == "PARTIAL"


async def test_repeat_breaker_and_forged_sources_cannot_claim_verified():
    worker = Worker([{"tool": "search", "query": "same"}] * 3)
    result = await DurableAgentLoop(worker).run(run(), {"memory_revision": 1})
    assert len(worker.calls) == 2 and result["artifact"]["workflow_status"] == "PARTIAL"
    step = Step(
        tool="finish",
        content="Done",
        citations=["https://fake.test"],
        checks=[{"criterion": "source", "met": True, "evidence_urls": ["https://fake.test"]}],
    )
    assert (
        DurableAgentLoop(worker).result({"steps": [], "acceptance": ["source"]}, step)["artifact"][
            "workflow_status"
        ]
        == "PARTIAL"
    )


def test_closed_loop_rejects_writes():
    with pytest.raises(ValueError):
        Step(tool="purchase", content="done")


async def test_invalid_tool_calls_stop_without_dispatching_or_granting_new_budget():
    worker = Worker([{"tool": "purchase"}, {"tool": "shell"}])
    result = await DurableAgentLoop(worker).run(run(), {"memory_revision": 1})
    assert not worker.calls and result["artifact"]["workflow_status"] == "PARTIAL"
    assert result["artifact"]["step_count"] == 2
