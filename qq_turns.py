"""Collect a person's consecutive QQ messages into one reply opportunity."""
from __future__ import annotations

from collections import deque
import re
import time

from PySide6.QtCore import QObject, QTimer


def message_ids(job):
    return list(job.get('qq_message_ids') or [job['user_message_id']])


def merge_jobs(first, second):
    if first['peer_id'] != second['peer_id'] or first['conversation_key'] != second['conversation_key']:
        raise ValueError('不能合并不同联系人的消息。')
    ordered = sorted(set(message_ids(first) + message_ids(second)))
    latest = second if second['user_message_id'] >= first['user_message_id'] else first
    result = {**latest, 'user_message_id': ordered[-1], 'qq_message_ids': ordered}
    result['qq_account_authorized'] = bool(first.get('qq_account_authorized') or second.get('qq_account_authorized'))
    result['dialogue_followup'] = first.get('dialogue_followup') or second.get('dialogue_followup')
    batches = {}
    for job in (first, second):
        groups = job.get('qq_image_batches')
        if groups is None:
            groups = ([{'message_id': job['qq_image_message_id'], 'refs': job.get('qq_image_refs', [])}]
                      if job.get('qq_current_images') and job.get('qq_image_message_id') else [])
        for group in groups:
            batches[group['message_id']] = group
    result['qq_image_batches'] = [batches[key] for key in sorted(batches)]
    result['qq_current_images'] = bool(batches)
    return result


def grouped_rows(database, conversation, ids, through_id):
    rows = []
    for identity in sorted(set(ids)):
        row = database.get_message(identity)
        if (not row or row['role'] != 'user' or row['conversation_key'] != conversation
                or identity > through_id):
            raise ValueError('连续消息已改变或不属于当前QQ，已停止生成。')
        rows.append(row)
    return rows


def combined_text(rows):
    if len(rows) == 1:
        return rows[0]['content']
    return '\n'.join(f"[连续消息{index+1}] {row['content']}" for index, row in enumerate(rows))


def may_skip(text, scope, mode='normal'):
    # A model may choose silence for a reaction, never silently drop an
    # explicit question or operational request.
    return (mode == 'normal' and not any(scope.values())
            and not re.search(r'[?？]|为什么|为啥|怎么|怎么办|什么|啥|多少|哪[个里种]|能否|能不能|'
                              r'是否|请|帮我|给我|告诉我|回复我|回答我|看一下|看看|查一下', text))


def reply_prompt():
    return ('\nQQ回话取舍：同一人连续发的文字、图片和表情是一组意思，先看完再决定要不要接。'
            '一次只回应最值得接的一点，不把每张图、每条表情分别答一遍。'
            '一两句已接住意思就结束，不再追加成功后会怎样的脑补、不补泛泛的下一步。'
            '接过截图后紧跟的得意、点头或收尾表情，可以当作同一话题的情绪；不要又说“只有表情不知道成没成”或重复追问。'
            '话已经说到位，对方只是收尾、点头或发个不必接的表情时，可以不发任何消息，最终只输出[[no_reply]]。'
            '不为了活跃强找话题、不以沉默惩罚对方。对方明确提问、交代任务、要求答复或任务遇到问题时正常处理。'
            '没有说的就不说；不是每条用户消息都需要你的下一句。')


class QQTurnBuffer(QObject):
    quiet_seconds = 1.4
    max_wait = 5.0

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.pending = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.flush)

    def submit(self, job):
        peer, now = job['peer_id'], time.monotonic()
        first = now
        current = self.pending.pop(peer, None)
        if current:
            first = current['first']
            job = merge_jobs(current['job'], job)
        # Merge jobs that were already queued behind another person's reply.
        queue = deque()
        for queued in self.window.jobs:
            if queued.get('source') == 'qq' and queued.get('peer_id') == peer and not queued.get('regenerate_message_id'):
                job = merge_jobs(queued, job)
            else:
                queue.append(queued)
        self.window.jobs = queue
        self.pending[peer] = {'job': job, 'first': first, 'due': min(now+self.quiet_seconds, first+self.max_wait)}
        self._arm()

    def _arm(self):
        if self.pending:
            self.timer.start(max(1, round(1000*(min(r['due'] for r in self.pending.values())-time.monotonic()))))
        else:
            self.timer.stop()

    def flush(self):
        if self.window._resetting_data or getattr(self.window, '_closing', False):
            self.clear()
            return
        now = time.monotonic()
        ready = sorted((r for r in self.pending.values() if r['due'] <= now), key=lambda r: r['first'])
        for item in ready:
            job = item['job']
            self.pending.pop(job['peer_id'], None)
            self.window.jobs.append(job)
        self._arm()
        self.window.start_next_job()

    def is_current(self, job):
        return not job.get('qq_superseded')

    def clear(self):
        self.timer.stop()
        self.pending.clear()
