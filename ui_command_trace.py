# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'command_trace.ui'
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
from PySide6.QtWidgets import (QApplication, QFrame, QLabel, QPlainTextEdit,
    QSizePolicy, QToolButton, QVBoxLayout, QWidget)

class Ui_CommandTrace(object):
    def setupUi(self, CommandTrace):
        if not CommandTrace.objectName():
            CommandTrace.setObjectName(u"CommandTrace")
        self.traceLayout = QVBoxLayout(CommandTrace)
        self.traceLayout.setSpacing(6)
        self.traceLayout.setObjectName(u"traceLayout")
        self.traceLayout.setContentsMargins(8, 6, 8, 6)
        self.toggleButton = QToolButton(CommandTrace)
        self.toggleButton.setObjectName(u"toggleButton")
        self.toggleButton.setCheckable(True)
        self.toggleButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggleButton.setArrowType(Qt.RightArrow)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.toggleButton.sizePolicy().hasHeightForWidth())
        self.toggleButton.setSizePolicy(sizePolicy)

        self.traceLayout.addWidget(self.toggleButton)

        self.detailsPanel = QWidget(CommandTrace)
        self.detailsPanel.setObjectName(u"detailsPanel")
        self.detailsLayout = QVBoxLayout(self.detailsPanel)
        self.detailsLayout.setObjectName(u"detailsLayout")
        self.detailsLayout.setContentsMargins(0, 0, 0, 0)
        self.purposeLabel = QLabel(self.detailsPanel)
        self.purposeLabel.setObjectName(u"purposeLabel")
        self.purposeLabel.setWordWrap(True)
        self.purposeLabel.setTextFormat(Qt.PlainText)

        self.detailsLayout.addWidget(self.purposeLabel)

        self.directoryLabel = QLabel(self.detailsPanel)
        self.directoryLabel.setObjectName(u"directoryLabel")
        self.directoryLabel.setWordWrap(True)
        self.directoryLabel.setTextFormat(Qt.PlainText)

        self.detailsLayout.addWidget(self.directoryLabel)

        self.commandView = QPlainTextEdit(self.detailsPanel)
        self.commandView.setObjectName(u"commandView")
        self.commandView.setReadOnly(True)
        self.commandView.setMaximumHeight(110)

        self.detailsLayout.addWidget(self.commandView)

        self.outputTitle = QLabel(self.detailsPanel)
        self.outputTitle.setObjectName(u"outputTitle")

        self.detailsLayout.addWidget(self.outputTitle)

        self.outputView = QPlainTextEdit(self.detailsPanel)
        self.outputView.setObjectName(u"outputView")
        self.outputView.setReadOnly(True)
        self.outputView.setMinimumHeight(120)
        self.outputView.setMaximumHeight(240)

        self.detailsLayout.addWidget(self.outputView)

        self.resultLabel = QLabel(self.detailsPanel)
        self.resultLabel.setObjectName(u"resultLabel")
        self.resultLabel.setWordWrap(True)

        self.detailsLayout.addWidget(self.resultLabel)

        self.ephemeralLabel = QLabel(self.detailsPanel)
        self.ephemeralLabel.setObjectName(u"ephemeralLabel")
        self.ephemeralLabel.setWordWrap(True)

        self.detailsLayout.addWidget(self.ephemeralLabel)


        self.traceLayout.addWidget(self.detailsPanel)


        self.retranslateUi(CommandTrace)

        QMetaObject.connectSlotsByName(CommandTrace)
    # setupUi

    def retranslateUi(self, CommandTrace):
        self.toggleButton.setText(QCoreApplication.translate("CommandTrace", u"\u7535\u8111\u64cd\u4f5c", None))
        self.outputTitle.setText(QCoreApplication.translate("CommandTrace", u"\u6267\u884c\u8f93\u51fa", None))
        self.outputView.setPlaceholderText(QCoreApplication.translate("CommandTrace", u"\u547d\u4ee4\u5c1a\u672a\u4ea7\u751f\u8f93\u51fa", None))
        self.ephemeralLabel.setText(QCoreApplication.translate("CommandTrace", "操作日志单独保存 · 追问近期任务时读取摘要 · 不加入长期记忆", None))
        pass
    # retranslateUi

