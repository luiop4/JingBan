# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'launcher.ui'
##
## Created by: Qt User Interface Compiler version 6.12.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QProgressBar, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget)

class Ui_LauncherWindow(object):
    def setupUi(self, LauncherWindow):
        if not LauncherWindow.objectName():
            LauncherWindow.setObjectName(u"LauncherWindow")
        LauncherWindow.setMinimumSize(QSize(720, 440))
        self.centralwidget = QWidget(LauncherWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.outerLayout = QVBoxLayout(self.centralwidget)
        self.outerLayout.setObjectName(u"outerLayout")
        self.outerLayout.setContentsMargins(14, 14, 14, 14)
        self.panel = QFrame(self.centralwidget)
        self.panel.setObjectName(u"panel")
        self.panelLayout = QHBoxLayout(self.panel)
        self.panelLayout.setSpacing(26)
        self.panelLayout.setObjectName(u"panelLayout")
        self.graphicLayout = QVBoxLayout()
        self.graphicLayout.setObjectName(u"graphicLayout")
        self.characterLabel = QLabel(self.panel)
        self.characterLabel.setObjectName(u"characterLabel")
        self.characterLabel.setMinimumSize(QSize(180, 240))
        self.characterLabel.setMaximumSize(QSize(180, 240))

        self.graphicLayout.addWidget(self.characterLabel)

        self.engineLabel = QLabel(self.panel)
        self.engineLabel.setObjectName(u"engineLabel")

        self.graphicLayout.addWidget(self.engineLabel)


        self.panelLayout.addLayout(self.graphicLayout)

        self.infoLayout = QVBoxLayout()
        self.infoLayout.setSpacing(9)
        self.infoLayout.setObjectName(u"infoLayout")
        self.brandLabel = QLabel(self.panel)
        self.brandLabel.setObjectName(u"brandLabel")

        self.infoLayout.addWidget(self.brandLabel)

        self.titleLabel = QLabel(self.panel)
        self.titleLabel.setObjectName(u"titleLabel")

        self.infoLayout.addWidget(self.titleLabel)

        self.subtitleLabel = QLabel(self.panel)
        self.subtitleLabel.setObjectName(u"subtitleLabel")

        self.infoLayout.addWidget(self.subtitleLabel)

        self.descriptionLabel = QLabel(self.panel)
        self.descriptionLabel.setObjectName(u"descriptionLabel")

        self.infoLayout.addWidget(self.descriptionLabel)

        self.schemaLabel = QLabel(self.panel)
        self.schemaLabel.setObjectName(u"schemaLabel")
        self.schemaLabel.setWordWrap(True)
        self.schemaLabel.setTextFormat(Qt.RichText)

        self.infoLayout.addWidget(self.schemaLabel)

        self.featuresLabel = QLabel(self.panel)
        self.featuresLabel.setObjectName(u"featuresLabel")
        self.featuresLabel.setTextFormat(Qt.RichText)
        self.featuresLabel.setWordWrap(True)

        self.infoLayout.addWidget(self.featuresLabel)

        self.statusLabel = QLabel(self.panel)
        self.statusLabel.setObjectName(u"statusLabel")

        self.infoLayout.addWidget(self.statusLabel)

        self.progressBar = QProgressBar(self.panel)
        self.progressBar.setObjectName(u"progressBar")
        self.progressBar.setValue(0)
        self.progressBar.setTextVisible(False)

        self.infoLayout.addWidget(self.progressBar)

        self.authorLayout = QHBoxLayout()
        self.authorLayout.setObjectName(u"authorLayout")
        self.authorAvatarLabel = QLabel(self.panel)
        self.authorAvatarLabel.setObjectName(u"authorAvatarLabel")
        self.authorAvatarLabel.setMaximumSize(QSize(22, 22))

        self.authorLayout.addWidget(self.authorAvatarLabel)

        self.authorLabel = QLabel(self.panel)
        self.authorLabel.setObjectName(u"authorLabel")

        self.authorLayout.addWidget(self.authorLabel)


        self.infoLayout.addLayout(self.authorLayout)

        self.closeButton = QPushButton(self.panel)
        self.closeButton.setObjectName(u"closeButton")
        self.closeButton.setVisible(False)

        self.infoLayout.addWidget(self.closeButton)


        self.panelLayout.addLayout(self.infoLayout)


        self.outerLayout.addWidget(self.panel)

        LauncherWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(LauncherWindow)

        QMetaObject.connectSlotsByName(LauncherWindow)
    # setupUi

    def retranslateUi(self, LauncherWindow):
        LauncherWindow.setWindowTitle(QCoreApplication.translate("LauncherWindow", u"\u9cb8\u4f34 \u00b7 \u6b63\u5728\u542f\u52a8", None))
        self.characterLabel.setText("")
        self.engineLabel.setText(QCoreApplication.translate("LauncherWindow", u"\u5927\u80a5\u9c7c \u00b7 \u4f60\u7684\u9cb8\u4f34", None))
        self.brandLabel.setText(QCoreApplication.translate("LauncherWindow", u"LOCAL-FIRST  /  \u9762\u5411\u957f\u671f\u966a\u4f34\u7684\u8bb0\u5fc6\u67b6\u6784", None))
        self.titleLabel.setText(QCoreApplication.translate("LauncherWindow", u"\u9cb8\u4f34", None))
        self.subtitleLabel.setText(QCoreApplication.translate("LauncherWindow", u"\u53ef\u6eaf\u6e90\u3001\u53ef\u6f14\u8fdb\u7684\u4e8b\u4ef6\u7ea7\u957f\u671f\u8bb0\u5fc6", None))
        self.descriptionLabel.setText(QCoreApplication.translate("LauncherWindow", u"SQLite \u5173\u7cfb\u6a21\u578b  \u00d7  FTS5 \u7d22\u5f15  \u00d7  \u68c0\u7d22\u5f0f\u4e0a\u4e0b\u6587\u7ec4\u88c5", None))
        self.schemaLabel.setText(QCoreApplication.translate("LauncherWindow", u"<b>\u4e8b\u4ef6\u6f14\u8fdb \u00b7 Revision Tracking</b><br/>\u4fdd\u7559\u72b6\u6001\u4fee\u8ba2\u94fe\uff0c\u6821\u9a8c\u6765\u6e90\u987a\u5e8f\u4e0e\u7248\u672c\uff0c\u51cf\u5c11\u65e7\u72b6\u6001\u56de\u5199\u3002<br/><br/><b>\u6d88\u606f\u6eaf\u6e90 \u00b7 Source Provenance</b><br/>\u4e8b\u4ef6\u6458\u8981\u5173\u8054\u539f\u6d88\u606f\uff1b\u6765\u6e90\u5220\u9664\u65f6\uff0c\u76f8\u5173\u4e8b\u4ef6\u4e0e\u7d22\u5f15\u8054\u52a8\u5931\u6548\u3002<br/><br/><b>\u6309\u9700\u53ec\u56de \u00b7 Context Retrieval</b><br/>\u6309\u8bdd\u9898\u68c0\u7d22\u4e8b\u4ef6\u4e0e\u4e2a\u4eba\u8bb0\u5fc6\uff0c\u5fc5\u8981\u65f6\u56de\u8bfb\u539f\u6587\uff0c\u63a7\u5236\u4e0a\u4e0b\u6587\u7528\u91cf\u3002", None))
        self.featuresLabel.setText(QCoreApplication.translate("LauncherWindow", u"\u589e\u91cf\u5f52\u6863 \u2192 \u4e8b\u4ef6\u7d22\u5f15 \u2192 \u76f8\u5173\u53ec\u56de \u2192 \u539f\u6587\u56de\u8bfb", None))
        self.statusLabel.setText(QCoreApplication.translate("LauncherWindow", u"\u6b63\u5728\u51c6\u5907\u542f\u52a8\u2026", None))
        self.authorAvatarLabel.setText("")
        self.authorLabel.setText(QCoreApplication.translate("LauncherWindow", u"by \u96ea\u843d\u65f6", None))
        self.closeButton.setText(QCoreApplication.translate("LauncherWindow", u"\u5173\u95ed", None))
    # retranslateUi

