"""Literal ordered intent matching; user text must not trigger regex backtracking."""

import re
from adex_agent.routing.schedule import RELATIVE_TIME, INTERVAL_TIME


def ordered_terms(text, before, after):
    """Match fixed terms in order on one line, in linear time for fixed vocabularies."""
    for line in text.casefold().split("\n"):
        ends = [position + len(term) for term in before if (position := line.find(term)) >= 0]
        if ends and any(line.find(term, min(ends)) >= 0 for term in after):
            return True
    return False


def travel_intent(text):
    return ordered_terms(text, ("规划", "计划", "安排"), ("行程", "旅游", "旅行")) or ordered_terms(
        text, ("旅行", "旅游"), ("计划",)
    )


def background_kind(text):
    """Ordinary dialogue remains interactive; only explicit background work routes here."""
    if any(term in text for term in ("深入研究", "深度研究", "调研报告")) or ordered_terms(
        text, ("研究并",), ("报告",)
    ):
        return "RESEARCH"
    if ordered_terms(text, ("制作", "生成", "开发", "做"), ("小游戏", "html游戏", "网页游戏")):
        return "GAME"
    if (
        travel_intent(text)
        and re.search(r"后台|异步|关闭页面后", text)
        and not re.search(r"(不要|不用|无需|不必|别).{0,8}(后台|任务|异步)", text)
    ):
        return "TRAVEL"
    if ordered_terms(text, ("画", "绘制", "生成"), ("架构图", "流程图", "时序图")):
        return "DIAGRAM"
    return None


def search_intent(text):
    """Use real evidence for explicit lookup and time-sensitive questions."""
    if re.search(r"(不要|不用|无需|别).{0,6}(联网|搜索|搜)", text):
        return False
    return (
        travel_intent(text)
        or bool(
            re.search(
                r"搜一下|搜下|搜索|帮我搜|查一下|查下|查询|浏览器|github|https?://|官网|这个网页|该页面|这个网站|继续浏览|\b(?:browse|visit|website)\b|(?:打开|访问|浏览).{0,30}(?:网站|网页)|"
                r"新闻|天气|汇率|股价|票价|航班|现任|开放时间|\b(latest|recent|current|today|tomorrow|news|weather|stock price|exchange rate)\b",
                text,
                re.I,
            )
        )
        or ordered_terms(
            text,
            ("近期", "最近", "最新", "今天", "明天", "今年", "现在", "目前", "实时", "本周", "本月"),
            (
                "演唱会",
                "新闻",
                "天气",
                "价格",
                "发布",
                "比赛",
                "活动",
                "消息",
                "信息",
                "动态",
                "进展",
                "航班",
                "汇率",
                "股价",
            ),
        )
        or ordered_terms(text, ("附近", "周边"), ("酒店", "餐厅", "咖啡", "医院", "景点"))
    )


def original_music_intent(text):
    return (
        ordered_terms(
            text, ("生成", "制作", "创作", "创造", "写", "做"), ("音乐", "歌曲", "一首", "一段", "首歌")
        )
        or ordered_terms(text, ("直接生成",), ("音频", "音乐"))
        or (text.startswith(("改成", "换成")) and ordered_terms(text, ("改成", "换成"), ("纯音乐", "伴奏")))
    )


def video_intent(text):
    return ordered_terms(text, ("生成", "制作", "创作", "做"), ("视频", "短片"))


def catalog_music_intent(text):
    return ordered_terms(text, ("搜索", "找", "推荐", "播放"), ("歌曲", "音乐", "歌单")) or ordered_terms(
        text, ("歌曲", "音乐", "歌单"), ("搜索", "推荐")
    )


def schedule_intent(text):
    requested = (
        bool(RELATIVE_TIME.search(text))
        or bool(INTERVAL_TIME.search(text))
        or ordered_terms(text, ("创建", "设置", "安排", "新建"), ("定时任务", "定时", "提醒"))
        or ordered_terms(
            text,
            (
                "每天",
                "每日",
                "每晚",
                "每早",
                "明天",
                "明早",
                "每隔",
                "每周",
                "每星期",
                "每月",
                "定期",
                "定时",
            ),
            ("帮我", "整理", "搜索", "搜集", "提醒", "汇总", "推送", "发送", "发我", "发给我", "监控"),
        )
        or ordered_terms(text, ("定时", "定期"), ("整理", "搜索", "提醒", "汇总", "发送"))
    )
    return requested and not bool(
        re.search(
            r"(不要|不用|别).{0,6}(创建|设置|定时|定期|每天|每隔|每|提醒|[一二三四五六七八九十两\d]{1,8}\s{0,16}(?:分钟|小时|秒))",
            text,
        )
    )


def image_intent(text):
    subjects = ("图片", "头像", "插画", "海报", "壁纸")
    return (
        ordered_terms(text, ("画", "绘制", "生成", "制作", "设计"), (*subjects, "图像", "照片"))
        or ordered_terms(text, subjects, ("画", "生成", "制作", "设计"))
    ) and not bool(re.search(r"架构图|流程图|时序图", text))
