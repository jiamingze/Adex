"""Adversarial text stays data; routing keeps literal order and line boundaries."""

import pytest
from adex_agent.routing.intent import (
    travel_intent,
    background_kind,
    image_intent,
    original_music_intent,
    search_intent,
    schedule_intent,
)
from adex_agent.routing.schedule import relative_chat_draft
from adex_kernel.text import strip_json_fence


def test_ordered_intents_keep_same_line_contract():
    assert travel_intent("安排上海旅行")
    assert travel_intent("旅行计划")
    assert not travel_intent("安排\n旅行")
    assert image_intent("生成一幅图片")
    assert not image_intent("生成流程图")
    assert original_music_intent("创作浪漫音乐")
    assert background_kind("研究并撰写报告") == "RESEARCH"
    assert search_intent("附近有什么酒店")
    assert not search_intent("不要搜索附近的酒店")
    assert schedule_intent("每天19点发我新闻")


def test_long_nonmatching_text_does_not_invent_a_route():
    text = "安排制作生成搜索" * 20000
    assert not travel_intent(text)
    assert not image_intent(text)
    assert not original_music_intent(text)
    assert background_kind(text) is None
    assert not schedule_intent(text)
    assert relative_chat_draft("9" * 20000 + "分钟后提醒我喝水") is None
    assert relative_chat_draft("1" + " " * 20000 + "分钟后提醒我喝水") is None


@pytest.mark.parametrize(
    "value",
    [
        ' {"title":"x"} ',
        '```json\n{"title":"x"}\n```',
        '```\n{"title":"x"}\n```',
    ],
)
def test_fence_boundaries(value):
    assert strip_json_fence(value) == '{"title":"x"}'


def test_json_internal_code_and_long_whitespace_are_preserved():
    value = '{"code":"```java"}'
    assert strip_json_fence("```json\n" + value + "\n```" + " " * 200000) == value
