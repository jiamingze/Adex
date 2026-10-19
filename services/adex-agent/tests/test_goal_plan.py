import json
import pytest
from adex_agent.goals.planning import parse_plan


def test_goal_plan_is_bounded_and_cannot_inject_execution_fields():
    valid = {"title": "发布", "outcome": "可验证", "steps": ["完成检查"]}
    assert parse_plan(json.dumps(valid))["steps"] == ["完成检查"]
    for invalid in [
        {**valid, "owner_id": "another"},
        {**valid, "steps": [""]},
        {**valid, "steps": ["x"] * 13},
    ]:
        with pytest.raises(ValueError):
            parse_plan(json.dumps(invalid))
