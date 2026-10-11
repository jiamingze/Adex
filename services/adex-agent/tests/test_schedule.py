import pytest
from pydantic import ValidationError
from adex_agent.schedule import ScheduleDraft


def test_daily_requires_timezone_and_time():
    base = dict(
        title="daily",
        instruction="task",
        kind="DAILY",
        timezone="Asia/Shanghai",
        first_fire_at="2026-10-11T00:00:00Z",
    )
    with pytest.raises(ValidationError):
        ScheduleDraft(**base)
    assert ScheduleDraft(**base, local_time="08:00").kind == "DAILY"


def test_interval_cannot_bypass_minimum_frequency():
    with pytest.raises(ValidationError):
        ScheduleDraft(
            title="fast",
            instruction="task",
            kind="INTERVAL",
            timezone="UTC",
            first_fire_at="2026-10-11T00:00:00Z",
            interval_seconds=1,
        )
