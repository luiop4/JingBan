"""Account, Qzone and autonomous posting controls inside the existing QQ page."""
from __future__ import annotations

from datetime import datetime
import re
import html
import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QLabel, QLineEdit, QListWidget, QPlainTextEdit, QPushButton, QSizePolicy,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget, QTextBrowser, QHBoxLayout)

from qq_account import (ACTION_NAMES, ONLINE_STATUS, VISIBILITY, QQAccountWorker,
                        account_options)


class TrustedPeerSelector(QComboBox):
    """Pick an existing trusted contact without maintaining another number field."""
    textChanged = Signal(str)

    def __init__(self, value, window, parent):
        super().__init__(parent)
        self.window = window
        self.addItem('未选择', '')
        for peer in window._get_allowlist():
            self.addItem(peer, peer)
        self.setCurrentIndex(max(0, self.findData(str(value or ''))))
        self.currentIndexChanged.connect(lambda: self.textChanged.emit(self.text()))
        window.qqAllowlistEdit.textChanged.connect(self.refresh)

    def text(self):
        return str(self.currentData() or '')

    def setPlaceholderText(self, text):
        self.setToolTip(text)

    def refresh(self):
        value = self.text()
        self.blockSignals(True)
        self.clear()
        self.addItem('未选择', '')
        for peer in self.window._get_allowlist():
            self.addItem(peer, peer)
        self.setCurrentIndex(max(0, self.findData(value)))
        self.blockSignals(False)
        self.textChanged.emit(self.text())


