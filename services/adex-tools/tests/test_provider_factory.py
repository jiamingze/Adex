from fastapi import HTTPException
import pytest
from adex_tools.creation.providers.factory import create_media_provider
from adex_tools.creation.contracts import MockMediaGenerationProvider
from adex_tools.creation.providers.dashscope import DashScopeMediaProvider


def test_factory_selects_adapters_without_submission(monkeypatch):
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'fixture-key')
    assert isinstance(create_media_provider('mock', 'IMAGE'), MockMediaGenerationProvider)
    assert isinstance(create_media_provider('dashscope', 'IMAGE'), DashScopeMediaProvider)
    with pytest.raises(HTTPException, match='BLOCKED_EXTERNAL'):
        create_media_provider('minimax', 'VIDEO')
