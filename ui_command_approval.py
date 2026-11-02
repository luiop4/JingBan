# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'command_approval.ui'
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
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget)

class Ui_CommandApproval(object):
    def setupUi(self, CommandApproval):
        if not CommandApproval.objectName():
            CommandApproval.setObjectName(u"CommandApproval")
        CommandApproval.resize(700, 440)
        self.mainLayout = QVBoxLayout(CommandApproval)
        self.mainLayout.setObjectName(u"mainLayout")
        self.introLabel = QLabel(CommandApproval)
        self.introLabel.setObjectName(u"introLabel")
        self.introLabel.setWordWrap(True)

        self.mainLayout.addWidget(self.introLabel)

        self.detailsLabel = QLabel(CommandApproval)
        self.detailsLabel.setObjectName(u"detailsLabel")
        self.detailsLabel.setWordWrap(True)

        self.mainLayout.addWidget(self.detailsLabel)

        self.commandEdit = QPlainTextEdit(CommandApproval)
        self.commandEdit.setObjectName(u"commandEdit")
        self.commandEdit.setReadOnly(True)

        self.mainLayout.addWidget(self.commandEdit)

        self.noteLabel = QLabel(CommandApproval)
        self.noteLabel.setObjectName(u"noteLabel")
        self.noteLabel.setWordWrap(True)

        self.mainLayout.addWidget(self.noteLabel)

        self.buttonsLayout = QHBoxLayout()
        self.buttonsLayout.setObjectName(u"buttonsLayout")
        self.cancelButton = QPushButton(CommandApproval)
        self.cancelButton.setObjectName(u"cancelButton")

        self.buttonsLayout.addWidget(self.cancelButton)

        self.executeButton = QPushButton(CommandApproval)
        self.executeButton.setObjectName(u"executeButton")
        self.executeButton.setAutoDefault(False)

        self.buttonsLayout.addWidget(self.executeButton)


        self.mainLayout.addLayout(self.buttonsLayout)


        self.retranslateUi(CommandApproval)

        self.cancelButton.setDefault(True)


        QMetaObject.connectSlotsByName(CommandApproval)
    # setupUi

    def retranslateUi(self, CommandApproval):
        CommandApproval.setWindowTitle(QCoreApplication.translate("CommandApproval", u"\u786e\u8ba4\u7535\u8111\u64cd\u4f5c", None))
        self.introLabel.setText(QCoreApplication.translate("CommandApproval", u"AI \u8bf7\u6c42\u6267\u884c\u4ee5\u4e0b\u547d\u4ee4\u3002\u6267\u884c\u540e\u53ef\u80fd\u4fee\u6539\u6587\u4ef6\u6216\u542f\u52a8\u7a0b\u5e8f\uff1b\u4ec5\u5728\u786e\u8ba4\u5185\u5bb9\u7b26\u5408\u4f60\u7684\u8981\u6c42\u65f6\u6267\u884c\u3002", None))
        self.noteLabel.setText(QCoreApplication.translate("CommandApproval", u"\u547d\u4ee4\u8f93\u51fa\u4f1a\u53d1\u7ed9\u5f53\u524d\u804a\u5929\u6a21\u578b\u3002\u8d85\u65f6\u4f1a\u5c1d\u8bd5\u505c\u6b62\u8fdb\u7a0b\uff0c\u4f46\u4e0d\u80fd\u64a4\u9500\u5df2\u53d1\u751f\u7684\u64cd\u4f5c\u3002", None))
        self.cancelButton.setText(QCoreApplication.translate("CommandApproval", u"\u53d6\u6d88", None))
        self.executeButton.setText(QCoreApplication.translate("CommandApproval", u"\u6267\u884c\u8fd9\u4e00\u6b21", None))
    # retranslateUi

