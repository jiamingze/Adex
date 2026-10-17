import re
from adex_agent.routing.schedule import RELATIVE_TIME


def travel_intent(text):
    return bool(re.search(r"(规划|计划|安排).*(行程|旅游|旅行)|(旅行|旅游).*计划", text))


def background_kind(text):
    """Bounded explicit intent router; ordinary dialogue remains interactive."""
    if re.search(r"(深入研究|深度研究|调研报告|研究并.*报告)", text):
        return "RESEARCH"
    if re.search(r"(制作|生成|开发|做).*(小游戏|HTML游戏|网页游戏)", text, re.I):
        return "GAME"
    if (
        travel_intent(text)
        and re.search(r"后台|异步|关闭页面后", text)
        and not re.search(r"(不要|不用|无需|不必|别).{0,8}(后台|任务|异步)", text)
    ):
        return "TRAVEL"
    if re.search(r"(画|绘制|生成).*(架构图|流程图|时序图)", text):
        return "DIAGRAM"
    return None


def search_intent(text):
    """Use real evidence for explicit lookup and time-sensitive questions."""
    if re.search(r"(不要|不用|无需|别).{0,6}(联网|搜索|搜)", text):
        return False
    return travel_intent(text) or bool(
        re.search(
            r"(搜一下|搜下|搜索|帮我搜|查一下|查下|查询|浏览器|github|https?://|官网|这个网页|该页面|这个网站|继续浏览|\b(?:browse|visit|website)\b|(?:打开|访问|浏览).{0,30}(?:网站|网页))|"
            r"(近期|最近|最新|今天|明天|今年|现在|目前|实时|本周|本月).*(演唱会|新闻|天气|价格|发布|比赛|活动|消息|信息|动态|进展|航班|汇率|股价)|"
            r"(新闻|天气|汇率|股价|票价|航班|现任|开放时间)|"
            r"\b(latest|recent|current|today|tomorrow|news|weather|stock price|exchange rate)\b",
            text,
            re.I,
        )
    )


def original_music_intent(text):
    return bool(
        re.search(
            r"(生成|制作|创作|创造|写|做).*(音乐|歌曲|一首|一段|首歌)|(直接生成).*(音频|音乐)|^(改成|换成).*(纯音乐|伴奏)",
            text,
        )
    )


def schedule_intent(text):
    return bool(
        RELATIVE_TIME.search(text)
        or re.search(
            r"(创建|设置|安排|新建).*(定时任务|定时|提醒)|(每天|每日|每晚|每早|明天|每隔).*(帮我|整理|搜索|搜集|提醒|汇总|推送|发送|发我|发给我|监控)|(?:定时|定期).*(整理|搜索|提醒|汇总|发送)",
            text,
        )
    ) and not bool(
        re.search(
            r"(不要|不用|别).{0,6}(创建|设置|定时|定期|每天|提醒|[一二三四五六七八九十两\d]+\s*(?:分钟|小时|秒))",
            text,
        )
    )


def image_intent(text):
    return bool(
        re.search(
            r"(画|绘制|生成|制作|设计).*(图片|头像|插画|海报|壁纸|图像|照片)|(图片|头像|插画|海报|壁纸).*(画|生成|制作|设计)",
            text,
        )
    ) and not bool(re.search(r"架构图|流程图|时序图", text))
