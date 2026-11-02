"""Persistent interaction mode; task permissions stay with their existing gates."""
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QButtonGroup


def current_mode(window):
    value = window.settings.get('interaction', {}).get('mode', 'normal')
    return 'work' if value == 'work' else 'normal'


def is_work(window):
    return current_mode(window) == 'work'


def conversation_key(window):
    return 'local:work' if is_work(window) else 'local'


def mode_prompt(mode):
    if mode == 'work':
        return ('\n当前为工作模式：保持同一个角色、记忆和称呼，把注意力放在本轮任务和交付。'
                '先理解目标，使用实际工具推进，依据结果说明完成情况、产物位置和必要的未完成项。'
                '按任务需要给出完整解释、代码或方案，简单问题简短回答，不凑长文。'
                '减少角色闲聊、调侃、无关追问和表情，不自己开启与任务无关的活动。'
                '只有必要的执行进展或需要用户判断时才发过程消息，不把每一步拆成聊天。'
                '现有工具权限和批准方式继续适用；不能把模式切换当作额外授权，也不假称验证过未核实的结果。')
    return ('\n当前为普通模式：用户是你的主人，保持原有角色性格、兴趣和主见，自然交流；'
            '日常搭话顺着当下语气接，几字、一句或两句都行；复杂任务才展开。'
            '短句也可以表达不服、得意、好奇或关心，不把每句写成温柔客服式答复；'
            '不复述用户、不写进展报告，不在每条末尾追加提问。'
            '不为了卖萌强加口头禅或自导自演；也可以不接不感兴趣的话题。用户交代任务时认真处理，'
            '需要解释或代码时充分展开。自主活动沿用已保存的心跳、QQ和视频开关。')


class InteractionModes(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 3)
        self.segment = QFrame(window.composerFrame)
        self.segment.setObjectName('modeSegment')
        self.segment.setStyleSheet('''QFrame#modeSegment {background:#EDF1F7;border-radius:10px;}
          QToolButton {border:0;background:transparent;color:#788397;padding:5px 13px;border-radius:8px;font-size:12px;}
          QToolButton:hover {color:#355FC6;background:#E3EAF8;}
          QToolButton:checked {color:#315FC8;background:white;font-weight:600;}''')
        buttons = QHBoxLayout(self.segment)
        buttons.setContentsMargins(3, 3, 3, 3)
        buttons.setSpacing(2)
        self.group, self.buttons = QButtonGroup(self), {}
        for name, mode in (('普通', 'normal'), ('工作', 'work')):
            button = QToolButton(self.segment)
            button.setText(name)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip('自然交流与自主陪伴' if mode == 'normal' else '专注当前任务，暂缓自主活动')
            self.group.addButton(button)
            self.buttons[mode] = button
            buttons.addWidget(button)
            button.clicked.connect(lambda checked=False, value=mode: self.select(value))
        self.hint = QLabel(window.composerFrame)
        self.hint.setStyleSheet('color:#8B96A8;font-size:11px;background:transparent;')
        self.hint.setWordWrap(True)
        row.addWidget(self.segment)
        row.addWidget(self.hint, 1)
        window.composerLayout.insertLayout(0, row)
        self.render()
        window.qq_account_service.autonomy_allowed = lambda: not is_work(window)

    def render(self):
        self.buttons[current_mode(self.window)].setChecked(True)
        self.hint.setText('日常对话 · 记忆共享' if not is_work(self.window) else '工作对话 · 记忆共享')
        bodies = [getattr(row, 'message_body', None) for row in getattr(self.window, 'message_rows', {}).values()]
        bodies.append(getattr(self.window, 'active_label', None))
        for body in bodies:
            if body is not None:
                body.set_original_reasoning_visible(is_work(self.window))

    def select(self, mode):
        if mode not in self.buttons:
            raise ValueError('模式需要为 normal 或 work。')
        if mode == current_mode(self.window):
            self.render()
            return
        window = self.window
        if window.active_worker or window.jobs or window.attachment_worker or window.pending_attachments:
            self.hint.setText('先完成当前回复，或发送／移除待发附件后切换')
            self.render()
            self.hint.setText('先完成当前回复，或发送／移除待发附件后切换')
            return
        drafts = getattr(self, 'drafts', {})
        drafts[current_mode(window)] = window.messageInput.toPlainText()
        self.drafts = drafts
        previous = dict(window.settings.get('interaction', {}))
        window.settings['interaction'] = {**window.settings.get('interaction', {}), 'mode': mode}
        try:
            window.write_config()
        except Exception:
            window.settings['interaction'] = previous
            self.render()
            raise
        self.apply()
        window.messageInput.setPlainText(drafts.get(mode, ''))
        window._reload_timeline()

    def apply(self):
        window, mode = self.window, current_mode(self.window)
        self.render()
        if mode == 'work':
            window.companion.cancel_active()
            if window.qq_active.worker and not window.qq_active.worker.forced:
                window.qq_active.worker.requestInterruption()
            if window.qq_social.worker:
                window.qq_social.worker.requestInterruption()
            visits = window.bilibili_visits
            if (visits.session_active or visits.pending_request or visits.worker or visits.share_worker) and (
                    visits.session.get('agency_episode') or visits.session_active and not visits.manual):
                visits.stop_session('已切换工作模式，暂缓自主漫游。', cancel_share=True)
        else:
            window.companion.invalidate_decision()
            window.companion._schedule_next()
            window.companion.wake_for_experience()
        window.companion.refresh()
        window.heartbeat_panel.refresh()
