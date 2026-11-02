"""Whale heartbeat workspace: live state, real materials and persistent plans."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
from html import escape
import json
from pathlib import Path
import time
import uuid

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QSplitter, QTabWidget, QTextBrowser,
    QVBoxLayout, QWidget)


NAME = '鲸鱼心跳'
SECTIONS = ('overview', 'mechanism', 'interests', 'thought', 'materials', 'intentions', 'settings', 'journal')
KIND_NAMES = {'discovery': '发现与感想', 'video': '观看记录', 'experience': '实际执行', 'note': '手动便签'}
PLAN_NAMES = {'open': '惦记着', 'active': '进行中的打算', 'sleeping': '暂时放着', 'done': '已完成', 'dropped': '已放下'}
ACTIVITY_NAMES = {'running': '执行中', 'finished': '已结束', 'quiet': '安静活动', 'failed': '失败', 'interrupted': '中断'}


def text_label(text='', name='', parent=None):
    label = QLabel(text, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setMinimumWidth(0)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    if name:
        label.setObjectName(name)
    return label


def date_text(value):
    try:
        return datetime.fromisoformat(value).astimezone().strftime('%m-%d %H:%M')
    except (TypeError, ValueError):
        return str(value or '尚未安排')


def receipt_text(receipt):
    return ' · '.join(str(receipt.get(key) or '') for key in ('tool', 'status', 'target'))


class HeartbeatPanel(QWidget):
    def __init__(self, window, controller):
        super().__init__(window.pageStack)
        self.window, self.controller, self.db = window, controller, window.database
        self.setObjectName('heartbeatPage')
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self._settings_dirty = self._interest_dirty = self._thought_dirty = False
        self._loading = True
        self._material_signature = self._plan_signature = None
        self.material_rows, self.plan_rows = {}, {}
        self._source_url = ''
        self.setStyleSheet('''
            QWidget#heartbeatPage { background:#F6F8FC; }
            QFrame#hbHero { background:#EAF0FF; border:1px solid #D8E2FB; border-radius:16px; }
            QFrame#hbCard { background:white; border:1px solid #E1E7F2; border-radius:13px; }
            QLabel { background:transparent; border:0; color:#273950; }
            QLabel#hbTitle { font-size:21px; font-weight:700; color:#2C4B83; }
            QLabel#hbHeading { font-size:15px; font-weight:600; }
            QLabel#hbMuted { color:#71809A; font-size:12px; }
            QLabel#hbValue { font-size:18px; font-weight:600; color:#365FC1; }
            QLabel#hbBadge { color:#3D60A4; background:#F8FAFF; border-radius:9px; padding:6px 10px; }
            QPushButton { padding:8px 12px; border:1px solid #DCE4F1; border-radius:8px; background:white; }
            QPushButton:hover { background:#EEF3FF; border-color:#A4BAED; }
            QPushButton#hbPrimary { background:#4D70CF; color:white; border-color:#4D70CF; }
            QPushButton#hbPrimary:hover { background:#3D60BB; }
            QTabWidget::pane { border:0; background:transparent; }
            QTabBar::tab { background:transparent; color:#73809A; padding:11px 12px; border-bottom:2px solid transparent; }
            QTabBar::tab:selected { color:#3B60BC; border-bottom:2px solid #5378D2; font-weight:600; }
            QScrollArea { border:0; background:transparent; }
            QWidget#hbContents { background:transparent; }
            QPlainTextEdit, QTextBrowser, QLineEdit, QComboBox, QSpinBox {
                border:1px solid #DFE6F2; border-radius:8px; padding:8px; background:#FAFBFE; }
            QPlainTextEdit:focus, QLineEdit:focus { border-color:#8DA8E8; }
            QListWidget { background:#FAFBFE; border:1px solid #DFE6F2; border-radius:10px; padding:4px; }
            QListWidget::item { padding:10px 8px; border-radius:7px; }
            QListWidget::item:selected { background:#E5EDFF; color:#355DAF; }
            QCheckBox { spacing:8px; padding:5px 0; background:transparent; }
        ''')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 12)
        outer.setSpacing(10)
        hero = QFrame(self)
        hero.setObjectName('hbHero')
        row = QHBoxLayout(hero)
        row.setContentsMargins(18, 15, 18, 15)
        identity = QVBoxLayout()
        identity.addWidget(text_label(NAME, 'hbTitle', hero))
        identity.addWidget(text_label('有自己的打算，也有想与你分享的瞬间。', 'hbMuted', hero))
        row.addLayout(identity, 1)
        self.badge = text_label('', 'hbBadge', hero)
        self.badge.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        row.addWidget(self.badge)
        self.toggle_button = QPushButton(hero)
        self.toggle_button.setObjectName('hbPrimary')
        self.toggle_button.clicked.connect(self.toggle)
        row.addWidget(self.toggle_button)
        outer.addWidget(hero)
        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setExpanding(False)
        outer.addWidget(self.tabs, 1)
        self.pages = {}
        for key, title in zip(SECTIONS, ('总览', '心跳机制', '兴趣范围', '心事匣', '素材池', '打算账本', '节律与权限', '运行记录')):
            area = QScrollArea(self.tabs)
            area.setProperty('heartbeatSection', key)
            area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            contents = QWidget(area)
            contents.setObjectName('hbContents')
            contents.setMinimumWidth(0)
            contents.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            box = QVBoxLayout(contents)
            box.setContentsMargins(0, 12, 6, 10)
            box.setSpacing(12)
            area.setWidget(contents)
            self.tabs.addTab(area, title)
            self.pages[key] = (contents, box)
        self._build_overview()
        self._build_mechanism()
        self._build_interests()
        self._build_thought()
        self._build_materials()
        self._build_intentions()
        self._build_settings()
        self._build_journal()
        self.feedback = text_label('', 'hbMuted', self)
        outer.addWidget(self.feedback)
        self.load_options()
        self._loading = False
        self.tabs.currentChanged.connect(lambda _index: self.refresh())
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

    def card(self, key, title, description=''):
        parent, target = self.pages[key]
        frame = QFrame(parent)
        frame.setObjectName('hbCard')
        frame.setMinimumWidth(0)
        box = QVBoxLayout(frame)
        box.setContentsMargins(17, 15, 17, 15)
        box.setSpacing(9)
        box.addWidget(text_label(title, 'hbHeading', frame))
        if description:
            box.addWidget(text_label(description, 'hbMuted', frame))
        target.addWidget(frame)
        return frame, box

    def finish(self, key):
        self.pages[key][1].addStretch(1)

    def buttons(self, box, specs):
        row = QHBoxLayout()
        row.setSpacing(8)
        result = []
        for title, callback in specs:
            button = QPushButton(title, self)
            button.clicked.connect(callback)
            row.addWidget(button)
            result.append(button)
        row.addStretch(1)
        box.addLayout(row)
        return result

    def _build_overview(self):
        frame, box = self.card('overview', '此刻', '开启后可以持续做事；开口的时机由具体进展和处境决定。')
        self.live_status = text_label('', 'hbValue', frame)
        self.live_goal = text_label('', parent=frame)
        self.live_next = text_label('', 'hbMuted', frame)
        self.live_due = text_label('', 'hbMuted', frame)
        for item in (self.live_status, self.live_goal, self.live_next, self.live_due):
            box.addWidget(item)
        self.wake_button, self.talk_button = self.buttons(box, (
            ('唤醒一次', self.wake), ('现在找我聊聊', lambda: self.controller.tick(force=True))))
        frame, box = self.card('overview', '心跳留下了什么')
        self.metrics = text_label('', 'hbValue', frame)
        box.addWidget(self.metrics)
        self.latest_choice = text_label('', parent=frame)
        box.addWidget(self.latest_choice)
        frame, box = self.card('overview', '互动去向')
        self.destination = text_label('', parent=frame)
        box.addWidget(self.destination)
        self.buttons(box, (('查看QQ接入', lambda: self.window.show_page(3)),))
        self.finish('overview')

    def _build_mechanism(self):
        frame, box = self.card('mechanism', '一次心跳如何发生', '从有来由的事情开始，经过真实行动，再决定是否开口。')
        self.stages = []
        for number, title, detail in (
                ('01', '留意新情况', '近期聊天、实际观看结果，或之前想继续的打算。'),
                ('02', '形成选择', '结合兴趣和未完想法，选择做事、聊天或休息。'),
                ('03', '实际行动', '调用现有工具搜索、阅读、创作或使用应用。'),
                ('04', '留下见闻', '保存真实来源和自己的感想，供以后继续。'),
                ('05', '决定分享', '有想说的再来聊；也可以安静结束。')):
            label = text_label(number+'  '+title+'\n'+detail, parent=frame)
            label.setContentsMargins(12, 10, 12, 10)
            box.addWidget(label)
            self.stages.append(label)
        self.mechanism_status = text_label('', 'hbMuted', frame)
        box.addWidget(self.mechanism_status)
        frame, box = self.card('mechanism', '她什么时候会醒来')
        box.addWidget(text_label('自己安排的继续时间、新聊天、实际视频结果，都可以引起注意。没有具体打算时才使用参考间隔。唤醒不等于必须发消息。', parent=frame))
        self.buttons(box, (('调整节律', lambda: self.open_section('settings')), ('查看为什么没开口', lambda: self.open_section('journal'))))
        self.finish('mechanism')

    def _build_interests(self):
        frame, box = self.card('interests', '兴趣范围', '可以给她一些方向，她也可以在相处和实际见闻中形成自己的兴趣。')
        self.interests = QPlainTextEdit(frame)
        self.interests.setPlaceholderText('例如：游戏设计、动画、小工具、没弄明白的科学问题……')
        self.interests.setMinimumHeight(105)
        self.interests.setMaximumHeight(155)
        self.interests.textChanged.connect(lambda: self.mark_dirty('interest'))
        box.addWidget(self.interests)
        self.buttons(box, (('保存兴趣方向', self.save_interests),))
        frame, box = self.card('interests', '她现在在意的东西')
        self.own_interests = text_label('', parent=frame)
        self.own_mood = text_label('', 'hbMuted', frame)
        box.addWidget(self.own_interests)
        box.addWidget(self.own_mood)
        self.finish('interests')

    def _build_thought(self):
        frame, box = self.card('thought', '心事匣', '留给下一次心跳的一点想法。她可以更新，你也可以在这里留一张便签。')
        self.thought = QPlainTextEdit(frame)
        self.thought.setPlaceholderText('还没想完的事、下次想接着聊的话……')
        self.thought.setMinimumHeight(150)
        self.thought.setMaximumHeight(240)
        self.thought.textChanged.connect(lambda: self.mark_dirty('thought'))
        box.addWidget(self.thought)
        self.buttons(box, (('保存便签', self.save_thought), ('清空便签', lambda: self.save_thought(clear=True))))
        box.addWidget(text_label('便签是想法，不代表已经做过的事；实际发现会单独保留在素材池。', 'hbMuted', frame))
        self.finish('thought')

    def _build_materials(self):
        frame, box = self.card('materials', '素材池', '真实见闻、观看感想和留住的小事。参与过选择，不等于已经向用户分享。')
        row = QHBoxLayout()
        self.material_filter = QComboBox(frame)
        self.material_filter.addItem('全部素材', '')
        for key, title in KIND_NAMES.items():
            self.material_filter.addItem(title, key)
        self.material_search = QLineEdit(frame)
        self.material_search.setPlaceholderText('搜索素材')
        row.addWidget(self.material_filter)
        row.addWidget(self.material_search, 1)
        box.addLayout(row)
        self.material_filter.currentIndexChanged.connect(lambda: self.refresh_materials())
        self.material_search.textChanged.connect(lambda: self.refresh_materials())
        split = QSplitter(Qt.Orientation.Vertical, frame)
        self.material_list = QListWidget(split)
        self.material_list.setWordWrap(True)
        self.material_list.setMinimumHeight(155)
        self.material_detail = QTextBrowser(split)
        self.material_detail.setOpenLinks(False)
        self.material_detail.setMinimumHeight(160)
        split.addWidget(self.material_list)
        split.addWidget(self.material_detail)
        split.setMinimumHeight(335)
        box.addWidget(split)
        self.material_list.currentItemChanged.connect(self.select_material)
        self.material_image = QLabel(frame)
        self.material_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.material_image.hide()
        box.addWidget(self.material_image)
        self.source_button, self.attend_button = self.buttons(box, (
            ('打开原始来源', self.open_source), ('下次留意这条', self.attend_material)))
        self.source_button.setEnabled(False)
        self.attend_button.setEnabled(False)
        box.addWidget(text_label('显示最近100条匹配素材；搜索可以查找更早的记录。', 'hbMuted', frame))

    def _build_intentions(self):
        frame, box = self.card('intentions', '打算账本', '她惦记着的事和下一步。你可以让某件事暂放，或明确放下。')
        self.plan_filter = QComboBox(frame)
        self.plan_filter.addItem('待续的打算', 'pending')
        self.plan_filter.addItem('所有打算', 'all')
        self.plan_filter.addItem('已完成 / 已放下', 'closed')
        self.plan_filter.currentIndexChanged.connect(lambda: self.refresh_plans())
        box.addWidget(self.plan_filter)
        self.plan_list = QListWidget(frame)
        self.plan_list.setWordWrap(True)
        self.plan_list.setMinimumHeight(160)
        self.plan_list.setMaximumHeight(260)
        self.plan_detail = QTextBrowser(frame)
        self.plan_detail.setMinimumHeight(150)
        box.addWidget(self.plan_list)
        box.addWidget(self.plan_detail)
        self.plan_list.currentItemChanged.connect(self.select_plan)
        self.plan_buttons = self.buttons(box, (('继续考虑', lambda: self.change_plan('open')),
            ('暂时放着', lambda: self.change_plan('sleeping')), ('放下这件事', lambda: self.change_plan('dropped'))))
        self.finish('intentions')

    def _build_settings(self):
        self.checks = {}
        frame, box = self.card('settings', '自主与在场', '由她决定做什么、做多久和何时休息。')
        for key, title in (('self_directed', '允许自己选事做并保留打算'),
                           ('away_activities', '长时间未操作或锁屏时，仍可做后台工作')):
            self.check(key, title, frame, box)
        frame, box = self.card('settings', '观察与电脑操作', '需要时才读取画面；电脑操作沿用聊天栏的总开关与批准方式。')
        for key, title in (('observe_window', '允许了解窗口标题'), ('observe_screen', '允许按需读取屏幕'),
                           ('allow_actions', '允许主动操作电脑'),
                           ('playful_computer', '允许她实际移动鼠标、挪动窗口来逗你（Esc可停）')):
            self.check(key, title, frame, box)
        self.computer_gate = text_label('', 'hbMuted', frame)
        box.addWidget(self.computer_gate)
        frame, box = self.card('settings', '自由安排', '由兴趣、未完的事情和新进展唤起活动；下一次何时继续由她决定。')
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.interval = QSpinBox(frame)
        self.interval.setRange(1, 120)
        self.interval.setSuffix(' 分钟')
        self.unanswered = QSpinBox(frame)
        self.unanswered.setRange(1, 10)
        self.unanswered.setSuffix(' 次')
        self.interval.hide()
        self.unanswered.hide()
        box.addLayout(form)
        self.interval.valueChanged.connect(lambda: self.mark_dirty('settings'))
        self.unanswered.valueChanged.connect(lambda: self.mark_dirty('settings'))
        self.checks['self_directed'].toggled.connect(lambda value: self.unanswered.setEnabled(not value))
        box.addWidget(text_label('自主做事不按每日次数或总时长分配额度；后台决策和执行会使用已配置的模型。', 'hbMuted', frame))
        frame, box = self.card('settings', '消息提醒')
        self.check('notifications', '后台消息弹出通知并闪烁任务栏', frame, box)
        self.check('notification_sound', '同时播放提示音', frame, box)
        self.checks['notifications'].toggled.connect(self.checks['notification_sound'].setEnabled)
        self.buttons(box, (('保存偏好与权限', self.save_settings), ('恢复已保存设置', self.restore_settings)))
        self.finish('settings')

    def has_editor_focus(self):
        return self.isVisible() and any(widget.hasFocus() for widget in
            (self.interests, self.thought, self.material_search, self.interval, self.unanswered))

    def _build_journal(self):
        frame, box = self.card('journal', '心跳运行记录', '查看选择的来由和实际工具结果。休息、失败和中断都如实展示。')
        self.journal = QTextBrowser(frame)
        self.journal.setMinimumHeight(380)
        box.addWidget(self.journal)
        self.buttons(box, (('刷新记录', self.refresh), ('查看全部历史', self.window.show_history_manager)))

    def check(self, key, title, parent, box):
        widget = QCheckBox(title, parent)
        widget.toggled.connect(lambda _value: self.mark_dirty('settings'))
        self.checks[key] = widget
        box.addWidget(widget)

    def mark_dirty(self, part):
        if self._loading:
            return
        setattr(self, '_'+part+'_dirty', True)

    def load_options(self):
        options = self.controller.options()
        self._loading = True
        for key, widget in self.checks.items():
            widget.setChecked(bool(options[key]))
        self.interval.setValue(int(options['interval_minutes']))
        self.unanswered.setValue(int(options['max_unanswered']))
        self.unanswered.setEnabled(not options['self_directed'])
        self.checks['notification_sound'].setEnabled(bool(options['notifications']))
        self.interests.setPlainText(str(options['interests_hint']))
        self._loading = False
        self._settings_dirty = self._interest_dirty = False

    def open_section(self, key='overview'):
        index = next((i for i in range(self.tabs.count()) if self.tabs.widget(i).property('heartbeatSection') == key), 0)
        self.tabs.setCurrentIndex(index)
        self.refresh()

    def toggle(self):
        self.controller.set_enabled(not self.controller.options()['enabled'])
        self.refresh()

    def wake(self):
        if self.controller.options()['enabled']:
            self.controller.attention_due = time.monotonic()
            self.controller.tick()
            self.feedback.setText('已唤醒；正在输入、聊天或等待回应时，会先让位。')
        self.refresh()

    def save_settings(self):
        values = {key: widget.isChecked() for key, widget in self.checks.items()}
        values.update(interval_minutes=self.interval.value(), max_unanswered=self.unanswered.value())
        self.controller.update_options(values)
        self._settings_dirty = False
        self.feedback.setText('节律与权限已保存。')
        self.refresh()

    def restore_settings(self):
        self.load_options()
        self.feedback.setText('已恢复保存过的设置。')

    def save_interests(self):
        self.controller.update_options({'interests_hint': self.interests.toPlainText().strip()[:500]})
        self.interests.setPlainText(str(self.controller.options()['interests_hint']))
        self._interest_dirty = False
        self.feedback.setText('兴趣方向已保存，后续心跳会参考。')

    def save_thought(self, clear=False):
        from companion_life import add_event
        value = '' if clear else self.thought.toPlainText().strip()[:1200]
        self.controller.invalidate_decision()
        with closing(self.db._connect()) as con, con:
            con.execute("INSERT INTO companion_meta VALUES('unfinished_thought',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (value,))
        add_event(self.db, 'note:'+uuid.uuid4().hex, 'note',
                  {'title': '你留下的便签' if value else '你清空了心事匣', 'reflection': value,
                   'origin': 'user', 'note': '用户手动编辑的想法资料，不是已经执行的经历。'})
        self._loading = True
        self.thought.setPlainText(value)
        self._loading = False
        self._thought_dirty = False
        self.controller.wake_for_experience()
        self.feedback.setText('便签已清空。' if clear else '便签已保存。')
        self.refresh()

    def refresh(self):
        if not self.isVisible() or getattr(self.window, '_resetting_data', False):
            return
        from agency import state
        from companion_life import overview
        from chat_flow import pending
        options = self.controller.options()
        own, life = state(self.db), overview(self.db)
        waiting = pending(self.db, 'local')
        active = self.window.active_job or {}
        visits = getattr(self.window, 'bilibili_visits', None)
        enabled = bool(options['enabled'])
        from interaction_modes import is_work
        working = is_work(self.window)
        phase, status = -1, '尚未开启'
        if enabled:
            phase, status = -1, '安静待着，等下一次想起'
            if waiting:
                status = '在等你回应：'+waiting['question']
            elif self.window.active_worker:
                if active.get('proactive'):
                    phase, status = 2, getattr(self.controller, 'activity_status', '') or '在推进自己的打算'
                    if status.startswith('正在留下这次的发现'):
                        phase = 3
                    elif status.startswith(('正在分享', '正在发送')):
                        phase = 4
                    elif status.startswith(('正在整理对话', '正在读取当前窗口')):
                        phase = 0
                else:
                    status = '先陪你处理这次对话'
            elif self.controller.decision_worker:
                phase, status = 1, '在想这次做什么、说什么'
            elif visits and visits.session_active and visits.session.get('agency_episode'):
                phase, status = 2, visits.status
            elif self.controller.failures:
                status = self.controller.status
            elif not self.window.settings['deepseek'].get('api_key', '').strip():
                status = '请先在设置中配置聊天模型'
            elif self.window.messageInput.toPlainText().strip() or self.window.pending_attachments:
                status = '你正在准备消息，先等你'
            elif self.has_editor_focus():
                status = '你正在编辑心跳内容，先等你'
        self.badge.setText('● 心跳已开启' if enabled else '○ 心跳已暂停')
        if working and enabled:
            phase, status = -1, '工作模式暂缓自动心跳，保留原有开关和计划'
            self.badge.setText('工作模式 · 自动暂缓')
        self.toggle_button.setText('暂停心跳' if enabled else '开启心跳')
        self.wake_button.setEnabled(enabled and not working)
        self.talk_button.setEnabled(enabled)
        self.live_status.setText(status)
        self.live_goal.setText('当前打算：'+(own['goal'] or '还没选定，醒来后自己决定'))
        self.live_next.setText('接下来：'+(own['next_step'] or '没有留下具体下一步'))
        due = min(self.controller.next_due, self.controller.attention_due) if self.controller.attention_due else self.controller.next_due
        seconds = max(0, int(due-time.monotonic()))
        wake = ('很快再想起' if seconds < 60 else '约 '+str((seconds+59)//60)+' 分钟后') if enabled else '心跳暂停中'
        if working and enabled:
            wake = '工作模式暂缓，切回普通模式后继续判断'
        self.live_due.setText('下次唤醒：'+wake+(' · '+own.get('resume_reason', '') if own.get('resume_reason') else ''))
        self.mechanism_status.setText('此刻：'+status+'。按实际决策与执行状态显示。')
        for index, label in enumerate(self.stages):
            label.setStyleSheet('background:#EAF0FF; border:1px solid #C9D9FA; border-radius:9px; color:#3B60AE;'
                               if index == phase else 'background:#F7F9FD; border:1px solid #E8EDF5; border-radius:9px; color:#6B7B93;')
        with closing(self.db._connect()) as con:
            plans = con.execute("SELECT count(*) FROM companion_intentions WHERE status NOT IN ('done','dropped')").fetchone()[0]
            materials = con.execute("SELECT count(*) FROM companion_events WHERE kind IN ('discovery','video','experience','note')").fetchone()[0]
            decisions = con.execute('SELECT count(*) FROM companion_decisions').fetchone()[0]
            usage = con.execute("SELECT coalesce(sum(total_tokens),0) FROM api_usage WHERE request_kind IN ('companion_decision','proactive') AND substr(created_at,1,10)=?", (self.db._now()[:10],)).fetchone()[0]
        self.metrics.setText(f'{plans} 个待续打算   ·   {materials} 条素材   ·   {decisions} 次选择')
        latest = life['decisions'][0]['payload'] if life['decisions'] else None
        self.latest_choice.setText(('最近选择：'+{'act': '做事', 'talk': '想聊聊', 'rest': '休息'}.get(latest.get('choice'), '')+' · '+str(latest.get('reason', '')) if latest else '还没有内部选择记录。')+f'\n今日已记录用量：{usage:,} Token')
        peer = self.db._owner_peer
        self.destination.setText('主动对话出现在客户端。'+('本人QQ已绑定：'+peer+'，沿用QQ接入的同步与通知设置。' if peer else '本人QQ尚未绑定，可到QQ接入中选择。'))
        self.own_interests.setText('、'.join(own['interests']) or '还没有形成持续兴趣。')
        self.own_mood.setText('她留下的心情：'+(own['mood'] or '暂时没有记录'))
        if not self._thought_dirty and not self.thought.hasFocus() and self.thought.toPlainText() != life['unfinished_thought']:
            self._loading = True
            self.thought.setPlainText(life['unfinished_thought'])
            self._loading = False
        self.computer_gate.setText('电脑总开关：'+('已开启 · '+('自动批准' if self.window.agentAutoApproveAction.isChecked() else '逐次确认')
                                                     if self.window.agentEnabledCheckBox.isChecked() else '已关闭'))
        section = self.tabs.currentWidget().property('heartbeatSection')
        if section == 'materials':
            self.refresh_materials()
        elif section == 'intentions':
            self.refresh_plans()
        elif section == 'journal':
            self.refresh_journal()

    def _fill_list(self, widget, rows, title, signature_name):
        signature = json.dumps(rows, ensure_ascii=False, sort_keys=True)
        if signature == getattr(self, signature_name):
            return
        setattr(self, signature_name, signature)
        selected = widget.currentItem().data(Qt.ItemDataRole.UserRole) if widget.currentItem() else None
        scroll = widget.verticalScrollBar().value()
        widget.blockSignals(True)
        widget.clear()
        chosen = None
        for row in rows:
            item = QListWidgetItem(title(row))
            item.setData(Qt.ItemDataRole.UserRole, row['id'])
            widget.addItem(item)
            if row['id'] == selected:
                chosen = item
        widget.blockSignals(False)
        if chosen:
            widget.setCurrentItem(chosen)
        elif rows:
            widget.setCurrentRow(0)
        else:
            widget.currentItemChanged.emit(None, None)
        widget.verticalScrollBar().setValue(scroll)

    def refresh_materials(self):
        kind = self.material_filter.currentData()
        query = self.material_search.text().strip()
        where, values = ["kind IN ('discovery','video','experience','note')"], []
        if kind:
            where.append('kind=?')
            values.append(kind)
        if query:
            where.append("payload LIKE ? ESCAPE '\\'")
            values.append('%'+query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')+'%')
        with closing(self.db._connect()) as con:
            rows = [dict(row) for row in con.execute('SELECT * FROM companion_events WHERE '+' AND '.join(where)+' ORDER BY id DESC LIMIT 100', values)]
        for row in rows:
            row['payload'] = json.loads(row['payload'])
        self.material_rows = {row['id']: row for row in rows}
        def title(row):
            value = row['payload']
            return KIND_NAMES.get(row['kind'], row['kind'])+' · '+str(value.get('title') or value.get('goal') or '实际工具经历')[:130]+'\n'+date_text(row['created_at'])+' · '+('已参与选择' if row['handled'] else '等待留意')
        self._fill_list(self.material_list, rows, title, '_material_signature')

    def select_material(self, item, previous=None):
        self.material_image.hide()
        self._source_url = ''
        row = self.material_rows.get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        self.attend_button.setEnabled(bool(row))
        if not row:
            self.material_detail.setPlainText('还没有匹配的素材。真实发现和观看结果会保存在这里。')
            self.source_button.setEnabled(False)
            return
        value = row['payload']
        title = str(value.get('title') or value.get('goal') or '实际工具经历')
        lines = [str(value.get('reflection') or value.get('impression') or value.get('note') or '')]
        sources = value.get('receipts', [])
        if value.get('url'):
            self._source_url = str(value['url'])
            lines.extend(['', '来源：'+self._source_url])
        for receipt in sources:
            lines.append(receipt_text(receipt))
            if not self._source_url:
                self._source_url = str((receipt.get('facts') or {}).get('url') or '')
        self.material_detail.setHtml('<h3>'+escape(title)+'</h3><p style="line-height:155%">'+escape('\n'.join(lines)).replace('\n', '<br>')+'</p>')
        self.source_button.setEnabled(QUrl(self._source_url).scheme().lower() in {'http', 'https'})
        if row['kind'] == 'video':
            from autonomous_video import read_visits
            root = Path(__file__).resolve().parent
            visit = next((r for r in read_visits(root) if r.get('id') == value.get('video_id')), None)
            if visit and visit.get('frames'):
                path = Path(visit['frames'][len(visit['frames'])//2]['path'])
                path = (root/path).resolve() if not path.is_absolute() else path.resolve()
                if path.is_relative_to((root/'data/attachments').resolve()) and path.is_file():
                    pixmap = QPixmap(str(path))
                    if not pixmap.isNull():
                        self.material_image.setPixmap(pixmap.scaled(max(160, min(600, self.width()-100)), 230,
                            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                        self.material_image.show()

    def open_source(self):
        url = QUrl(self._source_url)
        if url.scheme().lower() in {'http', 'https'}:
            QDesktopServices.openUrl(url)

    def attend_material(self):
        item = self.material_list.currentItem()
        if not item:
            return
        self.controller.invalidate_decision()
        with closing(self.db._connect()) as con, con:
            con.execute('UPDATE companion_events SET handled=0 WHERE id=?', (item.data(Qt.ItemDataRole.UserRole),))
        self.controller.wake_for_experience()
        self.feedback.setText('下次心跳会重新留意这条资料；不会直接重放旧操作。')
        self.refresh_materials()

    def refresh_plans(self):
        mode = self.plan_filter.currentData()
        where = "status NOT IN ('done','dropped')" if mode == 'pending' else "status IN ('done','dropped')" if mode == 'closed' else '1=1'
        with closing(self.db._connect()) as con:
            rows = [dict(row) for row in con.execute('SELECT * FROM companion_intentions WHERE '+where+' ORDER BY updated_at DESC LIMIT 100')]
        self.plan_rows = {row['id']: row for row in rows}
        self._fill_list(self.plan_list, rows, lambda row: PLAN_NAMES.get(row['status'], row['status'])+' · '+row['title']+'\n'+date_text(row['updated_at']), '_plan_signature')

    def select_plan(self, item, previous=None):
        row = self.plan_rows.get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        for button in self.plan_buttons:
            button.setEnabled(bool(row and row['status'] != 'done'))
        if not row:
            self.plan_detail.setPlainText('还没有这类打算。她选定要做的事情后会留在这里。')
            return
        self.plan_detail.setPlainText(row['title']+'\n\n状态：'+PLAN_NAMES.get(row['status'], row['status'])+
            '\n下一步：'+(row['next_step'] or '尚未留下')+'\n未完想法：'+(row['thought'] or '尚未留下'))

    def change_plan(self, status):
        item = self.plan_list.currentItem()
        row = self.plan_rows.get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        if not row or row['status'] == 'done':
            return
        from agency import state
        from companion_life import add_event
        own = state(self.db)
        affects_current = (own['goal'][:250] == row['title'] or
                           ((self.window.active_job or {}).get('life_decision') or {}).get('intention_id') == row['id'])
        if affects_current:
            self.controller.cancel_active()
        else:
            self.controller.invalidate_decision()
        with closing(self.db._connect()) as con, con:
            con.execute('UPDATE companion_intentions SET status=?,updated_at=? WHERE id=?', (status, self.db._now(), row['id']))
            if status == 'open':
                con.execute('DELETE FROM companion_meta WHERE key=?', ('hold:'+row['id'],))
            else:
                con.execute('INSERT INTO companion_meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                            ('hold:'+row['id'], status))
            if status in {'sleeping', 'dropped'}:
                con.execute("DELETE FROM interaction_waits WHERE conversation_key='local' AND goal=?", (row['title'],))
            if affects_current or status == 'open':
                own.update(goal=row['title'], next_step=row['next_step'] if status == 'open' else '',
                    status='planned' if status == 'open' else 'blocked', resume_at='',
                    resume_reason='你将这件事设为'+PLAN_NAMES[status], plan_revision=uuid.uuid4().hex)
                con.execute('INSERT INTO agency_state VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (json.dumps(own, ensure_ascii=False),))
        add_event(self.db, 'plan-edit:'+uuid.uuid4().hex, 'note', {'title': '你调整了打算：'+row['title'],
            'reflection': '改为'+PLAN_NAMES[status], 'origin': 'user', 'note': '用户对打算的选择；不代表实际完成。'})
        self.controller._schedule_next()
        self.controller.wake_for_experience()
        self.feedback.setText('已设为'+PLAN_NAMES[status]+'。')
        self.refresh()

    def refresh_journal(self):
        with closing(self.db._connect()) as con:
            decisions = [dict(row) for row in con.execute('SELECT * FROM companion_decisions ORDER BY created_at DESC,rowid DESC LIMIT 60')]
            activities = [dict(row) for row in con.execute('SELECT * FROM agency_journal ORDER BY started_at DESC LIMIT 60')]
        records = []
        for row in decisions:
            value = json.loads(row['payload'])
            records.append((row['created_at'], '选择 · '+{'act': '做事', 'talk': '想聊聊', 'rest': '休息'}.get(value.get('choice'), ''),
                str(value.get('reason', ''))+'\n打算：'+str(value.get('goal') or '暂时不行动')+
                '\n想何时再继续：'+str(value.get('revisit_minutes', ''))+' 分钟后'))
        for row in activities:
            lines = [row['intent'], row['summary']]
            lines.extend(receipt_text(r) for r in json.loads(row['receipts'] or '[]'))
            records.append((row['started_at'], '行动 · '+ACTIVITY_NAMES.get(row['status'], row['status']), '\n'.join(lines)))
        parts = ['<h3>最近的选择与实际行动</h3>']
        for when, title, content in sorted(records, key=lambda r: r[0], reverse=True):
            parts.append('<p style="color:#5370A2">'+escape(date_text(when)+'  '+title)+'</p><p style="line-height:155%">'+escape(content).replace('\n', '<br>')+'</p><hr>')
        rendered = ''.join(parts) if records else '<p>还没有记录。开启心跳后，会在这里留下真实的选择与行动。</p>'
        if self.journal.property('rendered') != rendered:
            scroll = self.journal.verticalScrollBar().value()
            self.journal.setHtml(rendered)
            self.journal.setProperty('rendered', rendered)
            self.journal.verticalScrollBar().setValue(scroll)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def reset_data_view(self):
        self._loading = True
        self.thought.clear()
        self._thought_dirty = False
        self.material_rows, self.plan_rows = {}, {}
        self._material_signature = self._plan_signature = None
        self.material_list.clear()
        self.plan_list.clear()
        self.journal.clear()
        self.journal.setProperty('rendered', None)
        self.feedback.clear()
        self._loading = False
