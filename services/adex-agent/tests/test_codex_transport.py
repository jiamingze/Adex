import asyncio
import sys

import pytest

from adex_agent.codex.transport import CodexTransport, ProtocolFailure


@pytest.fixture
def peer(tmp_path):
    path = tmp_path / "peer.py"
    path.write_text("""import json,sys
for line in sys.stdin:
 r=json.loads(line)
 if r.get('method')=='eof': break
 if r.get('method')=='bad':
  print('not-json',flush=True);continue
 if r.get('method')=='hang': continue
 if r.get('method')=='event':
  print(json.dumps({'method':'item/delta','params':{'text':'hello'}}),flush=True)
 if r.get('method')=='approval':
  print(json.dumps({'id':'server-1','method':'requestApproval','params':{}}),flush=True)
 if 'id' in r:print(json.dumps({'id':r['id'],'result':{'method':r['method']}}),flush=True)
""")
    return [sys.executable, str(path)]


async def test_correlates_parallel_calls_and_keeps_events(peer, tmp_path):
    async with CodexTransport(peer, tmp_path, {}) as rpc:
        a, b = await asyncio.gather(rpc.request("event", {}), rpc.request("second", {}))
        assert a["method"] == "event" and b["method"] == "second"
        assert (await rpc.next_event())["params"]["text"] == "hello"
        process = rpc.process
    assert process.returncode is not None


@pytest.mark.parametrize("method", ["eof", "bad"])
async def test_broken_stream_fails_pending_calls(peer, tmp_path, method):
    async with CodexTransport(peer, tmp_path, {}) as rpc:
        with pytest.raises(ProtocolFailure):
            await rpc.request(method, {})
        with pytest.raises(ProtocolFailure):
            await rpc.request("another", {})


async def test_timeout_is_not_retried(peer, tmp_path):
    async with CodexTransport(peer, tmp_path, {}) as rpc:
        with pytest.raises(ProtocolFailure, match="UNKNOWN"):
            await rpc.request("hang", {}, timeout=0.02)
        assert not rpc.pending


async def test_server_request_is_not_automatically_approved(peer, tmp_path):
    async with CodexTransport(peer, tmp_path, {}) as rpc:
        await rpc.request("approval", {})
        event = await rpc.next_event()
        assert event["id"] == "server-1"
        assert event["method"] == "requestApproval"


async def test_cancel_reaps_child(peer, tmp_path):
    async def run():
        async with CodexTransport(peer, tmp_path, {}) as rpc:
            ready.set_result(rpc.process)
            await rpc.request("hang", {})

    ready = asyncio.get_running_loop().create_future()
    task = asyncio.create_task(run())
    process = await ready
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert process.returncode is not None
