from adex_agent.routing.intent import background_kind


def test_router_keeps_chat_interactive():
    assert background_kind("你好，帮我解释一下数据库事务") is None
    assert background_kind("帮我深入研究数据库恢复并形成报告") == "RESEARCH"
    assert background_kind("生成一个HTML游戏") == "GAME"
    assert background_kind("画 Adex 架构图") == "DIAGRAM"


def test_travel_is_interactive_unless_background_is_explicit():
    from adex_agent.routing.intent import travel_intent
    text = "帮我安排一个上海出发到普吉岛的四天三晚行程"
    assert travel_intent(text)
    assert background_kind(text) is None
    assert background_kind("请在后台" + text) == "TRAVEL"
    assert background_kind("不要创建后台任务，" + text) is None
    assert not travel_intent("解释一下数据库事务")


def test_original_music_is_not_catalog_lookup():
    from adex_agent.routing.intent import original_music_intent
    assert original_music_intent('帮我写一首浪漫风格的，3分钟左右，适合放松听')
    assert original_music_intent('我要你直接生成音乐')
    assert not original_music_intent('搜索周杰伦的歌曲')
    assert original_music_intent('嗯激昂的音乐那就创造一首既而已')
    assert original_music_intent('帮我创作一首甜美的音乐')


def test_daily_schedule_chat_routes_before_search():
    from adex_agent.routing.intent import schedule_intent
    from adex_agent.routing.schedule import daily_chat_draft
    text='每天八点帮我整理网上最新关于spacx的信息'
    assert schedule_intent(text)
    draft=daily_chat_draft(text)
    assert draft['local_time']=='08:00' and draft['timezone']=='Asia/Shanghai'
    assert draft['instruction']=='整理网上最新关于SpaceX的信息'
    assert daily_chat_draft('每天晚上八点半提醒我运动')['local_time']=='20:30'
    assert daily_chat_draft('每天25点提醒我运动') is None
    assert daily_chat_draft('每天提醒我运动') is None
    assert not schedule_intent('帮我搜一下最新SpaceX新闻')
    assert not schedule_intent('不要每天提醒我')
    text='帮我创建一个定时任务每天8:00发送携程相关的行为'
    assert schedule_intent(text)
    assert daily_chat_draft(text)['instruction']=='发送携程相关的行为'
    assert daily_chat_draft(text)['local_time']=='08:00'
    assert schedule_intent('帮我创建定时任务')
    assert not schedule_intent('不要创建定时任务')
