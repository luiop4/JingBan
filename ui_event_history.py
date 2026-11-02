# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'event_history.ui'
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
from PySide6.QtWidgets import (QApplication, QDialog, QLabel, QPlainTextEdit,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget)

class Ui_EventHistoryDialog(object):
    def setupUi(self, EventHistoryDialog):
        if not EventHistoryDialog.objectName():
            EventHistoryDialog.setObjectName(u"EventHistoryDialog")
        EventHistoryDialog.setMinimumSize(QSize(560, 400))
        EventHistoryDialog.setSizeGripEnabled(True)
        self.mainLayout = QVBoxLayout(EventHistoryDialog)
        self.mainLayout.setObjectName(u"mainLayout")
        self.descriptionLabel = QLabel(EventHistoryDialog)
        self.descriptionLabel.setObjectName(u"descriptionLabel")
        self.descriptionLabel.setWordWrap(True)

        self.mainLayout.addWidget(self.descriptionLabel)

        self.historyText = QPlainTextEdit(EventHistoryDialog)
        self.historyText.setObjectName(u"historyText")
        self.historyText.setReadOnly(True)

        self.mainLayout.addWidget(self.historyText)

        self.closeButton = QPushButton(EventHistoryDialog)
        self.closeButton.setObjectName(u"closeButton")

        self.mainLayout.addWidget(self.closeButton)


        self.retranslateUi(EventHistoryDialog)

        QMetaObject.connectSlotsByName(EventHistoryDialog)
    # setupUi

    def retranslateUi(self, EventHistoryDialog):
        EventHistoryDialog.setWindowTitle(QCoreApplication.translate("EventHistoryDialog", u"\u4e8b\u4ef6\u53d8\u66f4\u8bb0\u5f55", None))
        self.descriptionLabel.setText(QCoreApplication.translate("EventHistoryDialog", u"\u6700\u8fd1 100 \u6b21\u8bb0\u5f55 \u00b7 \u6700\u65b0\u5728\u524d \u00b7 \u72b6\u6001\u4ee5\u7528\u6237\u6d88\u606f\u4e3a\u4f9d\u636e", None))
        self.closeButton.setText(QCoreApplication.translate("EventHistoryDialog", u"\u5173\u95ed", None))
    # retranslateUi

