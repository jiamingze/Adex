import sys
import pytest
from adex_agent.codex.provider import CodexProvider
from adex_agent.models.provider import ProviderFailure


class Upstream:
    name = "qwen"
    model = "fixture-model"
    base = "https://example.invalid/v1"
    key = "fixture-key"


class Peer:
    status = "completed"
    seen = []

    def __init__(self, command, cwd, env):
        self.seen.append((command, cwd, env))
        self.events = iter(
            [
                {
                    "method": "item/agentMessage/delta",
                    "params": {"threadId": "t", "turnId": "r", "delta": "OK"},
                },
                {
                    "method": "turn/completed",
                    "params": {"threadId": "t", "turn": {"id": "r", "status": self.status}},
                },
            ]
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def request(self, method, params, **kw):
        if method == "thread/start":
            return {"thread": {"id": "t"}}
        if method == "turn/start":
            return {"turn": {"id": "r"}}
        return {}

    async def send(self, message):
        pass

    async def next_event(self):
        return next(self.events)


async def test_stream_and_isolation(monkeypatch):
    monkeypatch.setattr("adex_agent.codex.provider.CodexTransport", Peer)
    monkeypatch.setenv("ADEX_CODEX_BINARY", sys.executable)
    p = CodexProvider(Upstream())
    events = [e async for e in p.stream([{"role": "user", "content": "hello"}])]
    assert events[-1]["content"] == "OK" and events[-1]["type"] == "completed"
    command, cwd, env = Peer.seen[-1]
    assert env["HOME"] == cwd and env["CODEX_HOME"] == cwd
    assert "ADEX_APP_KEY" not in env
    assert "features.shell_tool=false" in command


@pytest.mark.parametrize("status", ["failed", "interrupted"])
async def test_noncompleted_turn_never_commits(monkeypatch, status):
    monkeypatch.setattr("adex_agent.codex.provider.CodexTransport", Peer)
    monkeypatch.setattr(Peer, "status", status)
    monkeypatch.setenv("ADEX_CODEX_BINARY", sys.executable)
    with pytest.raises(ProviderFailure):
        _ = [e async for e in CodexProvider(Upstream()).stream([{"role": "user", "content": "hello"}])]


def test_unverified_provider_refused():
    class Other(Upstream):
        name = "minimax"

    with pytest.raises(RuntimeError):
        CodexProvider(Other())


def test_factory_never_silently_falls_back(monkeypatch):
    from adex_agent.models.provider import provider

    monkeypatch.setenv("ADEX_EXECUTION_ENGINE", "codex")
    with pytest.raises(RuntimeError, match="only verified for Qwen"):
        provider("minimax")
    with pytest.raises(RuntimeError, match="only verified for Qwen"):
        provider("mock")


async def test_unexpected_server_tool_request_is_refused(monkeypatch):
    class ApprovalPeer(Peer):
        async def next_event(self):
            return {"id": "approval", "method": "requestApproval", "params": {}}

    monkeypatch.setattr("adex_agent.codex.provider.CodexTransport", ApprovalPeer)
    monkeypatch.setenv("ADEX_CODEX_BINARY", sys.executable)
    with pytest.raises(ProviderFailure, match="CODEX_UNEXPECTED_TOOL_REQUEST"):
        _ = [e async for e in CodexProvider(Upstream()).stream([{"role": "user", "content": "hello"}])]


async def test_usage_is_mapped_to_existing_ledger_fields(monkeypatch):
    class UsagePeer(Peer):
        def __init__(self, *args):
            super().__init__(*args)
            self.events = iter(
                [
                    {
                        "method": "thread/tokenUsage/updated",
                        "params": {
                            "threadId": "t",
                            "tokenUsage": {
                                "total": {"inputTokens": 12, "outputTokens": 3, "totalTokens": 15}
                            },
                        },
                    },
                    *self.events,
                ]
            )

    monkeypatch.setattr("adex_agent.codex.provider.CodexTransport", UsagePeer)
    monkeypatch.setenv("ADEX_CODEX_BINARY", sys.executable)
    events = [e async for e in CodexProvider(Upstream()).stream([{"role": "user", "content": "hello"}])]
    assert events[-1]["usage"] == {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15}
