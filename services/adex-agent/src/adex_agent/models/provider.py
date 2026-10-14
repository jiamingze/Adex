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
        if latest == "fixture:slow-stream":
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
