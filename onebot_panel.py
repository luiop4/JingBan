"""Embedded OneBot controls. Construct widgets in their layout before showing them."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QTextCursor
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QToolButton,
                              QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox,
                              QVBoxLayout, QWidget)

from onebot_service import OneBotService


class OneBotPanel(QWidget):
    start_requested = Signal()
    stopping = Signal()
    stopped = Signal()
    ready = Signal()
    repair_requested = Signal()
    busy_changed = Signal(bool)

    def __init__(self, root, options=None, parent=None):
        super().__init__(parent)
        self.root = Path(root)
        self.worker = None
        self._logged_in = False
        options = options if isinstance(options, dict) else {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        card = QGroupBox('内置 OneBot · NapCat', self)
        body = QVBoxLayout(card)
        body.setSpacing(12)
        header = QHBoxLayout()
        self.status = QLabel('未启动 · 点击启动后在本页扫码登录', card)
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        header.addWidget(self.status, 1)
        try:
            import json
            info = json.loads((self.root / 'onebot/runtime/jingban-release.json').read_text(encoding='utf-8'))
            version = info['version']
        except (OSError, ValueError, KeyError):
            version = '组件待修复'
        header.addWidget(QLabel(version, card))
        body.addLayout(header)
        form = QFormLayout()
        path_row = QHBoxLayout()
        self.qq_path = QLineEdit(str(options.get('qq_path', '')), card)
        self.qq_path.setPlaceholderText('自动检测已安装的 QQ，也可手动选择 QQ.exe')
        self.browse = QPushButton('选择 QQ', card)
        self.browse.clicked.connect(self._choose_qq)
        path_row.addWidget(self.qq_path, 1)
        path_row.addWidget(self.browse)
        form.addRow('QQ 客户端', path_row)
        self.web_port = QSpinBox(card)
        self.web_port.setRange(1024, 65535)
        try:
            self.web_port.setValue(int(options.get('webui_port', 6099)))
        except (ValueError, TypeError):
            self.web_port.setValue(6099)
        form.addRow('本机管理端口', self.web_port)
        advanced = QWidget(card)
        advanced_layout = QVBoxLayout(advanced)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.addLayout(form)
        options_row = QHBoxLayout()
        self.auto_connect = QCheckBox('登录成功后连接鲸伴', card)
        self.auto_connect.setChecked(bool(options.get('auto_connect', True)))
        self.auto_start = QCheckBox('随鲸伴启动内置服务', card)
        self.auto_start.setChecked(bool(options.get('auto_start', False)))
        self.remember_login = QCheckBox('记住账号，下次快速登录', card)
        self.remember_login.setChecked(bool(options.get('remember_login', True)))
        options_row.addWidget(self.auto_connect)
        options_row.addWidget(self.auto_start)
        options_row.addStretch(1)
        body.addLayout(options_row)
        body.addWidget(self.remember_login)
        actions = QHBoxLayout()
        self.start_button = QPushButton('启动并登录 QQ', card)
        self.stop_button = QPushButton('停止服务', card)
        self.refresh_button = QPushButton('刷新二维码', card)
        self.repair_button = QPushButton('退出并修复组件', card)
        self.stop_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.start_button.clicked.connect(lambda: self.start_requested.emit())
        self.stop_button.clicked.connect(self.stop)
        self.refresh_button.clicked.connect(self._refresh_qr)
        self.repair_button.clicked.connect(lambda: self.repair_requested.emit())
        for button in (self.start_button, self.stop_button, self.refresh_button, self.repair_button):
            actions.addWidget(button)
        actions.addStretch(1)
        body.addLayout(actions)
        login_row = QHBoxLayout()
        self.qr = QLabel('登录二维码\n启动后显示', card)
        self.qr.setFixedSize(192, 192)
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setStyleSheet('background: white; color: #778196; border: 1px solid #E3E8F0; border-radius: 12px;')
        login_row.addWidget(self.qr)
        self.login_help = QLabel('使用手机 QQ 扫描这里的二维码，并在手机上确认登录。\n\n'
                                '二维码过期可点击刷新。登录状态、启动错误和运行日志会显示在本页。\n'
                                '自动回复仍由下方开关和白名单决定。', card)
        self.login_help.setWordWrap(True)
        self.login_help.setTextFormat(Qt.TextFormat.PlainText)
        login_row.addWidget(self.login_help, 1)
        body.addLayout(login_row)
        log_heading = QHBoxLayout()
        log_heading.addWidget(QLabel('运行日志', card))
        log_heading.addStretch(1)
        clear = QPushButton('清空显示', card)
        log_heading.addWidget(clear)
        advanced_layout.addLayout(log_heading)
        self.log = QPlainTextEdit(card)
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setMinimumHeight(140)
        self.log.setMaximumHeight(230)
        self.log.setPlaceholderText('内置服务的原控制台内容将显示在这里；访问令牌自动隐藏。')
        clear.clicked.connect(self.log.clear)
        advanced_layout.addWidget(self.log)
        detail_toggle = QToolButton(card)
        detail_toggle.setText('高级路径与运行日志')
        detail_toggle.setCheckable(True)
        detail_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        detail_toggle.setArrowType(Qt.ArrowType.RightArrow)
        body.addWidget(detail_toggle)
        body.addWidget(advanced)
        advanced.hide()
        detail_toggle.toggled.connect(advanced.setVisible)
        detail_toggle.toggled.connect(lambda checked: detail_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow))
        note = QLabel('内置组件随软件更新，登录配置保存在本机。\n'
                      '记住账号后，下次启动优先复用 QQ 登录态；登录失效或 QQ 要求验证时仍需扫码。', card)
        note.setWordWrap(True)
        body.addWidget(note)
        layout.addWidget(card)

    def options(self):
        return {'qq_path': self.qq_path.text().strip(), 'webui_port': self.web_port.value(),
                'auto_connect': self.auto_connect.isChecked(), 'auto_start': self.auto_start.isChecked(),
                'remember_login': self.remember_login.isChecked()}

    def is_busy(self):
        return self.worker is not None and self.worker.isRunning()

    def can_connect(self):
        return (self.is_busy() and self._logged_in and not self.worker.stop_requested.is_set())

    def start(self, config):
        if self.worker is not None:
            return
        self._logged_in = False
        self.qr.clear()
        self.qr.setText('正在启动…')
        self.status.setText('正在启动内置服务…')
        worker = OneBotService(self.root, config, self)
        self.worker = worker
        worker.status_changed.connect(self.status.setText, Qt.ConnectionType.QueuedConnection)
        worker.log_received.connect(self._append_log, Qt.ConnectionType.QueuedConnection)
        worker.qr_received.connect(self._show_qr, Qt.ConnectionType.QueuedConnection)
        worker.login_changed.connect(self._login_changed, Qt.ConnectionType.QueuedConnection)
        worker.ready.connect(self.ready, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(worker.deleteLater)
        self._set_busy(True)
        worker.start()

    def _set_busy(self, busy):
        self.start_button.setEnabled(not busy)
        self.stop_button.setEnabled(busy)
        self.refresh_button.setEnabled(busy and not self._logged_in)
        for widget in (self.qq_path, self.browse, self.web_port, self.repair_button):
            widget.setEnabled(not busy)
        self.busy_changed.emit(busy)

    def stop(self):
        if self.worker is not None:
            self.stopping.emit()
            self.status.setText('正在停止内置服务…')
            self.stop_button.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.worker.stop()

    def _finished(self):
        if self.sender() is not self.worker:
            return
        self.worker = None
        self._logged_in = False
        self.qr.clear()
        self.qr.setText('服务已停止')
        self._set_busy(False)
        self.stopped.emit()

    def _show_qr(self, data):
        if self._logged_in:
            return
        image = QPixmap()
        if image.loadFromData(data, 'PNG'):
            self.qr.setPixmap(image.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.FastTransformation))
            self.login_help.setText('请使用手机 QQ 扫描左侧二维码，并在手机上确认登录。\n\n'
                                    '登录成功后可自动连接鲸伴；二维码过期请点击“刷新二维码”。')

    def _login_changed(self, value):
        was_logged_in = self._logged_in
        self._logged_in = bool(value.get('isLogin'))
        self.refresh_button.setEnabled(not self._logged_in)
        if self._logged_in:
            self.status.setText('QQ 已登录 · 内置服务运行中')
            self.qr.clear()
            self.qr.setText('QQ 已在线')
            self.login_help.setText('QQ 已登录。\n\n点击“停止服务”会结束本次内置桥接；退出鲸伴也会停止它。\n'
                                    '勾选“记住账号”并保存后，下次启动优先快速登录。登录态由本机 QQ 保存。')
        else:
            if was_logged_in:
                self.qr.clear()
                self.qr.setText('等待新的二维码…')
            phases = {'waiting_qrcode': '等待扫码', 'generating_qrcode': '正在生成二维码…',
                      'quick_login': '正在尝试上次账号快速登录…',
                      'qrcode_scanned': '二维码已扫描，请在手机上确认', 'initializing': '登录已确认，正在初始化…',
                      'offline': 'QQ 已离线，请重新扫码', 'reconnecting': 'QQ 正在重新连接…'}
            self.status.setText(str(value.get('loginError') or phases.get(value.get('loginPhase'), '正在准备登录…')))

    def _refresh_qr(self):
        if self.worker is not None:
            self.qr.clear()
            self.qr.setText('正在刷新…')
            self.worker.refresh_qr()

    def _append_log(self, text):
        scrollbar = self.log.verticalScrollBar()
        value = scrollbar.value()
        bottom = value >= scrollbar.maximum() - 3
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        if bottom:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(value)

    def _choose_qq(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择本机 QQ.exe', self.qq_path.text(), 'QQ 客户端 (QQ.exe)')
        if path:
            self.qq_path.setText(path)