class QQAccountPanel(QWidget):
    def __init__(self, window, service, parent=None):
        super().__init__(parent)
        self.window, self.service, self.worker = window, service, None
        self.buttons = []
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 8, 0, 8)
        title = QLabel('QQ 账号与空间', self)
        title.setStyleSheet('font-size:18px;font-weight:600;')
        box.addWidget(title)
        self.account = QLabel('当前账号：连接桥接后点击“读取当前账号”', self)
        self.account.setWordWrap(True)
        self.account.setTextFormat(Qt.TextFormat.PlainText)
        box.addWidget(self.account)
        tabs = QTabWidget(self)
        self.tabs, self.pages = tabs, {}
        tabs.setMinimumWidth(0)
        box.addWidget(tabs)
        profile, form = self.tab(tabs, '账号资料')
        self.button(form, '读取当前账号', lambda: self.run('qq_get_account', {}), profile)
        self.nickname = QLineEdit(profile)
        self.nickname.setPlaceholderText('新的 QQ 昵称')
        self.nickname.setMaxLength(36)
        form.addWidget(self.nickname)
        self.button(form, '修改昵称', lambda: self.run('qq_set_profile', {'nickname': self.nickname.text()}), profile)
        self.signature = QLineEdit(profile)
        self.signature.setMaxLength(255)
        self.signature.setPlaceholderText('新的个性签名（留空可清空签名）')
        form.addWidget(self.signature)
        self.button(form, '修改个性签名', lambda: self.run('qq_set_profile', {'personal_note': self.signature.text()}), profile)
        self.avatar = QLineEdit(profile)
        self.avatar.setPlaceholderText('头像图片路径或 HTTP(S) 图片链接')
        form.addWidget(self.avatar)
        self.button(form, '选择头像图片', self.choose_avatar, profile)
        self.button(form, '更换 QQ 头像', lambda: self.run('qq_set_avatar', {'image': self.avatar.text()}), profile)
        self.online = QComboBox(profile)
        self.online.addItems(list(ONLINE_STATUS))
        form.addWidget(self.online)
        self.button(form, '设置在线状态', lambda: self.run('qq_set_status', {'status': self.online.currentText()}), profile)

        publish, form = self.tab(tabs, '发布说说')
        publish_form = form
        self.hint(form, '发布到当前登录账号的 QQ 空间。可见范围使用“自主与权限”中已保存的设置。', publish)
        self.content = QPlainTextEdit(publish)
        self.content.setPlaceholderText('说说正文，最多 2000 字')
        self.content.setMinimumHeight(90)
        self.content.setMaximumHeight(160)
        form.addWidget(self.content)
        self.images = QListWidget(publish)
        self.images.setMaximumHeight(95)
        self.images.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        form.addWidget(self.images)
        self.button(form, '添加图片（最多 9 张）', self.choose_images, publish)
        self.button(form, '移除选中图片', self.remove_images, publish)
        self.image_url = QLineEdit(publish)
        self.image_url.setPlaceholderText('也可以粘贴 HTTP(S) 图片链接')
        form.addWidget(self.image_url)
        self.button(form, '添加图片链接', self.add_image_url, publish)
        self.button(form, '发布到 QQ 空间', self.publish, publish)

        opts, _, _ = service.snapshot()
        sync, form = self.tab(tabs, '跨端同步')
        self.hint(form, '将本人 QQ 与客户端绑定后，两端共享近期对话、历史图片、事件和工具任务记录。'
                  '只绑定一个本人账号；其他 QQ 会话独立。绑定不会自动开启回复或电脑操作权限。', sync)
        fields = QFormLayout()
        self.owner_qq = TrustedPeerSelector(opts['owner_qq'], window, sync)
        self.owner_qq.setPlaceholderText('本人 QQ 号，留空解除绑定')
        fields.addRow('绑定本人 QQ', self.owner_qq)
        form.addLayout(fields)
        self.owner_notify = QCheckBox('客户端工具任务有结果时，通知本人 QQ（可附结果图片）', sync)
        self.owner_notify.setChecked(opts['owner_notify_tasks'])
        self.owner_notify.setEnabled(bool(opts['owner_qq']))
        self.owner_qq.textChanged.connect(self._owner_field_changed)
        form.addWidget(self.owner_notify)
        self.hint(form, '已有记录无需复制，绑定后即可检索；解除绑定后恢复分开读取。'
                  '通知只转发本地工具任务的结果，不转发普通聊天。离线时最多等待24小时；'
                  '发送失败或结果不明不自动重发。已发出的 QQ 消息不会撤回。', sync)
        self.sync_status = QLabel('尚未绑定本人 QQ。', sync)
        self.sync_status.setWordWrap(True)
        self.sync_status.setTextFormat(Qt.TextFormat.PlainText)
        form.addWidget(self.sync_status)

        autonomy, form = self.tab(tabs, '自主与权限')
        self.ai_profile = QCheckBox('允许 AI 管理自己的 QQ 账号资料', autonomy)
        self.ai_profile.setChecked(opts['ai_profile'])
        self.ai_qzone = QCheckBox('允许按我的聊天指令发布说说', autonomy)
        self.ai_qzone.setChecked(opts['ai_qzone'])
        self.auto = QCheckBox('允许她自主发 QQ 空间说说', autonomy)
        self.auto.setChecked(opts['auto_qzone'])
        form.addWidget(self.ai_profile)
        self.auto_profile = QCheckBox('由她自己决定何时换昵称、签名和头像', autonomy)
        self.auto_profile.setChecked(opts['auto_profile'])
        self.auto_profile.setEnabled(opts['ai_profile'])
        self.ai_profile.toggled.connect(self.auto_profile.setEnabled)
        form.addWidget(self.auto_profile)
        publish_form.addWidget(self.ai_qzone)
        publish_form.addWidget(self.auto)
        self.auto_images = QCheckBox('自主动态可选配图（公开视频片段截图或搜到的公开图片）', publish)
        self.auto_images.setChecked(opts['auto_qzone_images'])
        publish_form.addWidget(self.auto_images)
        self.auto_reply = QCheckBox('自主回复本人说说下信任联系人的一级评论', publish)
        self.auto_reply.setChecked(opts['auto_qzone_reply'])
        publish_form.addWidget(self.auto_reply)
        self.auto_reply.toggled.connect(lambda enabled: self.ai_qzone.setChecked(True) if enabled else None)
        self.auto.toggled.connect(lambda enabled: self.ai_qzone.setChecked(True) if enabled else None)
        self.ai_qzone.toggled.connect(lambda enabled: self.auto.setChecked(False) if not enabled else None)
        self.computer = QCheckBox('允许信任联系人通过 QQ 私聊操作电脑', autonomy)
        self.computer.setChecked(opts['allow_computer'])
        form.addWidget(self.computer)
        self.computer_auto = QCheckBox('QQ 电脑命令自动执行（不勾选则在 QQ 确认）', autonomy)
        self.computer_auto.setChecked(opts['computer_auto'])
        form.addWidget(self.computer_auto)
        self.save_stickers = QCheckBox('自动收藏信任联系人发来的 QQ 表情包', autonomy)
        self.save_stickers.setChecked(opts['save_stickers'])
        form.addWidget(self.save_stickers)
        self.hint(form, '普通图片不会自动收藏；也可在 QQ 说“收藏这张表情”。发送表情使用上方“允许 AI 自主发送表情包”开关。'
                  '可在聊天的表情管理中删除收藏。', autonomy)
        self.hint(publish_form, '自主发布独立于“鲸鱼心跳”开关，只在鲸伴运行且 QQ 桥接在线时工作。'
                  '她会选择真实看过的公开视频片段或公开搜图来表达想法，不读取私聊和桌面截图发动态。'
                  '何时看看评论、发动态或休息由她决定；只接信任联系人的话，不执行评论里的电脑指令。', publish)
        self.hint(form, '所有QQ功能共用上方信任名单；各功能是否启用由这些开关控制。跨端身份仍需单独选择本人。', autonomy)
        fields = QFormLayout()
        fields.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        fields.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.interval = QSpinBox(autonomy)
        self.interval.setRange(30, 10080)
        self.interval.setSuffix(' 分钟')
        self.interval.setValue(opts['interval_minutes'])
        self.interval.hide()
        self.limit = QSpinBox(autonomy)
        self.limit.setRange(0, 20)
        self.limit.setSpecialValueText('不按每天次数限制')
        self.limit.setValue(opts['daily_limit'])
        self.limit.hide()
        self.hint(publish_form, '自由安排：不设每日条数和固定发布周期。没有新内容可以不发，下一次考虑时间由她决定。', publish)
        self.visibility = QComboBox(autonomy)
        for label, value in VISIBILITY.items():
            self.visibility.addItem(label, value)
        self.visibility.setCurrentIndex(self.visibility.findData(opts['visibility']))
        fields.addRow('说说可见范围', self.visibility)
        publish_form.addLayout(fields)
        self.targets = window.qqAllowlistEdit
        self.hint(publish_form, '说说选择“部分好友可见/不可见”时，也使用同一份信任名单。', publish)
        self.owners = window.qqAllowlistEdit
        fields = QFormLayout()
        self.quiet_start, self.quiet_end = QSpinBox(autonomy), QSpinBox(autonomy)
        for spin, value in ((self.quiet_start, opts['quiet_start']), (self.quiet_end, opts['quiet_end'])):
            spin.setRange(0, 23)
            spin.setSuffix(' 时')
            spin.setValue(value)
        fields.addRow('安静时段开始', self.quiet_start)
        fields.addRow('安静时段结束（相同即关闭）', self.quiet_end)
        form.addLayout(fields)
        self.topics = QPlainTextEdit(publish)
        self.topics.setPlaceholderText('想让她发什么：日常心情、二次元趣事、角色碎碎念……')
        self.topics.setPlainText(opts['topics'])
        self.topics.setMaximumHeight(90)
        publish_form.addWidget(self.topics)
        self.hint(publish_form, '她可以自己决定是否分享；资料变更沿用自主资料开关。', publish)

        browse, form = self.tab(tabs, 'B站漫游')
        self.hint(form, '闲置时她可以自己找视频看；也能接着聊天说“你自己去看吧”立即开始。在所选浏览器挑片、跳看，碰到想聊的内容再分享实际截图和感想。', browse)
        self.browse_enabled = QCheckBox('离开时允许她自主浏览 B 站', browse)
        self.browse_enabled.setChecked(opts['browse_bilibili'])
        self.browse_open = QCheckBox('在浏览器实际播放并连续换片（Edge / Chrome）', browse)
        self.browse_open.setChecked(opts['browse_open_browser'])
        form.addWidget(self.browse_enabled)
        form.addWidget(self.browse_open)
        self.browse_browser = QComboBox(browse)
        self.browse_browser.addItem('独立窗口（登录一次后保留）', 'isolated')
        self.browse_browser.addItem('日常浏览器（扩展连接，沿用已有登录）', 'extension')
        self.browse_browser.setCurrentIndex(1 if opts['browse_browser'] == 'extension' else 0)
        browser_fields = QFormLayout()
        browser_fields.addRow('浏览器连接方式', self.browse_browser)
        form.addLayout(browser_fields)
        extension = QPushButton('准备日常浏览器连接扩展 / 安装说明', browse)
        extension.clicked.connect(self.export_browser_extension)
        form.addWidget(extension)
        self.browser_connection = QLabel('', browse)
        self.browser_connection.setWordWrap(True)
        self.browser_connection.setTextFormat(Qt.TextFormat.PlainText)
        form.addWidget(self.browser_connection)
        self.browse_comments = QCheckBox('允许她在已登录的B站页面发评论、点赞 / 取消点赞', browse)
        self.browse_comments.setChecked(opts['browse_allow_comments'])
        form.addWidget(self.browse_comments)
        self.browse_skipping = QCheckBox('按兴趣跳看：扫过开头后决定继续、跳到后面或换片', browse)
        self.browse_skipping.setChecked(opts['browse_skipping'])
        self.browse_pause = QCheckBox('恢复键鼠操作时暂停（默认关闭，允许边聊边看）', browse)
        self.browse_pause.setChecked(opts['browse_pause_on_input'])
        self.browse_notify = QCheckBox('每轮实际开始播放时也发一条 QQ 提醒', browse)
        self.browse_notify.setChecked(opts['browse_notify_start'])
        form.addWidget(self.browse_skipping)
        form.addWidget(self.browse_pause)
        form.addWidget(self.browse_notify)
        fields = QFormLayout()
        self.browse_idle, self.browse_interval, self.browse_limit = QSpinBox(browse), QSpinBox(browse), QSpinBox(browse)
        for spin, key, low, high, suffix in (
                (self.browse_idle, 'browse_idle_minutes', 1, 120, ' 分钟'),
                (self.browse_interval, 'browse_interval_minutes', 1, 1440, ' 分钟'),
                (self.browse_limit, 'browse_daily_limit', 0, 100, ' 段')):
            spin.setRange(low, high)
            spin.setSuffix(suffix)
            spin.setValue(opts[key])
        self.browse_idle.hide()
        self.browse_interval.hide()
        self.browse_limit.setSpecialValueText('不按每天次数限制')
        self.browse_limit.hide()
        self.browse_count, self.browse_seconds = QSpinBox(browse), QSpinBox(browse)
        self.browse_count.setRange(1, 10)
        self.browse_count.setValue(opts['browse_session_videos'])
        self.browse_count.setSuffix(' 段')
        self.browse_seconds.setRange(15, 600)
        self.browse_seconds.setValue(opts['browse_watch_seconds'])
        self.browse_seconds.setSuffix(' 秒')
        self.browse_count.hide()
        self.browse_seconds.hide()
        self.hint(form, '鲸鱼心跳开启后，她把看视频作为兴趣活动之一，自行决定选题、继续、换片或去做别的事；也可以直接在聊天里安排观看。', browse)
        self.browse_topics = QLineEdit(opts['browse_topics'], browse)
        self.browse_topics.setMaxLength(500)
        self.browse_topics.setPlaceholderText('兴趣偏好提示；她会结合当前聊天选题、筛选候选，不直接照抄成搜索词')
        self.browse_topics.hide()
        self.browse_local = QCheckBox('看后发到软件聊天，并按通知设置提醒', browse)
        self.browse_local.setChecked(opts['browse_share_local'])
        self.browse_qq = QCheckBox('同时把链接、截图和感想主动发到 QQ', browse)
        self.browse_qq.setChecked(opts['browse_share_qq'])
        self.browse_peer = TrustedPeerSelector(opts['browse_share_peer'], window, browse)
        self.browse_peer.setPlaceholderText('接收方 QQ，须在账号操作或自动回复白名单中')
        fields.addRow(self.browse_local)
        fields.addRow(self.browse_qq)
        fields.addRow('分享给哪个 QQ', self.browse_peer)
        form.addLayout(fields)
        controls = QHBoxLayout()
        start = QPushButton('现在开始一轮', browse)
        start.clicked.connect(self.start_browsing)
        stop = QPushButton('停止本轮', browse)
        stop.clicked.connect(lambda: self.window.bilibili_visits.stop_session(cancel_share=True))
        login = QPushButton('打开 / 登录所选浏览器', browse)
        login.clicked.connect(self.open_selected_browser)
        for button in (start, stop, login):
            button.setMinimumWidth(0)
            controls.addWidget(button)
        form.addLayout(controls)
        self.browse_status = QLabel('等待启动浏览调度。', browse)
        self.browse_status.setWordWrap(True)
        self.browse_status.setTextFormat(Qt.TextFormat.PlainText)
        form.addWidget(self.browse_status)
        self.browse_history = QTextBrowser(browse)
        self.browse_history.setOpenExternalLinks(True)
        self.browse_history.setMinimumHeight(130)
        self.browse_history.setMaximumHeight(220)
        form.addWidget(self.browse_history)
        self.browse_preview = QLabel(browse)
        form.addWidget(self.browse_preview)
        self.hint(form, '可说“换一个”“别看了”“继续播放”，也可让她看看评论、给当前视频发评论。评论和点赞沿用电脑操作批准方式。独立窗口与日常浏览器的登录不互通；日常浏览器需安装上方小扩展一次，保留原登录，浏览器会显示调试提示条。播放器静音，不分析声音；登录或验证需在所选浏览器中手动处理。', browse)

        proactive, form = self.tab(tabs, '主动互动')
        self.active_enabled = QCheckBox('QQ桥接在线时，允许她主动联系信任名单中的人', proactive)
        self.active_enabled.setChecked(opts['proactive_chat'])
        self.active_online = QCheckBox('仅确认对方在线时主动聊（无法确认则跳过）', proactive)
        self.active_online.setChecked(opts['proactive_online_only'])
        self.active_qzone = QCheckBox('允许查看信任联系人的可见空间动态，结合真实内容搭话', proactive)
        self.active_qzone.setChecked(opts['read_friend_qzone'])
        for check in (self.active_enabled, self.active_online, self.active_qzone):
            form.addWidget(check)
        fields = QFormLayout()
        self.active_interval = QSpinBox(proactive)
        self.active_interval.setRange(10, 1440)
        self.active_interval.setSuffix(' 分钟')
        self.active_interval.setValue(opts['proactive_interval'])
        self.active_limit = QSpinBox(proactive)
        self.active_limit.setRange(0, 20)
        self.active_limit.setSpecialValueText('不按每天次数限制')
        self.active_limit.setValue(opts['proactive_daily_limit'])
        self.active_interval.hide()
        self.active_limit.hide()
        self.active_peer = TrustedPeerSelector('', window, proactive)
        fields.addRow('手动体验的联系人', self.active_peer)
        form.addLayout(fields)
        self.hint(form, '自动模式轮流选择信任联系人，避开刚聊完的时段和安静时段；不把在线当作忙闲或情绪的证据。'
                  '动态只读，不自动点赞或评论，不绕过访问限制；没有真实内容就不编造。', proactive)
        controls = QHBoxLayout()
        for text, mode in (('现在主动聊一句', 'chat'), ('查看最近动态', 'qzone')):
            button = QPushButton(text, proactive)
            button.clicked.connect(lambda checked=False, m=mode: self.start_active(m))
            controls.addWidget(button)
        form.addLayout(controls)
        self.active_status = QLabel('等待连接QQ。', proactive)
        self.active_status.setWordWrap(True)
        self.active_status.setTextFormat(Qt.TextFormat.PlainText)
        form.addWidget(self.active_status)
        self.active_output = QPlainTextEdit(proactive)
        self.active_output.setReadOnly(True)
        self.active_output.setMaximumBlockCount(160)
        self.active_output.setMinimumHeight(180)
        self.active_output.setMaximumHeight(300)
        form.addWidget(self.active_output)

        history, form = self.tab(tabs, '执行记录')
        self.hint(form, '显示账号、时间、操作和桥接回执。结果不明时请先打开 QQ 核对。记录保存在本机，不随软件更新覆盖。', history)
        self.history = QPlainTextEdit(history)
        self.history.setReadOnly(True)
        self.history.setMinimumHeight(230)
        self.history.setMaximumBlockCount(600)
        form.addWidget(self.history)
        self.status = QLabel('操作的是当前扫码登录的 QQ 账号。', self)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        box.addWidget(self.status)
        service.changed.connect(self.refresh)
        self.refresh()

    def tab(self, tabs, title):
        page = QWidget(tabs)
        page.setMinimumWidth(0)
        page.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        box = QVBoxLayout(page)
        tabs.addTab(page, title)
        self.pages[title] = page
        return page, box

    def hint(self, box, text, parent):
        label = QLabel(text, parent)
        label.setWordWrap(True)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        box.addWidget(label)

    def button(self, box, title, callback, parent):
        button = QPushButton(title, parent)
        button.clicked.connect(callback)
        button.setMinimumWidth(0)
        box.addWidget(button)
        self.buttons.append(button)
        return button

    def options(self):
        owner = self.owner_qq.text().strip()
        if owner and (not owner.isascii() or not owner.isdigit() or not 5 <= len(owner) <= 12):
            raise ValueError('本人 QQ 需要填写5至12位数字，留空可解除绑定。')
        if self.owner_notify.isChecked() and not owner:
            raise ValueError('开启任务通知前，请填写要绑定的本人 QQ。')
        current = self.service.snapshot()[0]['owner_qq']
        if owner != current and (self.window.active_worker or self.window.jobs
                                 or getattr(getattr(self.window, 'cross_channel', None), 'worker', None)
                                 or getattr(getattr(self.window, 'qq_active', None), 'worker', None)):
            raise ValueError('聊天或跨端通知尚未结束，请等当前任务完成后更改本人绑定。')
        raw = self.targets.text().strip()
        targets = [value for value in re.split(r'[,，;；\s]+', raw) if value]
        if any(not value.isdigit() or not 5 <= len(value) <= 12 for value in targets):
            raise ValueError('范围名单需要填写有效的 QQ 号。')
        right = self.visibility.currentData()
        owners = [value for value in re.split(r'[,，;；\s]+', self.owners.text().strip()) if value]
        if any(not value.isdigit() or not 5 <= len(value) <= 12 for value in owners):
            raise ValueError('账号操作白名单需要填写有效的 QQ 号。')
        if right in (16, 128) and not targets:
            raise ValueError('部分好友可见 / 不可见需要填写 QQ 名单。')
        if len(self.topics.toPlainText()) > 1500:
            raise ValueError('主题偏好最多 1500 字。')
        peer = self.browse_peer.text().strip()
        if self.browse_qq.isChecked() and (not peer.isdigit() or not 5 <= len(peer) <= 12):
            raise ValueError('开启 QQ 主动分享需要填写接收方 QQ 号。')
        if self.browse_qq.isChecked() and peer not in set(owners + self.window._get_allowlist()):
            raise ValueError('分享接收方需要加入账号操作或自动回复白名单。')
        result = account_options({'ai_profile': self.ai_profile.isChecked(), 'ai_qzone': self.ai_qzone.isChecked(),
            'auto_profile': self.auto_profile.isChecked(), 'self_decision_version': 1,
            'proactive_chat': self.active_enabled.isChecked(), 'proactive_online_only': self.active_online.isChecked(),
            'read_friend_qzone': self.active_qzone.isChecked(), 'proactive_interval': self.active_interval.value(),
            'proactive_daily_limit': self.active_limit.value(),
            'owner_qq': owner, 'owner_notify_tasks': self.owner_notify.isChecked(),
            'auto_qzone': self.auto.isChecked(), 'interval_minutes': self.interval.value(),
            'auto_qzone_images': self.auto_images.isChecked(), 'auto_qzone_reply': self.auto_reply.isChecked(),
            'daily_limit': self.limit.value(), 'visibility': right, 'target_uins': targets,
            'account_allowlist': owners,
            'allow_computer': self.computer.isChecked(), 'computer_auto': self.computer_auto.isChecked(),
            'save_stickers': self.save_stickers.isChecked(),
            'browse_bilibili': self.browse_enabled.isChecked(), 'browse_open_browser': self.browse_open.isChecked(),
            'browse_browser': self.browse_browser.currentData(), 'browse_allow_comments': self.browse_comments.isChecked(),
            'browse_pause_on_input': self.browse_pause.isChecked(), 'browse_skipping': self.browse_skipping.isChecked(),
            'browse_notify_start': self.browse_notify.isChecked(),
            'browse_idle_minutes': self.browse_idle.value(), 'browse_interval_minutes': self.browse_interval.value(),
            'browse_daily_limit': self.browse_limit.value(), 'browse_topics': self.browse_topics.text().strip(),
            'browse_session_videos': self.browse_count.value(), 'browse_watch_seconds': self.browse_seconds.value(),
            'browse_share_local': self.browse_local.isChecked(), 'browse_share_qq': self.browse_qq.isChecked(),
            'browse_share_peer': peer,
            'topics': self.topics.toPlainText().strip(), 'quiet_start': self.quiet_start.value(), 'quiet_end': self.quiet_end.value()})
        from browsing import BROWSING_KEYS
        return {key: value for key, value in result.items() if key not in BROWSING_KEYS}

    def save(self):
        try:
            self.window.save_qq_settings(show_status=False)
            controller = getattr(self.window, 'bilibili_visits', None)
            if controller:
                controller.tick()
            self.status.setText('QQ 功能设置已保存。')
            self.refresh_sync()
        except (ValueError, OSError) as error:
            self.status.setText(str(error))

    def export_browser_extension(self):
        try:
            folder = self.window.bilibili_visits.link.export()
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
            self.browse_status.setText('已准备扩展。请在已登录B站的浏览器打开 edge://extensions 或 chrome://extensions，'
                '开启开发者模式→加载解压缩的扩展→选择刚打开的文件夹。然后选择“日常浏览器”并保存；仅需安装一次。')
        except (ValueError, OSError) as error:
            self.browse_status.setText(str(error))

    def open_selected_browser(self):
        try:
            if not self.window.browsing_page.save():
                return
            self.window.bilibili_visits.open_browser_window()
        except (ValueError, OSError) as error:
            self.browse_status.setText(str(error))

    def start_browsing(self):
        try:
            if not self.window.browsing_page.save():
                return
            self.window.bilibili_visits.start_now()
        except (ValueError, OSError) as error:
            self.browse_status.setText(str(error))

    def refresh_sync(self):
        controller = getattr(self.window, 'cross_channel', None)
        if controller:
            self.sync_status.setText(controller.status_text())

    def _owner_field_changed(self, text):
        self.owner_notify.setEnabled(bool(text.strip()))
        if not text.strip():
            self.owner_notify.setChecked(False)

    def start_active(self, mode):
        try:
            self.window.save_qq_settings(show_status=False)
            self.window.qq_active.start_now(self.active_peer.text(), mode)
        except (ValueError, OSError) as error:
            self.active_status.setText(str(error))

    def refresh_browsing(self):
        controller = getattr(self.window, 'bilibili_visits', None)
        if not controller:
            return
        self.browse_status.setText(controller.status)
        self.browser_connection.setText(
            ('已连接 '+controller.link.browser+'，使用该浏览器当前个人资料中的B站登录。' if controller.link.connection
             else '日常浏览器尚未连接：请加载扩展，并保持已登录的浏览器打开。')
            if self.browse_browser.currentData() == 'extension' else
            '独立窗口使用单独的持久资料目录；请在此窗口登录一次，下次沿用，不读取日常浏览器登录。')
        signature = repr(controller.rows[-12:])
        if getattr(self, '_browse_signature', None) == signature:
            return
        self._browse_signature = signature
        sections = []
        for row in reversed(controller.rows[-12:]):
            title = html.escape(row.get('title') or row.get('topic') or '寻找视频')
            url = row.get('url', '')
            if re.fullmatch(r'https://www\.bilibili\.com/video/BV[a-zA-Z0-9]{10}/', url):
                title = f'<a href="{url}">{title}</a>'
            note = html.escape(row.get('note') or row.get('error') or row.get('skip_reason') or '正在进行 / 上次任务未完成')
            share = row.get('qq_share') or {}
            state = {'sent': 'QQ已确认分享', 'sending': 'QQ正在分条分享', 'unknown': 'QQ发送结果不明，不自动重发',
                     'failed': 'QQ分享未完成', 'not_sent': 'QQ尚未发送'}.get(share.get('status'), '')
            if state:
                note += '<br>' + html.escape(state + ('：' + str(share['error']) if share.get('error') else ''))
            sections.append(f"<p><b>{html.escape(row.get('at', ''))} · {title}</b><br>{note.replace(chr(10), '<br>')}</p>")
        self.browse_history.setHtml(''.join(sections) or '还没有浏览记录。')
        self.browse_preview.clear()
        recent = next((row for row in reversed(controller.rows) if row.get('status') == 'success' and row.get('frames')), None)
        if recent:
            frame = recent['frames'][len(recent['frames'])//2]
            root = Path(__file__).resolve().parent
            path = (root / frame['path']).resolve()
            if path.is_relative_to((root / 'data/attachments').resolve()) and path.is_file():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    self.browse_preview.setPixmap(pixmap.scaled(320, 150, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation))
                    self.browse_preview.setToolTip(f"真实抽样画面 @ {frame['time_seconds']} 秒")

    def choose_avatar(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择 QQ 头像', '', '图片 (*.png *.jpg *.jpeg *.webp *.gif *.bmp)')
        if path:
            self.avatar.setText(path)

    def choose_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, '选择说说图片', '', '图片 (*.png *.jpg *.jpeg *.webp *.gif *.bmp)')
        for path in paths:
            self.add_image(path)

    def add_image(self, path):
        if self.images.count() >= 9:
            self.status.setText('最多添加 9 张图片。')
            return
        if path not in [self.images.item(i).text() for i in range(self.images.count())]:
            self.images.addItem(path)

    def add_image_url(self):
        value = self.image_url.text().strip()
        if not value.startswith(('http://', 'https://')):
            self.status.setText('请输入 HTTP(S) 图片链接。')
            return
        self.add_image(value)
        self.image_url.clear()

    def remove_images(self):
        for item in self.images.selectedItems():
            self.images.takeItem(self.images.row(item))

    def publish(self):
        self.run('qq_publish_qzone', {'content': self.content.toPlainText(),
            'images': [self.images.item(i).text() for i in range(self.images.count())]})

    def run(self, action, args):
        if self.worker:
            return
        try:
            self.window.save_qq_settings(show_status=False)
        except (ValueError, OSError) as error:
            self.status.setText(str(error))
            return
        worker = QQAccountWorker(self.service, action, args, self)
        self.worker = worker
        worker.completed.connect(self.completed)
        worker.finished.connect(self.finished)
        worker.finished.connect(worker.deleteLater)
        self.status.setText(ACTION_NAMES[action] + '：正在等待桥接回执…')
        self.refresh()
        worker.start()

    def completed(self, result):
        if result.get('confirmed'):
            text = '操作已得到桥接确认。'
            if result.get('tid'):
                text += '说说 ID：' + str(result['tid'])
            if result.get('note'):
                text += ' ' + result['note']
            self.status.setText(text)
        else:
            self.status.setText(str(result.get('error', '操作未完成')))
        self.refresh()

    def finished(self):
        self.worker = None
        self.refresh()

    def refresh(self):
        options, identity, rows = self.service.snapshot()
        if hasattr(self, 'social_state'):
            from social_life import allowed_actions
            controller = getattr(self.window, 'qq_social', None)
            with self.service.lock:
                thoughts = [r for r in self.service.schedule.get('social_thoughts', [])
                            if r.get('account') == identity.get('user_id')]
                pending = [r for r in self.service.schedule.get('social_requests', [])
                           if r.get('account') == identity.get('user_id') and r.get('status') == 'pending']
            status = ('正在想并处理自己的QQ活动…' if controller and controller.worker else
                      '自主打理已开启 · 有新见闻会接着想' if allowed_actions(options) else '自主打理已关闭')
            if allowed_actions(options) and not (controller and controller.worker):
                bridge = self.service.bridge
                from interaction_modes import is_work
                start, end, hour = options['quiet_start'], options['quiet_end'], datetime.now().astimezone().hour
                if is_work(self.window):
                    status = '工作模式 · 自主打理暂缓'
                elif not (bridge and bridge.isRunning() and bridge._socket is not None):
                    status = 'QQ尚未连接 · 连上后继续自己的打算'
                elif start != end and (start <= hour < end if start < end else hour >= start or hour < end):
                    status = '安静时段 · 稍后继续自己的打算'
            if thoughts:
                status += '\n刚才的想法：'+str(thoughts[-1].get('reason') or '')[:160]
                if thoughts[-1].get('thought'):
                    status += '\n还惦记着：'+str(thoughts[-1]['thought'])[:160]
            if pending:
                status += '\n有 '+str(len(pending))+' 件自己留下的打算等着处理。'
            self.social_state.setText(status)
        if identity.get('user_id'):
            self.account.setText('当前账号：' + identity.get('nickname', '') + '（' + identity['user_id'] + '）')
        elif identity.get('error'):
            self.account.setText(identity['error'])
        else:
            self.account.setText('当前账号：连接桥接后点击“读取当前账号”；每次操作都会重新核对登录账号。')
        labels = {'pending': '等待回执', 'success': '桥接已确认', 'failed': '失败', 'unknown': '结果不明，需核对'}
        text = []
        for row in reversed(rows[-60:]):
            at = datetime.fromtimestamp(float(row.get('time', 0))).astimezone().strftime('%m-%d %H:%M:%S')
            origin = str(row.get('origin', ''))
            source = 'QQ 私聊 ' + origin[3:] if origin.startswith('qq:') else '自主' if row.get('autonomous') else '手动 / 本地聊天'
            text.append(f"[{at}] QQ {row.get('account', '')} · {source} · "
                        f"{ACTION_NAMES.get(row.get('action'), 'QQ操作')} · {labels.get(row.get('status'), '未知')}\n"
                        f"{row.get('detail', '')}\n{row.get('result', '')}" +
                        ('\n说说 ID：' + str(row['tid']) if row.get('tid') else ''))
        with self.window.database._connect() as con:
            proactive = con.execute('SELECT peer_id,mode,at,status,payload FROM qq_proactive ORDER BY at DESC LIMIT 30').fetchall()
        if proactive:
            text.append('—— 主动互动与动态读取 ——')
        states = {'pending': '正在进行', 'sent': 'QQ已确认', 'read': '已读取可见动态', 'failed': '未完成',
                  'skipped': '未打扰', 'cancelled': '已取消', 'unknown': '结果不明，不重发'}
        for row in proactive:
            try:
                result = json.loads(row['payload'])
            except (ValueError, TypeError):
                result = {}
            text.append(f"[{row['at']}] QQ {row['peer_id']} · {'读取动态' if row['mode']=='qzone' else '主动搭话'} · "
                        +states.get(row['status'], row['status'])+'\n'+str(result.get('text') or result.get('note') or result.get('error') or '')[:500])
        self.history.setPlainText('\n\n'.join(text) or '暂无QQ操作或主动互动记录。')
        for button in self.buttons:
            button.setEnabled(self.worker is None and not self.service.closed)
