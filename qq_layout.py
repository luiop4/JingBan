"""One QQ workspace with stable navigation and a single visible trust list."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget)


class QQHub(QWidget):
    def __init__(self, window):
        super().__init__(window.qqScrollContent)
        self.window = window
        self.setObjectName('qqHub')
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.setStyleSheet('''
            QWidget#qqHub { background:#F7F9FD; }
            QListWidget#qqNav { background:#EEF2F9; border:0; border-radius:12px; padding:6px; }
            QListWidget#qqNav::item { padding:13px 10px; border-radius:8px; color:#64718B; }
            QListWidget#qqNav::item:selected { background:#DFE7FF; color:#365FE7; font-weight:600; }
            QGroupBox { background:white; border:1px solid #E3E8F1; border-radius:12px;
                        margin-top:14px; padding:16px; }
            QGroupBox::title { subcontrol-origin:margin; left:16px; color:#34466C; }
            QPushButton { padding:9px 14px; border-radius:8px; }
        ''')
        # Keep the original widgets and signal targets; change only their layout.
        layout = window.qqContentLayout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(14)
        body = QHBoxLayout()
        self.navigation = QListWidget(self)
        self.navigation.setObjectName('qqNav')
        self.navigation.setFixedWidth(142)
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stack = QStackedWidget(self)
        self.stack.setMinimumSize(0, 420)
        self.stack.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        body.addWidget(self.navigation)
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        connect, box = self.page('连接登录')
        self.add(box, window.onebotContainer)
        toggle = QToolButton(connect)
        toggle.setText('外部桥接 / 高级连接设置')
        toggle.setCheckable(True)
        toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toggle.setArrowType(Qt.ArrowType.RightArrow)
        box.addWidget(toggle)
        window.qqConnectionCard.setTitle('外部 OneBot WebSocket')
        self.add(box, window.qqConnectionCard)
        window.qqConnectionCard.hide()
        window.qqAllowlistLabel.hide()
        toggle.toggled.connect(window.qqConnectionCard.setVisible)
        toggle.toggled.connect(lambda checked: toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow))
        window.qqConnectButton.setText('连接 / 断开桥接')
        self.add(box, window.qqConnectButton)
        box.addStretch()

        permissions, box = self.page('聊天与联系人')
        trust = QGroupBox('信任联系人 · 全部QQ功能共用', permissions)
        form = QVBoxLayout(trust)
        hint = QLabel('只在这里填写一次QQ号。名单内联系人可使用已开启的回复、账号、电脑和主动互动功能。', trust)
        hint.setWordWrap(True)
        form.addWidget(hint)
        window.qqAllowlistEdit.setPlaceholderText('QQ号用逗号或空格分隔；留空不开放QQ功能')
        form.addWidget(window.qqAllowlistEdit)
        box.addWidget(trust)
        window.qqReplyCard.setTitle('聊天回复')
        window.qqAutoReplyCheckBox.setText('自动回复信任联系人的私聊')
        self.add(box, window.qqReplyCard)
        panel = window.qq_account_panel
        from qq_account_panel import TrustedPeerSelector
        previous_recipient = window.qqRecipientEdit
        window.qqRecipientEdit = TrustedPeerSelector('', window, window.qqManualCard)
        window.qqManualLayout.replaceWidget(previous_recipient, window.qqRecipientEdit)
        previous_recipient.hide()
        previous_recipient.deleteLater()
        self.add(box, panel.active_enabled)
        self.fold(box, '主动聊天、跨端同步与权限细节',
                  (panel.pages['主动互动'], panel.pages['跨端同步'], panel.pages['自主与权限']))
        box.addStretch()
        social, box = self.page('空间与资料')
        life = QGroupBox('她的QQ生活', social)
        life_box = QVBoxLayout(life)
        panel.social_state = QLabel('连接QQ后，她会延续自己的打算。', life)
        panel.social_state.setWordWrap(True)
        panel.social_state.setTextFormat(Qt.TextFormat.PlainText)
        life_box.addWidget(panel.social_state)
        think = QPushButton('让她现在想想', life)
        think.clicked.connect(self.review_social)
        life_box.addWidget(think)
        box.addWidget(life)
        for widget in (panel.auto, panel.auto_profile, panel.auto_reply, panel.auto_images):
            self.add(box, widget)
        self.fold(box, '可见范围、资料编辑与手动发送',
                  (panel.pages['发布说说'], panel.account, panel.pages['账号资料'], window.qqManualCard))
        box.addStretch()
        page, box = self.page('运行记录')
        self.add(box, panel.pages['执行记录'])
        box.addStretch()
        panel.hide()
        footer = QHBoxLayout()
        window.saveQqButton.setText('保存全部QQ设置')
        footer.addWidget(window.saveQqButton)
        window.saveQqButton.show()
        footer.addWidget(window.qqStatusLabel, 1)
        window.qqStatusLabel.setWordWrap(True)
        window.qqStatusLabel.show()
        outer.addLayout(footer)
        outer.addWidget(panel.status)
        panel.status.show()
        window.qqSafetyNote.hide()
        layout.addWidget(self)
        self.navigation.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navigation.setCurrentRow(0)

    def review_social(self):
        # QQHub is parented to qqScrollContent; keep the actual application
        # reference instead of relying on the Qt widget parent chain.
        controller = self.window.qq_social
        controller.next_check = 0
        controller.tick()
        self.window.qq_account_panel.refresh()

    def page(self, title):
        self.navigation.addItem(title)
        scroll = QScrollArea(self.stack)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget(scroll)
        content.setMinimumWidth(0)
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        box = QVBoxLayout(content)
        box.setContentsMargins(10, 4, 10, 10)
        box.setSpacing(14)
        heading = QLabel(title, content)
        heading.setStyleSheet('font-size:19px;font-weight:600;color:#34466C;padding:4px;')
        box.addWidget(heading)
        scroll.setWidget(content)
        self.stack.addWidget(scroll)
        return content, box

    @staticmethod
    def add(box, widget):
        box.addWidget(widget)
        widget.show()

    def fold(self, box, title, widgets):
        button = QToolButton(self)
        button.setText(title)
        button.setCheckable(True)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setArrowType(Qt.ArrowType.RightArrow)
        box.addWidget(button)
        frame = QWidget(self)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 4, 0, 0)
        for widget in widgets:
            self.add(layout, widget)
        box.addWidget(frame)
        frame.hide()
        button.toggled.connect(frame.setVisible)
        button.toggled.connect(lambda on: button.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow))
