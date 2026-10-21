import pytest
from adex_agent.models.provider import ThinkFilter, MockProvider


def test_reasoning_is_never_displayed():
    f = ThinkFilter()
    output = ""
    for part in ["<thi", "nk>secret", "</th", "ink>", "Visible", "<thi", "nk>hidden</think>!"]:
        output += f.feed(part)
    output += f.feed("", final=True)
    assert output == "Visible!"


def test_incomplete_thinking_remains_hidden():
    f = ThinkFilter()
    assert f.feed("<think>secret", final=True) == ""


async def test_mock_is_labelled():
    events = [e async for e in MockProvider().stream([{"role": "user", "content": "hello"}])]
    assert events[-1]["provider"] == "mock"
    assert "测试模型" in events[-1]["content"]
    assert "".join(e["text"] for e in events if e["type"] == "delta") == events[-1]["content"]


def test_tool_protocol_split_frames_never_expose_marker():
    import pytest
    from adex_agent.models.provider import ToolProtocolFilter, ProviderFailure
    for marker in ('<minimax:tool_call>', '[minimax:tool_call]', '<invoke name="search">'):
        guard = ToolProtocolFilter()
        exposed = ''
        with pytest.raises(ProviderFailure, match='UNSUPPORTED_TOOL_CALL'):
            for char in marker:
                exposed += guard.feed(char)
        assert exposed == ''


def test_search_intent_uses_explicit_and_current_queries():
    from adex_agent.routing.intent import search_intent
    assert search_intent('帮我搜一下近期周杰伦的演唱会')
    assert search_intent('近期周杰伦有哪些演唱会')
    assert not search_intent('解释二分查找的时间复杂度')
    assert not search_intent('不要联网搜索，帮我写诗')


@pytest.mark.parametrize('model', ['qwen3.8-flash', 'qwen3.8-max'])
async def test_qwen_stream_model_and_usage(monkeypatch, model):
    import httpx,json
    from adex_agent.models.provider import QwenProvider
    monkeypatch.setenv('DASHSCOPE_API_KEY','fixture-key')
    monkeypatch.setenv('DASHSCOPE_CHAT_MODEL',model)
    def handle(request):
        payload=json.loads(request.content)
        assert payload['model']==model
        assert payload['enable_thinking'] is False and 'reasoning_split' not in payload
        return httpx.Response(200,content='data: '+json.dumps({'choices':[{'delta':{'content':'OK'},'finish_reason':'stop'}],'usage':{'total_tokens':3}})+'\n\ndata: [DONE]\n\n')
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handle)))
    events=[event async for event in QwenProvider().stream([{'role':'user','content':'hi'}])]
    assert events[-1]['provider']=='qwen' and events[-1]['content']=='OK'
    assert events[-1]['usage']['total_tokens']==3


def test_qwen_pseudo_tools_are_blocked_across_frames():
    from adex_agent.models.provider import ToolProtocolFilter,ProviderFailure
    import pytest
    for marker in ('[TOOL_CALL]', '{tool =>', '<tool_call'):
        for split in range(1,len(marker)):
            guard=ToolProtocolFilter()
            assert guard.feed(marker[:split])==''
            with pytest.raises(ProviderFailure,match='UNSUPPORTED_TOOL_CALL'):
                guard.feed(marker[split:])


def test_explicit_provider_selection_does_not_change_default(monkeypatch):
    from adex_agent.models.provider import provider, QwenProvider, MiniMaxProvider
    monkeypatch.setenv('ADEX_MODEL_PROVIDER','qwen')
    monkeypatch.setenv('MINIMAX_API_KEY','fixture-minimax')
    monkeypatch.setenv('DASHSCOPE_API_KEY','fixture-qwen')
    assert isinstance(provider('minimax'),MiniMaxProvider)
    assert isinstance(provider('qwen'),QwenProvider)
    assert isinstance(provider(),QwenProvider)


def test_automatic_search_for_fresh_information():
    from adex_agent.routing.intent import search_intent
    assert search_intent('整理最新关于 SpaceX 的信息')
    assert search_intent('今天上海天气怎么样')
    assert search_intent('latest SpaceX updates')
    assert not search_intent('不用联网搜索，解释天空为什么是蓝色')
    assert not search_intent('帮我写一首浪漫的诗')


def test_qwen_default_is_flash(monkeypatch):
    from adex_agent.models.provider import QwenProvider
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'fixture-key')
    monkeypatch.delenv('DASHSCOPE_CHAT_MODEL', raising=False)
    assert QwenProvider().model == 'qwen3.8-flash'
