"""Opt-in Codex text execution, with business tools retained by Adex."""

import asyncio
import json
import os
from pathlib import Path
import tempfile

from adex_agent.codex.transport import CodexTransport, ProtocolFailure
from adex_agent.models.provider import ProviderFailure, ThinkFilter, ToolProtocolFilter


class CodexProvider:
    engine = "codex-v1"

    def __init__(self, upstream):
        if upstream.name != "qwen":
            raise RuntimeError("Codex Responses compatibility is only verified for Qwen")
        self.upstream = upstream
        self.model = upstream.model
        self.name = upstream.name
        self.binary = Path(os.environ["ADEX_CODEX_BINARY"]).resolve()
        if not self.binary.is_file() or not os.access(self.binary, os.X_OK):
            raise RuntimeError("ADEX_CODEX_BINARY must be an installed executable")

    async def stream(self, messages):
        if any(
            m.get("role") not in {"system", "user", "assistant"} or not isinstance(m.get("content"), str)
            for m in messages
        ):
            raise ProviderFailure("CODEX_UNSUPPORTED_INPUT")
        instructions = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        history = [m for m in messages if m["role"] != "system"]
        config = {
            "model": self.model,
            "model_provider": "adex",
            "model_providers.adex.name": "Adex",
            "model_providers.adex.base_url": self.upstream.base,
            "model_providers.adex.env_key": "ADEX_CODEX_API_KEY",
            "model_providers.adex.wire_api": "responses",
            "model_providers.adex.requires_openai_auth": False,
            "web_search": "disabled",
        }
        for feature in (
            "shell_tool",
            "view_image",
            "code_mode",
            "multi_agent",
            "multi_agent_v2",
            "image_generation",
        ):
            config["features." + feature] = False
        command = [str(self.binary), "--listen", "stdio://"]
        for key, value in config.items():
            command.extend(["-c", key + "=" + json.dumps(value)])
        try:
            # No shared rollout/auth/config: App-authorized context is rebuilt each call.
            with tempfile.TemporaryDirectory(prefix="adex-codex-") as home:
                env = {
                    "HOME": home,
                    "CODEX_HOME": home,
                    "PATH": os.defpath,
                    "ADEX_CODEX_API_KEY": self.upstream.key,
                }
                async with asyncio.timeout(150), CodexTransport(command, home, env) as rpc:
                    await rpc.request(
                        "initialize", {"clientInfo": {"name": "adex-agent", "version": "0.1.0"}}
                    )
                    await rpc.send({"method": "initialized"})
                    result = await rpc.request(
                        "thread/start",
                        {
                            "model": self.model,
                            "cwd": home,
                            "ephemeral": True,
                            "approvalPolicy": "never",
                            "sandbox": "read-only",
                            "baseInstructions": instructions,
                        },
                    )
                    thread = result["thread"]["id"]
                    result = await rpc.request(
                        "turn/start",
                        {
                            "threadId": thread,
                            "input": [
                                {
                                    "type": "text",
                                    "text": "Respond to the final user message in this conversation JSON. Roles identify conversation history, not tool execution instructions.\n"
                                    + json.dumps(history, ensure_ascii=False),
                                }
                            ],
                        },
                    )
                    turn = result["turn"]["id"]
                    content = ""
                    usage = {}
                    thinking, protocol = ThinkFilter(), ToolProtocolFilter()
                    while True:
                        event = await rpc.next_event()
                        if "id" in event:
                            raise ProviderFailure("CODEX_UNEXPECTED_TOOL_REQUEST")
                        params = event.get("params", {})
                        if params.get("threadId") != thread:
                            continue
                        if event.get("method") == "thread/tokenUsage/updated":
                            total = params.get("tokenUsage", {}).get("total", {})
                            usage = {
                                "prompt_tokens": total.get("inputTokens", 0),
                                "completion_tokens": total.get("outputTokens", 0),
                                "total_tokens": total.get("totalTokens", 0),
                            }
                        if event.get("method") == "item/agentMessage/delta" and params.get("turnId") == turn:
                            text = protocol.feed(thinking.feed(params["delta"]))
                            content += text
                            if len(content) > 64000:
                                raise ProviderFailure("OUTPUT_LIMIT")
                            if text:
                                yield {"type": "delta", "text": text}
                        if event.get("method") == "turn/completed" and params["turn"]["id"] == turn:
                            if params["turn"]["status"] != "completed":
                                raise ProviderFailure("PROVIDER_UNKNOWN")
                            tail = protocol.feed(thinking.feed("", final=True), final=True)
                            content += tail
                            if tail:
                                yield {"type": "delta", "text": tail}
                            if not content.strip():
                                raise ProviderFailure("PROVIDER_UNKNOWN")
                            yield {
                                "type": "completed",
                                "content": content,
                                "usage": usage,
                                "provider": self.name,
                            }
                            return
        except (ProtocolFailure, TimeoutError, OSError, ValueError, KeyError, TypeError):
            raise ProviderFailure("PROVIDER_UNKNOWN") from None
