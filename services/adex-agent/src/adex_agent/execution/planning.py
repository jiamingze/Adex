"""Bounded repair of completed model proposals. Never retries a dispatched tool."""

import json
from pydantic import ValidationError
from adex_kernel.text import strip_json_fence


async def validated_plan(runtime, owner, key, messages, schema, validate):
    messages = [dict(message) for message in messages]
    messages[0]["content"] += "\nJSON schema: " + json.dumps(schema.model_json_schema(), ensure_ascii=False)
    for attempt in range(2):
        output = ""
        async for event in runtime.invoke(key + ":schema:" + str(attempt), owner, messages):
            if event["type"] == "completed":
                output = event["content"]
        try:
            proposal = schema.model_validate_json(strip_json_fence(output))
            validate(proposal)
            return proposal
        except ValueError as error:
            if attempt:
                raise ValueError("INVALID_TOOL_CALL") from None
            detail = (
                [
                    {"loc": list(item["loc"]), "type": item["type"]}
                    for item in error.errors(include_input=False, include_url=False)
                ][:8]
                if isinstance(error, ValidationError)
                else [{"type": str(error)[:200]}]
            )
            messages += [
                {"role": "assistant", "content": output[:16000]},
                {
                    "role": "user",
                    "content": "规划未通过校验，尚未执行任何工具。只根据原目标及实际观察修正JSON，不增加权限或编造来源。错误："
                    + json.dumps(detail, ensure_ascii=False),
                },
            ]
