"""Typed, bounded repair of planning output; never retries an unknown tool effect."""

import json
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from adex_kernel.text import strip_json_fence
from adex_agent.models.provider import ProviderFailure


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["press", "set_value", "observe", "search", "navigate", "done", "blocked"]
    element_id: str = Field(default="", max_length=100)
    text: str = Field(default="", max_length=4000)
    reason: str = Field(default="", max_length=500)


async def plan_operation(runtime, owner, key, messages, observation):
    messages = [dict(m) for m in messages]
    messages[0]["content"] += "\n严格JSON契约：" + json.dumps(Plan.model_json_schema(), ensure_ascii=False)
    for attempt in range(2):
        output = ""
        async for event in runtime.invoke(key + ":" + str(attempt), owner, messages):
            if event["type"] == "completed":
                output = event["content"]
        try:
            result = Plan.model_validate_json(strip_json_fence(output))
            if observation.get("status") == "not_observed" and result.action not in {
                "observe",
                "search",
                "navigate",
                "blocked",
            }:
                raise ValueError(
                    "First action must observe, search or navigate; no execution evidence exists"
                )
            if result.action == "search" and (not result.text.strip() or len(result.text.strip()) > 500):
                raise ValueError("Search text must contain 1..500 characters")
            if result.action == "navigate":
                from urllib.parse import urlsplit

                address = urlsplit(result.text)
                if result.text == observation.get("navigation_url"):
                    raise ValueError(
                        "This URL was already opened. Use observe while loading or done with an observed link; do not navigate again"
                    )
                if address.scheme != "https" or not address.hostname or address.username or address.password:
                    raise ValueError("Navigate text must be a public HTTPS URL without credentials")
            if result.action == "done" and observation.get("status") == "loading":
                raise ValueError("Page is still loading; observe again, no successful result exists yet")
            if result.action in {"done", "blocked"} and not result.text.strip():
                if result.reason.strip():
                    result.text = result.reason
                else:
                    raise ValueError("Done/blocked must explain the observed result or obstacle in text")
            if result.action == "done" and observation.get("nodes"):
                observed_urls = {node.get("url") for node in observation["nodes"] if node.get("url")}
                reported = re.findall(r"https?://[^\s)\]<>]+", result.text)
                if any(url.rstrip("。，；") not in observed_urls for url in reported):
                    raise ValueError(
                        "Done URLs must copy exact URLs from current observation; never invent links"
                    )
            return result
        except ValueError as error:
            if attempt:
                break
            detail = (
                [
                    {"loc": list(e["loc"]), "type": e["type"]}
                    for e in error.errors(include_input=False, include_url=False)
                ][:10]
                if isinstance(error, ValidationError)
                else [{"type": "invalid_step", "reason": str(error)}]
            )
            messages += [
                {"role": "assistant", "content": output[:20000]},
                {
                    "role": "user",
                    "content": "规划格式校验失败："
                    + json.dumps(detail, ensure_ascii=False)
                    + "。只输出契约中的完整JSON，搜索词放text；初始无观察时用search或observe，不可编造执行结果。",
                },
            ]
    raise ProviderFailure("INVALID_COMPUTER_PLAN")
