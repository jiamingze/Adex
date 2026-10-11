from adex_agent.routing.intent import image_intent, search_intent


def test_image_and_browser_intents():
    assert image_intent('帮我绘制一个适合个人助手的头像')
    assert image_intent('生成一张海报')
    assert not image_intent('帮我绘制一个架构图')
    assert not image_intent('这个头像不错')
    assert search_intent('去查GitHub上Adex项目')
