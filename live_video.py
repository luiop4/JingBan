"""Route live browser questions separately from archive/video follow-ups."""
import re


def browse_video_command(text, recent=()):
    """Recognize direct session commands, not quotes, capability questions or memories."""
    text = str(text).strip()
    if len(text) > 240 or re.search(r'她说|他说|它说|回复[：:]|提示词|截图|为什么|为啥|什么原理|怎么实现|功能.*(?:吗|如何)|先不用改', text):
        return None
    site = bool(re.search(r'b\s*站|bilibili|漫游', text, re.I))
    history = [str(item.get('content', '')) if isinstance(item, dict) else str(item) for item in list(recent)[-8:]]
    context = any(re.search(r'b\s*站|bilibili|漫游|收藏夹|下一段视频', item, re.I) for item in history[-4:])
    context |= any(re.search(r'(?:本鲸|我).{0,12}(?:看视频|看完|换片)|播放器', item) for item in history[-4:])
    if (site or context) and re.search(r'(?:视频|播放|播放器).{0,12}(?:暂停|不动|卡住|停住|停在)|(?:暂停|停在|卡在).{0,10}(?:那里|那儿|视频)', text):
        return {'action': 'status'}
    source = 'favorites' if re.search(r'收藏|收藏夹', text) else 'search'
    if context and not re.search(r'随便|别的|搜索|推荐', text):
        for item in reversed(history):
            if re.search(r'收藏|收藏夹|b\s*站|bilibili|漫游', item, re.I):
                source = 'favorites' if re.search(r'收藏|收藏夹', item) else 'search'
                break
    if re.search(r'别停|不要停|不用停|不要跳过|别跳过|不用换|不要换|别换', text):
        return None
    if (site or context) and re.search(r'换一个|下一个(?:视频)?|下一条|跳过(?:这个|这段)?|这段别看|这个不看|换点别的', text):
        return {'action': 'next'}
    if (site or context) and re.search(r'(?:停止|暂停|取消|结束)(?:.{0,8})(?:刷|逛|看|漫游)|(?:别|不要|先别|不用)(?:再|继续)?(?:刷|逛|漫游)|(?:别看了|先不看了|停一下|停下来|算了不看)', text):
        return {'action': 'stop'}
    if re.search(r'现在.*(?:播放什么|正在看什么)|(?:看看|看下|识别).*(?:我|浏览器).*(?:正在|当前|在播|播放)', text):
        return None
    if (site or context) and re.search(r'进度|进展|漫游状态|(?:刷|逛|看)(?:到|了|过|得).{0,12}(?:什么|啥|好看|有意思|怎么样|吗|没有|了吗)|启动了吗|开始了吗|真的去了吗|你.*(?:刷|逛|漫游).{0,12}(?:了没|了吗|没有|怎么样|好看)|(?:还是|不就是).*(?:之前|旧|那两)', text):
        return {'action': 'status'}
    if context and not re.search(r'不去|别去|不要|不用|先别|不看|别看|不让|为什么|为啥', text):
        continuation = re.search(r'(?:你|本鲸)?(?:自己|继续|接着|再|去).{0,8}(?:看|逛|刷|挑)|(?:去吧|继续吧|接着吧|随便看|看你的)', text)
        assent = re.fullmatch(r'(?:好吧|好啊|好呀|行吧|可以|嗯|那就这样)[，,。！!\s]*', text)
        offered = history and re.search(r'继续|起一轮|去看|去刷|自己.{0,4}(?:看|逛)|挑.{0,4}新', history[-1])
        if continuation or assent and offered:
            return {'action': 'start', 'source': source, 'continuation': True}
    if not site or re.search(r'之前|以前|昨天|上次|怎么刷|如何刷|能不能刷|可以刷吗|不想|不让', text):
        return None
    if re.search(r'刷|逛|(?:开始|继续|启动).{0,5}漫游', text):
        if re.search(r'[“"「][^”"」]*(?:刷|逛)', text):
            return None
        if re.search(r'吗|么|？|\?', text) and not re.search(r'帮我|给我|请|去刷|去逛|开始|继续', text):
            return None
        return {'action': 'start', 'source': source}
    return None


def current_video_request(text):
    command = browse_video_command(text)
    if command and command['action'] in {'start', 'stop', 'next'}:
        return False
    video = re.search(r'B\s*站|bilibili|视频|播放器|浏览器', text, re.I)
    observe = re.search(r'看|读|识别|播放|放的|什么|啥', text)
    current = re.search(r'现在|当前|正在|在播|在放|在看|播的|播放的|播放什么|播放啥|'
                        r'看看.*(?:B\s*站|浏览器)|我.*(?:B\s*站|浏览器).*(?:播|放|看)', text, re.I)
    historical = re.search(r'之前|以前|上次|昨天|前天|上一个|最早|历史|回忆|刚才|刚刚|当时|那次', text)
    explicit_now = re.search(r'现在|当前|正在', text)
    return bool(video and observe and current and (not historical or explicit_now))
