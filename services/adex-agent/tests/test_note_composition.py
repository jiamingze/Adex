import json
import pytest
from adex_agent.notes.composition import parse_note, compose_note
from adex_agent.models.provider import MockProvider


def test_note_json_validation_preserves_code_and_rejects_invalid_output():
    note = parse_note(
        "```json\n" + json.dumps({"title": "  技术方案  ", "content": "## API\n```java\ncode\n```"}) + "\n```"
    )
    assert note["title"] == "技术方案"
    assert "```java" in note["content"]
    for output in [
        "not JSON",
        '{"title":" ","content":"x"}',
        '{"title":"ok","content":""}',
        '{"title":"ok","content":"x","operation":"execute"}',
    ]:
        with pytest.raises(ValueError):
            parse_note(output)


async def test_compose_uses_stable_key_and_labelled_fixture():
    class FixtureRuntime:
        async def invoke(self, key, owner, messages):
            assert key == "note:owner:message"
            assert owner == "owner"
            async for event in MockProvider().stream(messages):
                yield event

    note = await compose_note(FixtureRuntime(), "owner", "message", "source technical plan")
    assert note["title"].startswith("TEST_FIXTURE")
    assert "非真实 AI" in note["content"]
    assert "source technical plan" in note["content"]
