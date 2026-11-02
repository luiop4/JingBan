"""Identify explicit archive questions without filtering short saved messages."""
import re


def asks_for_beginning(text):
    return bool(re.search(r'最开始|最早|最初|一开始|第一次|第一句|第一条|初次|开头', text)
                and re.search(r'说|聊|消息|对话|发|问|记得|记录|内容', text)
                and re.search(r'什么|啥|哪|记得|还记|找|查|引用|看看|内容|吗|么', text))


def archive_question(text, previous_users=()):
    beginning = asks_for_beginning(text)
    if not beginning and re.search(r'更早|再往前|前面还|之前还|漏了|漏掉|不是第一|不对|再查|重新查', text):
        beginning = any(asks_for_beginning(old) for old in list(previous_users)[-3:])
    # Explicit assistant-authored speech; a leading “你记得我…” still asks about the user.
    role = 'assistant' if re.search(
        r'你(?:最开始|最早|最初|一开始|第一次|的第一)(?:对我|跟我|和我)?(?:说|聊|发|回|答)|'
        r'你(?:的)?(?:第一句|第一条)(?:话|消息|回复|回答)|'
        r'你(?:当时)?(?:是怎么|怎么)(?:回复|回答)', text) else 'user'
    explicit = beginning or bool(re.search(
        r'记不记得|还记得|记得吗|说过什么|聊过什么|之前.*(?:说|提|聊|发)|'
        r'上次.*(?:说|提|聊|发)|我.*(?:说|提|聊|发)过|查.*(?:历史|记录)|翻.*(?:历史|记录)', text))
    return {'beginning': beginning, 'role': role, 'explicit': explicit}
