from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from adex_agent.browser.search_fallback import blocked_search_fallback


@pytest.mark.parametrize("mode,host,status,action,expected", [
    ("lookup", "www.google.com", "AGENT", None, True),
    ("lookup", "shop.example.com", "AGENT", None, False),
    ("lookup", "www.google.com", "UNKNOWN", "write", False),
    ("lookup", "www.google.com", "HUMAN", None, False),
    ("operate", "www.google.com", "AGENT", None, False),
])
async def test_alternate_search_never_retries_writes_or_bypasses_login(mode, host, status, action, expected):
    core = SimpleNamespace(call=AsyncMock(return_value={
        "provider": "TEST_FIXTURE", "items": [{"url": "https://example.com/news", "title": "TEST_FIXTURE", "snippet": "synthetic result"}],
    }))
    view = {"url": f"https://{host}/search?q=Adex", "status": status, "action_id": action, "access_block": {"code": "blocked"}}
    run = {"owner_id": "owner", "request": {"params": {"browser_mode": mode}}}
    result = await blocked_search_fallback(core, run, view, "session")
    assert bool(result) is expected
    assert core.call.await_count == int(expected)
    if result:
        assert "Google 当前要求网站验证" in result['content']
        assert result['artifact']['receipts'] == []
        assert result['artifact']['search_fallback']['provider'] == 'TEST_FIXTURE'


async def test_unavailable_alternate_search_does_not_invent_results():
    core = SimpleNamespace(call=AsyncMock(side_effect=RuntimeError('unavailable')))
    result = await blocked_search_fallback(core, {'owner_id': 'owner', 'request': {'params': {'browser_mode': 'lookup'}}}, {
        'url': 'https://www.google.com/search?q=Adex', 'status': 'AGENT', 'access_block': {'code': 'blocked'},
    }, 'session')
    assert result is None
    core.call.assert_awaited_once()


async def test_blocked_google_workflow_finishes_with_alternate_sources_without_handoff():
    from adex_agent.browser.workflow import BrowserWorkflow
    calls = []
    async def call(service, scope, method, path, body, **kwargs):
        calls.append(path)
        if path.endswith('/ensure'):
            return {'id': 'session'}
        if path.endswith('/observe'):
            return {'url': 'https://www.google.com/search?q=Adex', 'status': 'AGENT',
                    'access_block': {'code': 'blocked'}, 'nodes': []}
        if path == '/internal/search':
            return {'provider': 'TEST_FIXTURE', 'items': [{'url': 'https://example.com/news', 'title': 'TEST_FIXTURE'}]}
        raise AssertionError('Unexpected write or handoff: ' + path)
    workflow = BrowserWorkflow(SimpleNamespace(core=SimpleNamespace(call=call), runtime=None))
    result = await workflow.run({'id': 'run', 'owner_id': 'owner', 'origin_conversation_id': 'conversation',
        'epoch': 1, 'attempt_id': 'attempt', 'request': {'browser_url': 'https://www.google.com/search?q=Adex',
        'params': {'browser_mode': 'lookup'}}}, {'memory_revision': 1})
    assert result['phase'] == 'result'
    assert calls.count('/internal/search') == 1
    assert result['pending_effects'] == []
