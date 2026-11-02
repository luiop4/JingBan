"""Global browsing preferences and a page independent of the QQ integration."""
DEFAULT_BROWSING = {
    'defaults_version': 2, 'browse_bilibili': True, 'browse_open_browser': True,
    'browse_allow_comments': True, 'browse_browser': 'extension',
    'browse_topics': '', 'browse_skipping': True, 'browse_pause_on_input': False,
    'browse_session_videos': 3, 'browse_watch_seconds': 120,
    'browse_idle_minutes': 5, 'browse_interval_minutes': 30, 'browse_daily_limit': 0,
    'browse_share_local': True,
}
BROWSING_KEYS = frozenset(DEFAULT_BROWSING)-{'defaults_version'}


def normalize(value):
    result = {**DEFAULT_BROWSING, **(value if isinstance(value, dict) else {})}
    for key in ('browse_bilibili', 'browse_open_browser', 'browse_allow_comments', 'browse_skipping',
                'browse_pause_on_input', 'browse_share_local'):
        result[key] = result[key] is True
    result['browse_browser'] = 'extension' if result.get('browse_browser') == 'extension' else 'isolated'
    result['browse_topics'] = ''  # Legacy field; selections now come from her own state.
    for key, low, high in (('browse_session_videos', 1, 10), ('browse_watch_seconds', 15, 600)):
        try:
            result[key] = max(low, min(high, int(result[key])))
        except (ValueError, TypeError):
            result[key] = DEFAULT_BROWSING[key]
    result['browse_daily_limit'] = 0
    return result


def migrate(settings):
    saved = settings.get('browsing') or {}
    legacy = settings.get('qq', {}).get('account', {})
    values = {key: legacy[key] for key in BROWSING_KEYS if key in legacy}
    values.update(saved)
    if saved.get('defaults_version') not in (1, 2):
        # The user requested browsing/interaction enabled by default in this release.
        values.update(browse_bilibili=True, browse_open_browser=True, browse_allow_comments=True,
                      browse_skipping=True)
    if saved.get('defaults_version') != 2:
        values.update(browse_browser='extension', browse_topics='', defaults_version=2)
    settings['browsing'] = normalize(values)
    return settings


from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QToolButton
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices


class BrowsingPage(QWidget):
    def __init__(self, window):
        super().__init__(window.heartbeat_panel)
        self.window = window
        panel = window.qq_account_panel
        box = QVBoxLayout(self)
        box.setContentsMargins(10, 16, 10, 16)
        title = QLabel('浏览与活动', self)
        title.setStyleSheet('font-size:20px;font-weight:600')
        box.addWidget(title)
        note = QLabel('她可以研究问题、读网页、搜图、看不同网站，或操作已授权的应用。'
                      '鲸鱼心跳决定做什么；B站提供额外的播放器和后台评论能力。', self)
        note.setWordWrap(True)
        box.addWidget(note)
        for widget, label in ((panel.browse_enabled, 'B站浏览（默认开启）'),
                              (panel.browse_comments, '后台评论与点赞（默认开启）'),
                              (panel.browse_local, '有想分享的发现时发到软件聊天')):
            widget.setText(label)
            box.addWidget(widget)
            widget.show()
        self.status = QLabel('评论与选片沿用你现有浏览器的B站登录。', self)
        self.status.setWordWrap(True)
        box.addWidget(self.status)
        controls = QHBoxLayout()
        for label, callback in (('接入已登录的浏览器', self.connect_existing_browser), ('停止视频活动', self.stop), ('保存浏览设置', self.save)):
            button = QPushButton(label, self)
            button.clicked.connect(callback)
            controls.addWidget(button)
        box.addLayout(controls)
        tip = QLabel('首次把连接扩展加载到原来登录B站的浏览器中即可，无需再次登录或扫码。她按自己的兴趣和见闻选片，'
                     '也可以先逛推荐页，不需要你设置题材。', self)
        tip.setWordWrap(True)
        box.addWidget(tip)
        toggle = QToolButton(self)
        toggle.setText('浏览器连接、视频细节与观看记录')
        toggle.setCheckable(True)
        toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toggle.setArrowType(Qt.ArrowType.RightArrow)
        box.addWidget(toggle)
        advanced = panel.pages['B站漫游']
        box.addWidget(advanced)
        advanced.hide()
        toggle.toggled.connect(advanced.setVisible)
        toggle.toggled.connect(lambda enabled: toggle.setArrowType(Qt.ArrowType.DownArrow if enabled else Qt.ArrowType.RightArrow))
        box.addStretch()
        self._connection_signature = None
        self.connection_timer = QTimer(self)
        self.connection_timer.setInterval(2000)
        self.connection_timer.timeout.connect(self.refresh_connection)
        self.connection_timer.start()
        self.refresh_connection()

    def save(self):
        window, panel = self.window, self.window.qq_account_panel
        previous = dict(window.settings['browsing'])
        account_before = dict(window.settings['qq']['account'])
        peer = panel.browse_peer.text().strip()
        if panel.browse_qq.isChecked() and peer not in window._get_allowlist():
            self.status.setText('开启QQ分享前，请先在QQ接入的信任名单中选择接收方。')
            return False
        values = {**previous, 'browse_bilibili': panel.browse_enabled.isChecked(),
                  'browse_allow_comments': panel.browse_comments.isChecked(),
                  'browse_open_browser': panel.browse_open.isChecked(),
                  'browse_browser': panel.browse_browser.currentData(), 'browse_topics': panel.browse_topics.text(),
                  'browse_skipping': panel.browse_skipping.isChecked(), 'browse_pause_on_input': panel.browse_pause.isChecked(),
                  'browse_share_local': panel.browse_local.isChecked()}
        window.settings['browsing'] = normalize(values)
        window.settings['qq']['account'] = {**account_before, 'browse_share_qq': panel.browse_qq.isChecked(),
            'browse_share_peer': peer, 'browse_notify_start': panel.browse_notify.isChecked()}
        try:
            window.write_config()
        except OSError as error:
            window.settings['browsing'] = previous
            window.settings['qq']['account'] = account_before
            self.status.setText('保存未完成：'+str(error)[:120])
            return False
        window.qq_account_service.configure_browsing(window.settings['browsing'])
        window.qq_account_service.configure(window.settings['qq']['account'])
        if not values['browse_bilibili']:
            window.bilibili_visits.stop_session(cancel_share=True)
        panel.refresh_browsing()
        self.status.setText('浏览设置已保存。后台评论与QQ连接独立。')
        return True

    def connect_existing_browser(self):
        try:
            folder = self.window.bilibili_visits.link.export()
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
            self.status.setText('已打开连接扩展目录。在原来登录B站的浏览器加载此目录；已有扩展请点重新加载。保持浏览器开启即可，不用重新登录B站。')
        except (ValueError, OSError) as error:
            self.status.setText('连接准备未完成：'+str(error)[:120])

    def refresh_connection(self):
        controller = getattr(self.window, 'bilibili_visits', None)
        if controller is None:
            return
        link = controller.link
        signature = (bool(link.connection), link.browser, getattr(link, 'background_bilibili', False))
        if signature == self._connection_signature:
            return
        self._connection_signature = signature
        self.status.setText('已连接'+link.browser+'，使用这个浏览器资料的B站登录状态。' if link.connection else
                            '尚未连接日常浏览器。首次接入连接扩展后，就能沿用已有登录，无需重新扫码。')

    def stop(self):
        self.window.bilibili_visits.stop_session(cancel_share=True)
