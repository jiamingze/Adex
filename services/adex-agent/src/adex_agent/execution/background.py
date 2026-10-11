"""Durable background execution; Automation exclusively owns claim, lease and fencing."""

import asyncio
import json
import os
from uuid import uuid4
from fastapi import HTTPException
from adex_kernel.core import digest
from adex_agent.models.provider import ProviderFailure


class BackgroundWorker:
    def __init__(self, core, runtime, checkpoints):
        self.core = core
        self.runtime = runtime
        self.checkpoints = checkpoints

    async def run_write(self, run, action, extra=None):
        body = {"epoch": run["epoch"], "attempt_id": run["attempt_id"]} | (extra or {})
        return await self.core.call(
            "automation",
            "run:write",
            "POST",
            f"/internal/runs/{run['id']}/{action}",
            body,
            owner=run["owner_id"],
            resource=run["id"],
        )

    async def background_run(self, run):
        failure_revision = None

        async def heartbeat():
            while True:
                await asyncio.sleep(10)
                await self.run_write(run, "heartbeat")

        async def execute():
            nonlocal failure_revision
            context = await self.runtime.context(run["owner_id"], run["origin_conversation_id"])
            revision = context["memory_revision"]
            failure_revision = revision
            saved = None
            if run.get("checkpoint_ref"):
                cp = await self.core.query(
                    "SELECT * FROM checkpoints WHERE id=%s AND run_id=%s AND owner_id=%s",
                    (run["checkpoint_ref"], run["id"], run["owner_id"]),
                    one=True,
                )
                if cp and digest(cp["state"]) == cp["sha256"] and cp["memory_revision"] == revision:
                    saved = cp["state"]
            if saved and saved.get("phase") == "result":
                result = saved
            elif run.get("kind") == "CALENDAR":
                approval = run["request"]["approval_id"]
                action = await self.core.call(
                    "tools",
                    "calendar:execute",
                    "POST",
                    "/internal/calendar/execute",
                    {
                        "approval_id": approval,
                        "run_id": str(run["id"]),
                        "epoch": run["epoch"],
                        "attempt_id": str(run["attempt_id"]),
                    },
                    owner=run["owner_id"],
                    resource=approval,
                )
                result = {
                    "schema_version": 1,
                    "phase": "result",
                    "content": "已按批准的草稿写入日历。事件 ID：" + str(action["uid"]),
                    "completed_steps": ["calendar"],
                    "pending_effects": [],
                    "usage": {},
                }
            elif run.get("kind") in ("IMAGE", "AUDIO", "VIDEO"):
                request = run.get("request", {})
                if isinstance(request, str):
                    request = json.loads(request)
                media = await self.core.call(
                    "tools",
                    "creative:write",
                    "POST",
                    "/internal/creative/generate",
                    {
                        "kind": run["kind"],
                        "prompt": run["instruction"],
                        "request_key": str(run["id"]),
                        "provider": request.get("provider", "mock"),
                        "rights_confirmed": request.get("rights_confirmed", False),
                        "input_refs": request.get("input_refs", []),
                        "params": request.get("params", {}),
                        "run_id": str(run["id"]),
                        "epoch": run["epoch"],
                        "attempt_id": str(run["attempt_id"]),
                    },
                    owner=run["owner_id"],
                )
                result = {
                    "schema_version": 1,
                    "phase": "result",
                    **media,
                    "completed_steps": ["media"],
                    "pending_effects": [],
                    "usage": {},
                    "provider": media.get("artifact", {}).get("model_id", "unknown"),
                }
            else:
                if saved and saved.get("phase") == "plan" and saved.get("messages"):
                    messages = saved["messages"]
                    evidence = saved.get("travel_evidence")
                else:
                    context["messages"].append({"role": "user", "content": run["instruction"], "seq": 0})
                    kind = run.get("kind", "CHAT")
                    travel_request = run.get("request", {}).get("travel")
                    if kind == "TRAVEL" and travel_request:
                        evidence = await self.core.call(
                            "tools",
                            "travel:read",
                            "POST",
                            "/internal/travel",
                            travel_request,
                            owner=run["owner_id"],
                        )
                        context["messages"][-1]["content"] += (
                            "\n真实旅行证据（候选城市如有歧义须告知，未验证库存）："
                            + json.dumps(evidence, ensure_ascii=False)[:16000]
                        )
                    policies = {
                        "RESEARCH": "进行有来源的研究，比较证据、局限和结论，输出可下载的 Markdown 报告。",
                        "TRAVEL": "输出可编辑的逐日旅行计划，必须附来源URL与抓取时间。未核实价格/库存要明确标记，不得编造坐标。提供地点的地图搜索链接。",
                        "GAME": "生成完整可运行的单文件 HTML 小游戏，代码置于 html 代码块，禁止网络请求/外部脚本/读取Cookie/存储。",
                        "DIAGRAM": "生成可编辑 Mermaid 图，仅允许 flowchart、sequenceDiagram 或 classDiagram，无click、HTML、外部链接或初始化指令。输出 mermaid代码块。",
                    }
                    if kind in policies:
                        context["messages"][-1]["content"] += "\n" + policies[kind]
                    search = kind in ("RESEARCH", "TRAVEL") or any(
                        word in run["instruction"] for word in ("搜索", "新闻", "最新", "简报", "search")
                    )
                    messages = await self.runtime.messages(
                        context, search=search, research=kind == "RESEARCH"
                    )
                state = {
                    "schema_version": 1,
                    "phase": "plan",
                    "instruction": run["instruction"],
                    "messages": messages,
                    "completed_steps": [],
                    "travel_evidence": evidence if "evidence" in locals() else None,
                    "pending_effects": [],
                    "budget": {"max_model_calls": 1},
                }
                ref = await self.checkpoints.save_checkpoint(run, f"plan:{run['epoch']}", state, revision)
                await self.run_write(run, "checkpoint", {"checkpoint_ref": ref})
                output = None
                async for e in self.runtime.invoke(
                    f"run:{run['id']}:answer:memory:{revision}", run["owner_id"], messages
                ):
                    if e["type"] == "completed":
                        output = e
                if output is None:
                    raise ProviderFailure("PROVIDER_UNKNOWN")
                result = {
                    "schema_version": 1,
                    "phase": "result",
                    "content": output["content"],
                    "completed_steps": ["answer"],
                    "artifact": {"travel": evidence}
                    if run.get("kind") == "TRAVEL" and "evidence" in locals()
                    else {},
                    "pending_effects": [],
                    "usage": output["usage"],
                    "provider": output["provider"],
                }
            if run.get("kind") in ("RESEARCH", "TRAVEL", "GAME", "DIAGRAM") and not result.get(
                "artifact", {}
            ).get("file_id"):
                import re

                source = result["content"]
                language = {"GAME": "html", "DIAGRAM": "mermaid"}.get(run["kind"])
                if language:
                    match = re.search(r"```" + language + r"\s*\n([\s\S]*?)```", source, re.I)
                    if not match:
                        raise ProviderFailure("ARTIFACT_SOURCE_REQUIRED")
                    source = match.group(1)
                imported = await self.core.call(
                    "tools",
                    "artifact:write",
                    "POST",
                    "/internal/artifacts/import",
                    {"kind": run["kind"], "source": source, "request_key": str(run["id"])},
                    owner=run["owner_id"],
                )
                result["artifact"] = {**result.get("artifact", {}), **imported}
            if run.get("kind") == "GAME" and not result.get("artifact", {}).get("runner"):
                import re

                source = re.search(r"```html\s*\n([\s\S]*?)```", result["content"], re.I)
                if source:
                    checked = await self.core.call(
                        "tools",
                        "code:check",
                        "POST",
                        "/internal/game/check",
                        {"source": source.group(1)},
                        owner=run["owner_id"],
                    )
                    result["artifact"] = {
                        **result.get("artifact", {}),
                        "runner": checked,
                        "source_format": "html",
                    }
                else:
                    result["artifact"] = {"runner": {"status": "FAILED", "reason": "HTML_SOURCE_REQUIRED"}}
            ref = await self.checkpoints.save_checkpoint(run, f"result:{run['epoch']}", result, revision)
            await self.run_write(run, "checkpoint", {"checkpoint_ref": ref})
            gate = os.getenv("ADEX_TEST_CHECKPOINT_GATE")
            if gate and os.getenv("ADEX_MODEL_PROVIDER") == "mock":
                from pathlib import Path

                Path(gate).write_text(ref)
                while Path(gate).exists():
                    await asyncio.sleep(0.1)
            await self.run_write(run, "complete", {"checkpoint_ref": ref})

        work = asyncio.create_task(execute())
        beat = asyncio.create_task(heartbeat())
        try:
            done, _ = await asyncio.wait({work, beat}, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except Exception as e:
            code = (
                e.code
                if isinstance(e, ProviderFailure)
                else str(e.detail)
                if isinstance(e, HTTPException)
                else "WORKER_ERROR"
            )
            try:
                await self.run_write(
                    run,
                    "fail",
                    {
                        "code": code if code.replace("_", "").isalnum() else "WORKER_ERROR",
                        **({"memory_revision": failure_revision} if failure_revision is not None else {}),
                    },
                )
            except Exception:
                pass
        finally:
            work.cancel()
            beat.cancel()
            await asyncio.gather(work, beat, return_exceptions=True)

    async def worker(self):
        worker = "agent-" + str(uuid4())
        while True:
            try:
                claim = await self.core.call(
                    "automation", "run:claim", "POST", "/internal/runs/claim", {"worker_id": worker}
                )
                if claim.get("run"):
                    await self.background_run(claim["run"])
                else:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(3)
