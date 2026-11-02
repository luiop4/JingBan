"""Request-time chronology hints; never rewrite stored conversation text."""
from datetime import datetime


def conversation_clock(messages, now=None):
    now = now or datetime.now().astimezone()
    def parse(item):
        try:
            value = datetime.fromisoformat(item['created_at'])
            return value.astimezone(now.tzinfo)
        except (KeyError, TypeError, ValueError):
            return None

    def elapsed(start, end):
        minutes = int((end - start).total_seconds() // 60)
        if minutes < 0:
            return '时间记录存在倒序，不能据此推断间隔'
        days, minutes = divmod(minutes, 1440)
        hours, minutes = divmod(minutes, 60)
        return (f'{days}天' if days else '') + (f'{hours}小时' if hours else '') + f'{minutes}分钟'

    hour = now.hour
    period = '凌晨' if hour < 6 else '早上' if hour < 12 else '下午' if hour < 18 else '晚上'
    lines = [f'当前本地日期和时间：{now.isoformat(timespec="seconds")}，星期{"一二三四五六日"[now.weekday()]}，{period}。']
    users = [(item, parse(item)) for item in messages if item['role'] == 'user']
    users = [(item, stamp) for item, stamp in users if stamp is not None]
    if users:
        item, stamp = users[-1]
        lines.append(f'最近用户消息 #{item["id"]} 发送于 {stamp.isoformat(timespec="minutes")}，距现在 {elapsed(stamp, now)}。')
    if len(users) >= 2:
        previous, current = users[-2][1], users[-1][1]
        lines.append(f'最近两次用户发言相隔 {elapsed(previous, current)}；本地日期从 {previous.date()} 到 {current.date()}。')
        if current.date() > previous.date():
            lines.append('这两次发言已经跨日，不能当作同一晚连续发生。')
    lines.append('按每条消息的发送日期理解“今天、明天、昨晚、准备睡觉”等表达。'
                 '睡觉、忙碌、看视频等是当时状态，不能自动延续到现在；长时间未聊不等于一直没睡。'
                 '隔夜后用户重新来聊，可自然问候或问睡得如何，不能无依据指责熬夜，也不能断言已经睡过或睡了多久。'
                 '当前用户明确说明的状态优先于旧消息和记忆。除非有必要，不报时间索引或机械解释时间差。')
    return '\n[本轮时间与对话间隔，仅供理解语境]\n' + '\n'.join(lines)
