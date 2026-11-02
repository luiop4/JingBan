"""About page with the installed version and locally bundled release history."""
from html import escape

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                              QSizePolicy, QTextBrowser, QVBoxLayout, QWidget, QPushButton)

from app_info import ROOT, application_info, release_history


class AboutPage(QWidget):
    repair_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('aboutPage')
        info = application_info()
        self.releases = release_history()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(20)

        card = QFrame(self)
        card.setObjectName('aboutBrandCard')
        header = QHBoxLayout(card)
        header.setContentsMargins(22, 20, 22, 20)
        header.setSpacing(16)
        icon = QLabel(card)
        icon.setFixedSize(68, 68)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(ROOT / 'assets' / 'jingban-icon.png'))
        if not pixmap.isNull():
            icon.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))
        else:
            icon.setText('鲸伴')
        header.addWidget(icon)
        identity = QVBoxLayout()
        title = QLabel(info['name'], card)
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setObjectName('aboutAppName')
        identity.addWidget(title)
        subtitle = QLabel('有记忆的陪伴', card)
        subtitle.setObjectName('aboutTagline')
        identity.addWidget(subtitle)
        header.addLayout(identity)
        header.addStretch(1)
        version = QLabel('当前版本  v' + info['version'], card)
        version.setObjectName('aboutVersionBadge')
        version.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header.addWidget(version)
        layout.addWidget(card)

        intro = QLabel('对话与记忆保存在本机，支持历史检索、语音交流和电脑协作。', self)
        intro.setObjectName('aboutIntroduction')
        intro.setWordWrap(True)
        layout.addWidget(intro)

        update_row = QHBoxLayout()
        update_help = QLabel('启动时自动校验程序与 OneBot 组件，同版本也可补齐缺失或损坏的文件。', self)
        update_help.setWordWrap(True)
        update_row.addWidget(update_help, 1)
        repair_button = QPushButton('退出并检查修复', self)
        repair_button.setToolTip('保存当前对话后退出，打开启动器检查更新与文件完整性。')
        repair_button.clicked.connect(lambda checked=False: self.repair_requested.emit())
        update_row.addWidget(repair_button)
        layout.addLayout(update_row)

        history_heading = QHBoxLayout()
        title = QLabel('版本更新记录', self)
        title.setObjectName('aboutHistoryTitle')
        history_heading.addWidget(title)
        history_heading.addStretch(1)
        count = QLabel(f'共 {len(self.releases)} 个版本', self)
        count.setObjectName('aboutHistoryCount')
        history_heading.addWidget(count)
        layout.addLayout(history_heading)

        history = QHBoxLayout()
        history.setSpacing(16)
        self.version_list = QListWidget(self)
        self.version_list.setObjectName('aboutVersionList')
        self.version_list.setFixedWidth(152)
        for record in self.releases:
            label = 'v' + record['version']
            if record['version'] == info['version']:
                label += '  · 当前'
            item = QListWidgetItem(label)
            item.setSizeHint(QSize(140, 46))
            self.version_list.addItem(item)
        self.notes = QTextBrowser(self)
        self.notes.setObjectName('aboutReleaseNotes')
        self.notes.setOpenExternalLinks(False)
        self.notes.setOpenLinks(False)
        self.notes.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        history.addWidget(self.version_list)
        history.addWidget(self.notes, 1)
        layout.addLayout(history, 1)
        self.version_list.currentRowChanged.connect(self.show_release)
        if self.releases:
            current = next((index for index, record in enumerate(self.releases)
                            if record['version'] == info['version']), 0)
            self.version_list.setCurrentRow(current)
        else:
            self.notes.setPlainText('暂时没有版本更新记录。')

    def show_release(self, index):
        if not 0 <= index < len(self.releases):
            return
        record = self.releases[index]
        paragraphs = [escape(line.strip()) for line in record['content'].splitlines() if line.strip()]
        self.notes.setHtml('<h2 style="font-size:18px; margin-bottom:18px">v' + escape(record['version']) +
                           '</h2>' + ''.join('<p style="line-height:155%; margin:0 0 13px">' + line + '</p>' for line in paragraphs))
        self.notes.verticalScrollBar().setValue(0)
