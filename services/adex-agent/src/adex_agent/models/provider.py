import asyncio
import json
import os
from typing import Protocol, AsyncIterator, Any
import httpx


class ProviderFailure(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ModelProvider(Protocol):
    """Streaming model port. Providers report completion/usage; execution owns durable state."""

    model: str

    def stream(self, messages: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]: ...


class ThinkFilter:
    """Suppress reasoning tags, including tags split across streaming frames."""

    def __init__(self):
        self.buffer = ""
        self.thinking = False

    def feed(self, value: str, final=False) -> str:
        self.buffer += value
        output = ""
        while self.buffer:
            tag = "</think>" if self.thinking else "<think>"
            idx = self.buffer.find(tag)
            if idx >= 0:
                if not self.thinking:
                    output += self.buffer[:idx]
                self.buffer = self.buffer[idx + len(tag) :]
                self.thinking = not self.thinking
                continue
            keep = 0
            if not final:
                for n in range(1, min(len(tag), len(self.buffer) + 1)):
                    if self.buffer.endswith(tag[:n]):
                        keep = n
            ready = self.buffer[:-keep] if keep else self.buffer
            if not self.thinking:
                output += ready
            self.buffer = self.buffer[-keep:] if keep else ""
            break
        return output


class ToolProtocolFilter:
    """Reject pseudo tool protocols before their first marker reaches the UI."""

    markers = (
        "<minimax:tool_call",
        "[minimax:tool_call]",
        "<invoke",
        "</minimax:tool_call",
        "[tool_call]",
        "[/tool_call]",
        "<tool_call",
        "{tool =>",
    )

    def __init__(self):
        self.buffer = ""

    def feed(self, value, final=False):
        self.buffer += value
        lower = self.buffer.lower()
        if any(marker in lower for marker in self.markers):
            raise ProviderFailure("UNSUPPORTED_TOOL_CALL")
        keep = 0
        if not final:
            for marker in self.markers:
                for n in range(1, min(len(marker), len(lower) + 1)):
                    if lower.endswith(marker[:n]):
                        keep = max(keep, n)
        result = self.buffer[:-keep] if keep else self.buffer
        self.buffer = self.buffer[-keep:] if keep else ""
        return result


class MiniMaxProvider:
    name = "minimax"

    def __init__(self):
        self.key = os.environ["MINIMAX_API_KEY"]
        self.base = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1").rstrip("/")
        if not self.base.startswith("https://"):
            raise RuntimeError("MiniMax endpoint requires HTTPS")
        self.model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.5")

    async def stream(self, messages):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": int(os.getenv("ADEX_MAX_OUTPUT_TOKENS", "4096")),
            "stream_options": {"include_usage": True},
            **({"enable_thinking": False} if self.name == "qwen" else {"reasoning_split": True}),
        }
        content = ""
        usage = {}
        finished = False
        filter_ = ThinkFilter()
        protocol = ToolProtocolFilter()
        # No blind HTTP retry: a lost response may already have incurred provider cost.
        try:
            async with asyncio.timeout(150):
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(120, connect=10), trust_env=False
                ) as client:
                    async with client.stream(
                        "POST",
                        self.base + "/chat/completions",
                        json=payload,
                        headers={"Authorization": "Bearer " + self.key},
                    ) as response:
                        if response.status_code >= 400:
                            code = (
                                "PROVIDER_AUTH_FAILED"
                                if response.status_code in (401, 403)
                                else "PROVIDER_RATE_LIMIT"
                                if response.status_code == 429
                                else "PROVIDER_REJECTED"
                            )
                            raise ProviderFailure(code)
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                finished = True
                                break
                            event = json.loads(data)
                            if event.get("base_resp", {}).get("status_code", 0) != 0 or event.get("error"):
                                raise ProviderFailure("PROVIDER_REJECTED")
                            if event.get("usage"):
                                usage = event["usage"]
                            for choice in event.get("choices", []):
                                text = protocol.feed(
                                    filter_.feed(choice.get("delta", {}).get("content") or "")
                                )
                                if text:
                                    content += text
                                    if len(content) > 64000:
                                        raise ProviderFailure("OUTPUT_LIMIT")
                                    yield {"type": "delta", "text": text}
                                reason = choice.get("finish_reason")
                                if reason:
                                    finished = reason in ("stop", "length")
                                    if reason not in ("stop", "length"):
                                        raise ProviderFailure("PROVIDER_CONTENT_BLOCKED")
            tail = protocol.feed(filter_.feed("", final=True), final=True)
            if tail:
                content += tail
                yield {"type": "delta", "text": tail}
            if not finished or not content.strip():
                raise ProviderFailure("PROVIDER_UNKNOWN")
            yield {"type": "completed", "content": content, "usage": usage, "provider": self.name}
        except ProviderFailure:
            raise
        except (httpx.HTTPError, TimeoutError, ValueError):
            raise ProviderFailure("PROVIDER_UNKNOWN") from None


