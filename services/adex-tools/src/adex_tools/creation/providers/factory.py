"""Provider strategy selection. Creating an adapter never submits a paid generation request."""

from fastapi import HTTPException
from adex_tools.creation.contracts import MockMediaGenerationProvider, MediaSubmissionProvider
from .minimax import MiniMaxMusicProvider
from .acestep import AceStepMusicProvider
from .dashscope import DashScopeMediaProvider


def create_media_provider(name: str, kind: str) -> MediaSubmissionProvider:
    if name == "dashscope":
        return DashScopeMediaProvider(kind)
    strategies = {
        "mock": MockMediaGenerationProvider,
        "minimax": MiniMaxMusicProvider,
        "acestep": AceStepMusicProvider,
    }
    if name not in strategies or (name != "mock" and kind != "AUDIO"):
        raise HTTPException(503, "BLOCKED_EXTERNAL")
    return strategies[name]()
