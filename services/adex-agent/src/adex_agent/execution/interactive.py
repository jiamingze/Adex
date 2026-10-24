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
            from adex_agent.routing.intent import (
                original_music_intent,
                schedule_intent,
                background_kind,
                video_intent,
                catalog_music_intent,
            )

            latest = next(
                (m["content"] for m in reversed(body.context["messages"]) if m["role"] == "user"), ""
            )
            import re

            selected_runtime = copy.copy(self.runtime)
            if body.model:
                selected_runtime.provider_mode = (
                    "qwen" if body.model in {"qwen3.8-flash", "qwen3.8-max"} else "minimax"
                )
                selected_runtime.provider = provider(selected_runtime.provider_mode)
            from adex_agent.skills.trading import native_mt5_request

            if native_mt5_request(latest) and not schedule_intent(latest):
                # Domain ownership precedes generic "下单"/computer classifiers.
                # This enters read/preparation only; it creates no order or approval.
                async for chunk in self.reply(selected_runtime, body, latest, native_mt5=True):
                    yield chunk
                return
            from adex_agent.actions.planner import task_action

            action = await task_action(selected_runtime, self.core, body)
            if action["tool"] == "clarify":
                yield (
                    json.dumps({"type": "completed", "content": action["message"]}, ensure_ascii=False) + "\n"
                )
                return
            if action["tool"] != "none":
                yield (
                    json.dumps({"type": "task.action.requested", "action": action}, ensure_ascii=False) + "\n"
                )
                return
            from adex_agent.routing.productivity import todo_draft

            todo = await todo_draft(selected_runtime, body.owner_id, body.invocation_key, latest)
            if todo:
                yield json.dumps({"type": "todo.requested", "draft": todo}, ensure_ascii=False) + "\n"
                return
            if schedule_intent(latest):
                from adex_agent.routing.schedule import (
                    daily_chat_draft,
                    relative_chat_draft,
                    interval_chat_draft,
                    semantic_chat_draft,
                )

                draft = interval_chat_draft(latest) or relative_chat_draft(latest) or daily_chat_draft(latest)
                if not draft:
                    draft = await semantic_chat_draft(
                        selected_runtime, body.owner_id, body.invocation_key, latest
                    )
                if draft:
                    from adex_agent.routing.notification import notification_plan

                    preferences = await notification_plan(
                        selected_runtime, body.owner_id, body.invocation_key, latest
                    )
                    if preferences.get("clarification"):
                        yield (
                            json.dumps(
                                {"type": "completed", "content": preferences["clarification"]},
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                        return
                    draft.update(preferences)
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
            from adex_agent.routing.browser import route_request, task_instruction

            from adex_agent.routing.location import relevant as location_relevant

            # Ordinary local information queries retain their consented turn context;
            # do not turn a nearby recommendation into an unrelated background browser task.
            browser_mode = (
                "none"
                if location_relevant(latest) and not re.search(r"网站|官网|网页|浏览器|https?://", latest)
                else await route_request(
                    selected_runtime, body.owner_id, body.invocation_key, body.context["messages"]
                )
            )
            if browser_mode != "none":
                yield (
                    json.dumps(
                        {
                            "type": "task.requested",
                            "kind": "BROWSER",
                            "instruction": task_instruction(body.context["messages"], latest),
                            "request": {"params": {"browser_mode": browser_mode}},
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
            if video_intent(latest):
                duration_match = re.search(r"(?<!\d)(\d{1,8})\s{0,16}秒", latest)
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
                match = re.search(r"(?<![\d.])(\d{1,8}(?:\.\d{1,6})?)\s{0,16}(分钟|秒)", latest)
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
            if catalog_music_intent(latest):
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
            async for chunk in self.reply(selected_runtime, body, latest):
                yield chunk
        except ProviderFailure as e:
            yield json.dumps({"type": "error", "code": e.code}) + "\n"
        except Exception:
            yield json.dumps({"type": "error", "code": "AGENT_UNAVAILABLE"}) + "\n"

    async def reply(self, selected_runtime, body, latest, native_mt5=False):
        """Shared streamed reply path; native terminal selection grants no mutations."""
        import re

        context = await selected_runtime.working(body.context)
        from adex_agent.skills.registry import REGISTRY

        skill_plan = REGISTRY.resolve_context(context.get("messages", []))
        from adex_agent.routing.intent import search_intent

        terminal = native_mt5 or (skill_plan and skill_plan.skill.id == "trading.mt5-research")
        searching = False if terminal else body.web_search or search_intent(latest)
        if (
            skill_plan
            and skill_plan.search_queries
            and not re.search(r"(不要|不用|无需|别).{0,6}(联网|搜索|搜)", latest)
        ):
            searching = True
        yield (
            json.dumps(
                {
                    "type": "progress",
                    "text": "正在读取本机 MT5 行情与挂单"
                    if terminal
                    else "正在检索景点、预约要求与交通"
                    if searching and skill_plan
                    else "正在打开网页并读取内容"
                    if searching and re.search(r"https?://|官网|网站|网页|浏览", latest, re.I)
                    else "正在搜索最新资料"
                    if searching
                    else "正在理解你的问题",
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        messages = await selected_runtime.interactive_messages(
            body.invocation_key, body.owner_id, context, search=searching
        )
        yield (
            json.dumps(
                {
                    "type": "progress",
                    "text": "正在核对 MT5 数据与订单执行边界"
                    if terminal
                    else "正在编排逐日路线与检查行程约束"
                    if skill_plan
                    else "正在整理资料与回答"
                    if searching
                    else "正在思考回答",
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        card_row = await self.core.query(
            "SELECT cards FROM interactive_plans WHERE invocation_key=%s",
            (body.invocation_key,),
            one=True,
        )
        from adex_agent.skills.trading_advice import automatic_advice, wants_advice

        if terminal and wants_advice(context.get("messages", [])):
            yield (
                json.dumps(
                    {"type": "progress", "text": "正在自动分析多周期行情并校验交易草案"}, ensure_ascii=False
                )
                + "\n"
            )
            content = await automatic_advice(
                selected_runtime, body.owner_id, body.invocation_key, messages, latest
            )
            yield (
                json.dumps(
                    {"type": "completed", "content": content, "cards": card_row["cards"]}, ensure_ascii=False
                )
                + "\n"
            )
            return
        async for event in selected_runtime.invoke(body.invocation_key, body.owner_id, messages):
            if event["type"] == "completed":
                event = {**event, "cards": card_row["cards"]}
            yield json.dumps(event, ensure_ascii=False) + "\n"