class QwenProvider(MiniMaxProvider):
    name = "qwen"

    def __init__(self):
        self.key = os.environ["DASHSCOPE_API_KEY"]
        self.base = os.getenv(
            "DASHSCOPE_CHAT_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ).rstrip("/")
        if not self.base.startswith("https://"):
            raise RuntimeError("Qwen endpoint requires HTTPS")
        self.model = os.getenv("DASHSCOPE_CHAT_MODEL", "qwen3.8-max")


class MockProvider:
    model = "deterministic-fixture-v1"

    async def stream(self, messages):
        latest = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if any(
            m.get("role") == "system" and m.get("content", "").startswith("SEMANTIC_MEMORY_V1")
            for m in messages
        ):
            from adex_agent.memory.fixture import proposal

            planned = proposal(json.loads(latest))
            text = planned if isinstance(planned, str) else json.dumps(planned, ensure_ascii=False)
            yield {"type": "completed", "content": text, "usage": {}, "provider": "mock"}
            return
        if any(
            m.get("role") == "system" and m.get("content", "").startswith("BROWSER_ROUTE_V1")
            for m in messages
        ):
            # Deterministic fixture only, never evidence of real semantic/external execution.
            value = json.loads(latest)
            query = value["recent"][-1]["content"]
            mode = "none"
            if any(w in query for w in ("价格", "多少钱", "库存")) or (
                any(w in query for w in ("淘宝", "京东", "商品")) and "搜" in query
            ):
                mode = "lookup"
            elif any(w in query for w in ("发表", "发布", "发出去", "下单", "购买")) and not any(
                w in query for w in ("怎么", "如何", "先讨论", "不要", "能不能")
            ):
                mode = "operate"
            yield {
                "type": "completed",
                "content": json.dumps({"mode": mode}),
                "usage": {},
                "provider": "mock",
            }
            return
        if latest in ("fixture:slow-stream", "TEST_FIXTURE 偏好清淡但后续回复阻塞"):
            await asyncio.sleep(30)
        text = "【测试模型，非真实 AI】已收到：" + latest[:200]
        if any(
            m.get("role") == "system" and m.get("content", "").startswith("NOTE_COMPOSE_V1") for m in messages
        ):
            text = json.dumps(
                {"title": "TEST_FIXTURE 整理笔记", "content": "【测试模型，非真实 AI】\n\n" + latest},
                ensure_ascii=False,
            )
        if (
            any(
                m.get("role") == "system" and m.get("content", "").startswith("NOTE_COMPOSE_V1")
                for m in messages
            )
            and latest == "fixture:note-invalid"
        ):
            text = "invalid-note-json"
        if any(
            m.get("role") == "system" and m.get("content", "").startswith("BROWSER_OPERATOR_V1")
            for m in messages
        ):
            value = json.loads(latest)
            nodes = value["observation"].get("nodes", [])
            step = {"action": "navigate", "url": "https://example.com/fixture"}
            if value["observation"].get("url") != "about:blank":
                step = {"action": "done", "reason": "TEST_FIXTURE only"}
                for name, content in (
                    ("标题", "TEST_FIXTURE 标题"),
                    (
                        "正文",
                        "TEST_FIXTURE_UNKNOWN"
                        if "fixture:browser-unknown" in value["goal"]
                        else "TEST_FIXTURE 正文，不是真实发布",
                    ),
                ):
                    node = next((n for n in nodes if n.get("name") == name and n.get("id")), None)
                    if node and not node.get("value"):
                        step = {"action": "type", "element_id": node["id"], "text": content}
                        break
                else:
                    if not value["observation"].get("business_receipts"):
                        node = next(
                            (n for n in nodes if n.get("name") == "发布" and n.get("role") == "button"), None
                        )
                        if node:
                            step = {"action": "click", "element_id": node["id"]}
            if value["observation"].get("url") != "about:blank" and any(
                "本次为商品查价/网页查询" in m.get("content", "")
                for m in messages
                if m.get("role") == "system"
            ):
                step = {"action": "done", "text": "TEST_FIXTURE：当前演练页面没有商品报价，无法核实价格。"}
            text = json.dumps(step, ensure_ascii=False)
        for index in range(0, len(text), 8):
            await asyncio.sleep(0.02)
            yield {"type": "delta", "text": text[index : index + 8]}
        yield {"type": "completed", "content": text, "usage": {}, "provider": "mock"}


def provider(mode=None) -> ModelProvider:
    mode = mode or os.getenv("ADEX_MODEL_PROVIDER", "minimax")
    if mode == "mock":
        return MockProvider()
    if mode == "qwen":
        return QwenProvider()
    if mode != "minimax":
        raise RuntimeError("Unsupported model provider")
    return MiniMaxProvider()
