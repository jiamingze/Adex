"""Schedules HTTP adapter; scopes are checked before invoking capabilities."""

from fastapi import APIRouter, Request, HTTPException
from adex_kernel.core import owner_match
import json
from adex_agent.models.provider import ProviderFailure
from adex_agent.dependencies import core, runtime
from adex_agent.api.schemas import DraftRequest

router = APIRouter()


@router.post("/internal/agent/schedule-draft")
async def schedule_draft(request: Request, body: DraftRequest):
    claims = core.require(request, "app", "schedule:draft", body.conversation_id)
    owner_match(claims, body.owner_id)
    messages = [
        {
            "role": "system",
            "content": '将用户的日程请求转换为 JSON 草稿。不要执行任务。仅输出 JSON 对象，字段为 title, instruction（实际执行内容）, kind（ONCE/DAILY/INTERVAL）, timezone（IANA）, first_fire_at（含 UTC 偏移的 ISO8601 未来时间）, local_time（DAILY 时 HH:mm）, interval_seconds（INTERVAL 时至少 60）。存在歧义时仅输出 {"clarification":"问题"}。没有明确时区则使用 '
            + body.timezone
            + "。当前 UTC 时间为 "
            + body.current_time
            + "。",
        },
        {"role": "user", "content": body.instruction},
    ]
    try:
        result = None
        async for event in runtime.invoke(
            "draft:" + str(body.owner_id) + ":" + str(body.request_id), body.owner_id, messages
        ):
            if event["type"] == "completed":
                result = event["content"]
        if not result:
            raise HTTPException(502, detail="DRAFT_PARSE_FAILED")
        from adex_kernel.text import strip_json_fence

        result = strip_json_fence(result)
        parsed = json.loads(result)
        if "clarification" in parsed:
            return {"clarification": str(parsed["clarification"])[:500]}
        from adex_agent.routing.schedule import ScheduleDraft

        from adex_agent.routing.notification import notification_plan

        preferences = await notification_plan(runtime, body.owner_id, body.request_id, body.instruction)
        if preferences.get("clarification"):
            return preferences
        parsed.update(preferences)
        return ScheduleDraft.model_validate(parsed).model_dump(exclude_none=True)
    except ProviderFailure as exc:
        raise HTTPException(502, detail=exc.code) from None
    except (ValueError, TypeError):
        raise HTTPException(502, detail="DRAFT_PARSE_FAILED") from None
