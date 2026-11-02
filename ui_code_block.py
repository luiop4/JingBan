# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'code_block.ui'
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
    QPlainTextEdit, QPushButton, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)

class Ui_CodeBlock(object):
    def setupUi(self, CodeBlock):
        if not CodeBlock.objectName():
            CodeBlock.setObjectName(u"CodeBlock")
        CodeBlock.setMinimumSize(QSize(260, 0))
        self.verticalLayout = QVBoxLayout(CodeBlock)
        self.verticalLayout.setSpacing(6)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.headerLayout = QHBoxLayout()
        self.headerLayout.setObjectName(u"headerLayout")
        self.languageLabel = QLabel(CodeBlock)
        self.languageLabel.setObjectName(u"languageLabel")

        self.headerLayout.addWidget(self.languageLabel)

        self.headerSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.headerLayout.addItem(self.headerSpacer)

        self.copyButton = QPushButton(CodeBlock)
        self.copyButton.setObjectName(u"copyButton")

        self.headerLayout.addWidget(self.copyButton)


        self.verticalLayout.addLayout(self.headerLayout)

        self.codeEditor = QPlainTextEdit(CodeBlock)
        self.codeEditor.setObjectName(u"codeEditor")
        self.codeEditor.setReadOnly(True)
        self.codeEditor.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.verticalLayout.addWidget(self.codeEditor)


        self.retranslateUi(CodeBlock)

        QMetaObject.connectSlotsByName(CodeBlock)
    # setupUi

    def retranslateUi(self, CodeBlock):
        self.languageLabel.setText(QCoreApplication.translate("CodeBlock", u"\u4ee3\u7801", None))
        self.copyButton.setText(QCoreApplication.translate("CodeBlock", u"\u590d\u5236\u4ee3\u7801", None))
        pass
    # retranslateUi

