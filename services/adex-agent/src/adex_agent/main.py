import copy
from typing import Literal
import asyncio
import json
import os
from contextlib import asynccontextmanager
from uuid import UUID
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from adex_kernel.core import Core, digest, owner_match
from .runtime import Runtime
from .provider import ProviderFailure, provider

core = Core("agent")
runtime = Runtime(core)


@asynccontextmanager
async def lifespan(app):
    await core.start()
    task = (
        asyncio.create_task(runtime.worker())
        if os.getenv("ADEX_BACKGROUND_WORKER", "true") == "true"
        else None
    )
    audit = asyncio.create_task(runtime.audit_checkpoints())
    yield
    audit.cancel()
    await asyncio.gather(audit, return_exceptions=True)
    if task:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    await runtime.redis.aclose()
    await core.pool.close()


app = FastAPI(title="Adex Agent", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.exception_handler(HTTPException)
async def error(request, exc):
    return JSONResponse({"code": exc.detail}, status_code=exc.status_code)


@app.get("/health/live")
async def live():
    return {"status": "UP", "service": "agent"}


@app.get("/health/ready")
async def ready():
    try:
        await core.query("SELECT 1")
        redis_state = "UP"
        try:
            await runtime.redis.ping()
        except Exception:
            redis_state = "DEGRADED"
        return {"status": "UP", "redis": redis_state, "provider": os.getenv("ADEX_MODEL_PROVIDER", "minimax")}
    except Exception:
        return JSONResponse({"status": "DOWN"}, status_code=503)


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invocation_key: str = Field(max_length=180)
    owner_id: UUID
    conversation_id: UUID
    turn_id: UUID
    context: dict
    web_search: bool = False
    model: Literal["", "qwen3.8-max", "minimax"] = ""


@app.post("/internal/agent/turns")
async def turn(request: Request, body: Turn):
    claims = core.require(request, "app", "turn:execute", body.turn_id)
    owner_match(claims, body.owner_id)
    if str(body.context.get("owner_id")) != str(body.owner_id) or str(
        body.context.get("conversation_id")
    ) != str(body.conversation_id):
        raise HTTPException(403, detail="SCOPE_DENIED")

    async def stream():
        try:
            from .router import original_music_intent, search_intent, background_kind

            latest = next(
                (m["content"] for m in reversed(body.context["messages"]) if m["role"] == "user"), ""
            )
            import re

            from .router import schedule_intent
            if schedule_intent(latest):
                from .schedule import daily_chat_draft
                draft = daily_chat_draft(latest)
                if draft:
                    yield json.dumps({"type":"schedule.requested", "draft":draft},ensure_ascii=False)+"\n"
                else:
                    yield json.dumps({"type":"completed", "content":"可以为你设置定时任务。请补充明确的执行时间，例如：每天上午8点汇总 SpaceX 最新消息。"},ensure_ascii=False)+"\n"
                return
            if re.search(r"(生成|制作|创作|做).*(视频|短片)", latest):
                duration_match = re.search(r"(\d+)\s*秒", latest)
                duration = int(duration_match[1]) if duration_match else 5
                if not 2 <= duration <= 30:
                    raise ProviderFailure("INVALID_MEDIA_DURATION")
                yield json.dumps({"type": "task.requested", "kind": "VIDEO", "instruction": latest,
                    "request": {"provider": os.getenv("ADEX_VIDEO_PROVIDER", "mock"), "rights_confirmed": True,
                    "params": {"duration_seconds": duration}}}, ensure_ascii=False) + "\n"
                return
            if original_music_intent(latest):
                audio_limit = 600
                duration = min(180, audio_limit)
                match = re.search(r"(\d+(?:\.\d+)?)\s*(分钟|秒)",latest)
                if match:
                    duration = float(match[1]) * (60 if match[2] == "分钟" else 1)
                if not 1 <= duration <= audio_limit:
                    yield json.dumps({"type":"completed", "content":f"当前音乐模型单次支持最多{audio_limit}秒。请指定这个范围内的时长，例如：生成两分钟浪漫钢琴曲。"},ensure_ascii=False)+"\n"
                    return
                provider_name = os.getenv("ADEX_MUSIC_PROVIDER", "mock")
                yield json.dumps({"type":"task.requested", "kind":"AUDIO", "instruction":latest,
                    "request":{"provider":provider_name,"rights_confirmed":True,
                    "params":{"duration_seconds":duration,"mode":"vocals" if re.search(r"人声|歌词|演唱",latest) else "instrumental"}}},ensure_ascii=False)+"\n"
                return
            if re.search(r"(搜索|找|推荐|播放).*(歌曲|音乐|歌单)|(歌曲|音乐|歌单).*(搜索|推荐)", latest):
                from psycopg.types.json import Jsonb
                from adex_kernel.core import digest

                hash_value = digest({"context": body.context, "kind": "music"})
                old = await core.query(
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
                    catalog = await core.call(
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
                    await core.query(
                        "INSERT INTO interactive_tool_results(invocation_key,owner_id,request_hash,result) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (body.invocation_key, body.owner_id, hash_value, Jsonb(completed)),
                    )
                    completed = (
                        await core.query(
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
            selected_runtime = copy.copy(runtime)
            if body.model:
                selected_runtime.provider_mode = "qwen" if body.model == "qwen3.8-max" else "minimax"
                selected_runtime.provider = provider(selected_runtime.provider_mode)
            context = await selected_runtime.working(body.context)
            searching = body.web_search or search_intent(latest)
            yield json.dumps({"type":"progress","text":"正在搜索最新资料" if searching else "正在理解你的问题"},ensure_ascii=False)+"\n"
            messages = await selected_runtime.interactive_messages(
                body.invocation_key, body.owner_id, context, search=searching
            )
            yield json.dumps({"type":"progress","text":"正在整理资料与回答" if searching else "正在思考回答"},ensure_ascii=False)+"\n"
            card_row = await core.query(
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

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.get("/internal/checkpoints/{ref}")
async def checkpoint(request: Request, ref: UUID):
    claims = core.require(request, "automation", "checkpoint:read", ref)
    cp = await core.query(
        "SELECT * FROM checkpoints WHERE id=%s AND owner_id=%s", (ref, claims["owner"]), one=True
    )
    if not cp:
        raise HTTPException(404, detail="NOT_FOUND")
    if digest(cp["state"]) != cp["sha256"]:
        raise HTTPException(409, detail="CHECKPOINT_CORRUPTED")
    return jsonable_encoder(cp)


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    owner_id: UUID
    conversation_id: UUID
    instruction: str = Field(min_length=1, max_length=2000)
    timezone: str = Field(max_length=80)
    current_time: str


@app.post("/internal/agent/schedule-draft")
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
        import re

        result = re.sub(r"^```(?:json)?\s*|\s*```$", "", result.strip())
        parsed = json.loads(result)
        if "clarification" in parsed:
            return {"clarification": str(parsed["clarification"])[:500]}
        from .schedule import ScheduleDraft

        return ScheduleDraft.model_validate(parsed).model_dump(exclude_none=True)
    except ProviderFailure as exc:
        raise HTTPException(502, detail=exc.code) from None
    except (ValueError, TypeError):
        raise HTTPException(502, detail="DRAFT_PARSE_FAILED") from None


@app.get("/internal/usage")
async def usage(request: Request):
    claims = core.require(request, "app", "usage:read")
    owner = UUID(claims["owner"])
    counts = await core.query(
        "SELECT state,count(*) AS calls FROM invocations WHERE owner_id=%s AND created_at>=date_trunc('day',now()) GROUP BY state",
        (owner,),
    )
    tokens = await core.query(
        "SELECT COALESCE(sum(CASE WHEN result->'usage'->>'prompt_tokens' ~ '^[0-9]+$' THEN (result->'usage'->>'prompt_tokens')::bigint ELSE 0 END),0) AS input_tokens,COALESCE(sum(CASE WHEN result->'usage'->>'completion_tokens' ~ '^[0-9]+$' THEN (result->'usage'->>'completion_tokens')::bigint ELSE 0 END),0) AS output_tokens FROM invocations WHERE owner_id=%s AND created_at>=date_trunc('day',now())",
        (owner,),
        one=True,
    )
    estimated = None
    if os.getenv("ADEX_PRICE_INPUT_PER_MILLION") and os.getenv("ADEX_PRICE_OUTPUT_PER_MILLION"):
        from decimal import Decimal

        input_rate = Decimal(os.environ["ADEX_PRICE_INPUT_PER_MILLION"])
        output_rate = Decimal(os.environ["ADEX_PRICE_OUTPUT_PER_MILLION"])
        if input_rate.is_finite() and output_rate.is_finite() and input_rate >= 0 and output_rate >= 0:
            estimated = str(
                (
                    Decimal(tokens["input_tokens"]) * input_rate
                    + Decimal(tokens["output_tokens"]) * output_rate
                )
                / 1_000_000
            )
    return {
        "tokens": tokens,
        "estimated_cost": estimated,
        "currency": os.getenv("ADEX_PRICE_CURRENCY", "CNY"),
        "provider": os.getenv("ADEX_MODEL_PROVIDER", "minimax"),
        "daily_call_limit": int(os.getenv("ADEX_DAILY_MODEL_CALL_LIMIT", "50")),
        "states": counts,
        "pricing": "Provider billing is authoritative; local call counts do not imply currency cost",
    }
