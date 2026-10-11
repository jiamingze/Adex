"""Interactive intent routing and streaming execution, independent of HTTP transport."""

from adex_agent.models.provider import ProviderFailure, provider
import copy
import json
import os


class InteractiveTurnService:
    def __init__(self, core, runtime):
        self.core = core
        self.runtime = runtime

    async def events(self, body):
        try:
            from adex_agent.routing.intent import original_music_intent, search_intent, background_kind

            latest = next(
                (m["content"] for m in reversed(body.context["messages"]) if m["role"] == "user"), ""
            )
            import re

            from adex_agent.routing.intent import schedule_intent

            if schedule_intent(latest):
                from adex_agent.routing.schedule import daily_chat_draft

                draft = daily_chat_draft(latest)
                if draft:
                    yield (
                        json.dumps({"type": "schedule.requested", "draft": draft}, ensure_ascii=False) + "\n"
                    )
                else:
                    yield (
                        json.dumps(
                            {
                                "type": "completed",
                                "content": "可以为你设置定时任务。请补充明确的执行时间，例如：每天上午8点汇总 SpaceX 最新消息。",
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                return
            from adex_agent.routing.intent import image_intent

            if image_intent(latest):
                yield (
                    json.dumps(
                        {
                            "type": "task.requested",
                            "kind": "IMAGE",
                            "instruction": latest,
                            "request": {
                                "provider": os.getenv("ADEX_IMAGE_PROVIDER", "dashscope"),
                                "rights_confirmed": True,
                                "params": {"width": 1024, "height": 1024},
                            },
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                return
            if re.search(r"(生成|制作|创作|做).*(视频|短片)", latest):
                duration_match = re.search(r"(\d+)\s*秒", latest)
                duration = int(duration_match[1]) if duration_match else 5
                if not 2 <= duration <= 30:
                    raise ProviderFailure("INVALID_MEDIA_DURATION")
                yield (
                    json.dumps(
                        {
                            "type": "task.requested",
                            "kind": "VIDEO",
                            "instruction": latest,
                            "request": {
                                "provider": os.getenv("ADEX_VIDEO_PROVIDER", "mock"),
                                "rights_confirmed": True,
                                "params": {"duration_seconds": duration},
                            },
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                return
            if original_music_intent(latest):
                audio_limit = 600
                duration = min(180, audio_limit)
                match = re.search(r"(\d+(?:\.\d+)?)\s*(分钟|秒)", latest)
                if match:
                    duration = float(match[1]) * (60 if match[2] == "分钟" else 1)
                if not 1 <= duration <= audio_limit:
                    yield (
                        json.dumps(
                            {
                                "type": "completed",
                                "content": f"当前音乐模型单次支持最多{audio_limit}秒。请指定这个范围内的时长，例如：生成两分钟浪漫钢琴曲。",
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    return
                provider_name = os.getenv("ADEX_MUSIC_PROVIDER", "mock")
                yield (
                    json.dumps(
                        {
                            "type": "task.requested",
                            "kind": "AUDIO",
                            "instruction": latest,
                            "request": {
                                "provider": provider_name,
                                "rights_confirmed": True,
                                "params": {
                                    "duration_seconds": duration,
                                    "mode": "vocals"
                                    if re.search(r"人声|歌词|演唱", latest)
                                    else "instrumental",
                                },
                            },
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                return
            if re.search(r"(搜索|找|推荐|播放).*(歌曲|音乐|歌单)|(歌曲|音乐|歌单).*(搜索|推荐)", latest):
                from psycopg.types.json import Jsonb
                from adex_kernel.core import digest

                hash_value = digest({"context": body.context, "kind": "music"})
                old = await self.core.query(
                    "SELECT * FROM interactive_tool_results WHERE invocation_key=%s",
                    (body.invocation_key,),
                    one=True,
                )
                if old and (str(old["owner_id"]) != str(body.owner_id) or old["request_hash"] != hash_value):
                    raise ProviderFailure("IDEMPOTENCY_CONFLICT")
                if old:
                    completed = old["result"]
                else:
                    query = (
                        re.sub(
                            r"(帮我|请|搜索|找一下|推荐|播放|的歌曲|的音乐|歌单|歌曲)", "", latest
                        ).strip()[:300]
                        or latest[:300]
                    )
                    catalog = await self.core.call(
                        "tools",
                        "music:read",
                        "POST",
                        "/internal/music/catalog",
                        {"query": query},
                        owner=body.owner_id,
                    )
                    text = (
                        "找到了以下曲目，可在官方平台打开。站内文件库支持播放你拥有使用权的音频。"
                        if catalog["items"]
                        else "暂未检索到匹配曲目，请尝试更具体的歌手或歌名。"
                    )
                    completed = {
                        "type": "completed",
                        "content": text,
                        "cards": [
                            {
                                "schema_version": 1,
                                "type": "music_playlist",
                                "data": catalog,
                                "actions": ["open_provider"],
                            }
                        ],
                    }
                    await self.core.query(
                        "INSERT INTO interactive_tool_results(invocation_key,owner_id,request_hash,result) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (body.invocation_key, body.owner_id, hash_value, Jsonb(completed)),
                    )
                    completed = (
                        await self.core.query(
                            "SELECT result FROM interactive_tool_results WHERE invocation_key=%s",
                            (body.invocation_key,),
                            one=True,
                        )
                    )["result"]
                yield json.dumps(completed, ensure_ascii=False) + "\n"
                return
            kind = background_kind(latest)
            if kind:
                yield (
                    json.dumps(
                        {"type": "task.requested", "kind": kind, "instruction": latest}, ensure_ascii=False
                    )
                    + "\n"
                )
                return
            selected_runtime = copy.copy(self.runtime)
            if body.model:
                selected_runtime.provider_mode = "qwen" if body.model == "qwen3.8-max" else "minimax"
                selected_runtime.provider = provider(selected_runtime.provider_mode)
            context = await selected_runtime.working(body.context)
            searching = body.web_search or search_intent(latest)
            yield (
                json.dumps(
                    {"type": "progress", "text": "正在搜索最新资料" if searching else "正在理解你的问题"},
                    ensure_ascii=False,
                )
                + "\n"
            )
            messages = await selected_runtime.interactive_messages(
                body.invocation_key, body.owner_id, context, search=searching
            )
            yield (
                json.dumps(
                    {"type": "progress", "text": "正在整理资料与回答" if searching else "正在思考回答"},
                    ensure_ascii=False,
                )
                + "\n"
            )
            card_row = await self.core.query(
                "SELECT cards FROM interactive_plans WHERE invocation_key=%s",
                (body.invocation_key,),
                one=True,
            )
            async for event in selected_runtime.invoke(body.invocation_key, body.owner_id, messages):
                if event["type"] == "completed":
                    event = {**event, "cards": card_row["cards"]}
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except ProviderFailure as e:
            yield json.dumps({"type": "error", "code": e.code}) + "\n"
        except Exception:
            yield json.dumps({"type": "error", "code": "AGENT_UNAVAILABLE"}) + "\n"
