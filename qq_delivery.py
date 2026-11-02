"""Split chat replies into ordered QQ bubbles without cutting code or URLs."""
import re


def split_reply(text, limit=260, *, compact=False):
    text = str(text).strip()
    if not text:
        return []
    if compact and len(text) <= 160 and not re.search(r'```|~~~|(?:^|\n)\s*(?:[-*]|\d+[.、])\s|\|.*\|', text):
        return [' '.join(line.strip() for line in text.splitlines() if line.strip())]
    blocks, paragraph, code = [], [], []
    fence = None
    for line in text.splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if fence:
            code.append(line)
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                blocks.append(('code', '\n'.join(code)))
                code, fence = [], None
        elif marker:
            if paragraph:
                blocks.append(('text', '\n'.join(paragraph)))
                paragraph = []
            fence, code = marker[1], [line]
        elif line.strip():
            paragraph.append(line)
        elif paragraph:
            blocks.append(('text', '\n'.join(paragraph)))
            paragraph = []
    if paragraph:
        blocks.append(('text', '\n'.join(paragraph)))
    if code:
        blocks.append(('code', '\n'.join(code)))
    result = []
    for kind, block in blocks:
        if kind == 'code':
            if len(block) <= 1800:
                result.append(block)
                continue
            lines = block.splitlines()
            opening = lines[0]
            closing = re.match(r'\s*(`{3,}|~{3,})', opening)[1]
            body = lines[1:-1] if re.fullmatch(r'\s*[`~]{3,}\s*', lines[-1]) else lines[1:]
            part = opening + '\n'
            for line in body:
                if len(part) + len(line) > 1700 and part != opening + '\n':
                    result.append(part.rstrip() + '\n' + closing)
                    part = opening + '\n'
                part += line + '\n'
            result.append(part.rstrip() + '\n' + closing)
            continue
        remaining = block.strip()
        while len(remaining) > limit:
            stop = max(remaining.rfind(mark, limit//3, limit) for mark in ('。', '！', '？', '；', '\n', '. ', '! ', '? '))
            cut = stop + 1 if stop >= 0 else limit
            # Keep the full URL/Markdown target in one bubble.
            for match in re.finditer(r'https?://\S+|\[[^\]]*\]\([^)]*\)', remaining):
                if match.start() < cut < match.end():
                    cut = match.start() if match.start() else match.end()
                    break
            result.append(remaining[:cut].strip())
            remaining = remaining[cut:].lstrip()
        if remaining:
            result.append(remaining)
    return [part for part in result if part]


from PySide6.QtCore import QThread, Signal


class QQVideoShareWorker(QThread):
    completed = Signal(object)

    def __init__(self, service, root, peer, visit, parent=None):
        super().__init__(parent)
        self.service, self.root, self.peer, self.visit = service, root, peer, dict(visit)

    def permitted(self):
        opts = self.service.snapshot()[0]
        allowed = self.peer in opts['account_allowlist'] or self.peer in self.service.reply_allowlist
        return (not self.service.closed and allowed and opts['browse_bilibili'] and opts['browse_share_qq']
                and opts['browse_share_peer'] == self.peer)

    def run(self):
        import base64
        from pathlib import Path
        from qq_bridge import QQActionError
        try:
            bridge = self.service.bridge
            if bridge is None or not self.permitted():
                raise QQActionError('桥接未连接或接收方未获授权。')
            paragraphs = split_reply(self.visit['note'])
            messages = [[{'type': 'text', 'data': {'text': paragraphs[0]}}]] if paragraphs else []
            frames = self.visit.get('frames', [])
            if frames:
                frame = frames[len(frames)//2]
                path = (Path(self.root)/frame['path']).resolve()
                if path.is_relative_to((Path(self.root)/'data/attachments').resolve()) and path.is_file() and path.stat().st_size < 4*1024**2:
                    messages.append([{'type': 'image', 'data': {'file': 'base64://' + base64.b64encode(path.read_bytes()).decode('ascii')}}])
            messages.extend([[{'type': 'text', 'data': {'text': part}}] for part in paragraphs[1:]])
            messages.append([{'type': 'text', 'data': {'text': self.visit['title'] + '\n' + self.visit['url']}}])
            result = bridge.send_bundle_wait(self.peer, messages, self.permitted, self.isInterruptionRequested)
            self.completed.emit(result)
        except Exception as error:
            self.completed.emit({'confirmed': False, 'error': str(error)[:200] if isinstance(error, QQActionError) else '分享任务未完成。',
                'outcome_unknown': bool(getattr(error, 'outcome_unknown', False))})


class QQSessionNoticeWorker(QThread):
    completed = Signal(object)

    def __init__(self, service, peer, text, parent=None):
        super().__init__(parent)
        self.service, self.peer, self.text = service, peer, text

    def permitted(self):
        return not self.service.closed and self.peer in self.service.snapshot()[0]['account_allowlist']

    def run(self):
        from qq_bridge import QQActionError
        try:
            bridge = self.service.bridge
            if bridge is None or not self.permitted():
                raise QQActionError('桥接未连接或权限已撤销，通知未发送。')
            messages = [[{'type': 'text', 'data': {'text': part}}] for part in split_reply(self.text)]
            self.completed.emit(bridge.send_bundle_wait(self.peer, messages, self.permitted, self.isInterruptionRequested))
        except Exception as error:
            self.completed.emit({'confirmed': False, 'error': str(error)[:180] if isinstance(error, QQActionError) else '状态通知未完成。',
                                 'outcome_unknown': bool(getattr(error, 'outcome_unknown', False))})
