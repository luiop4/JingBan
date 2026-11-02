# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'history_manager.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateEdit,
    QDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_HistoryDialog(object):
    def setupUi(self, HistoryDialog):
        if not HistoryDialog.objectName():
            HistoryDialog.setObjectName(u"HistoryDialog")
        HistoryDialog.setMinimumSize(QSize(760, 520))
        self.mainLayout = QVBoxLayout(HistoryDialog)
        self.mainLayout.setObjectName(u"mainLayout")
        self.descriptionLabel = QLabel(HistoryDialog)
        self.descriptionLabel.setObjectName(u"descriptionLabel")
        self.descriptionLabel.setWordWrap(True)

        self.mainLayout.addWidget(self.descriptionLabel)

        self.searchLayout = QHBoxLayout()
        self.searchLayout.setObjectName(u"searchLayout")
        self.keywordEdit = QLineEdit(HistoryDialog)
        self.keywordEdit.setObjectName(u"keywordEdit")

        self.searchLayout.addWidget(self.keywordEdit)

        self.stateCombo = QComboBox(HistoryDialog)
        self.stateCombo.setObjectName(u"stateCombo")

        self.searchLayout.addWidget(self.stateCombo)

        self.searchButton = QPushButton(HistoryDialog)
        self.searchButton.setObjectName(u"searchButton")

        self.searchLayout.addWidget(self.searchButton)


        self.mainLayout.addLayout(self.searchLayout)

        self.dateLayout = QHBoxLayout()
        self.dateLayout.setObjectName(u"dateLayout")
        self.dateCheck = QCheckBox(HistoryDialog)
        self.dateCheck.setObjectName(u"dateCheck")

        self.dateLayout.addWidget(self.dateCheck)

        self.startDate = QDateEdit(HistoryDialog)
        self.startDate.setObjectName(u"startDate")
        self.startDate.setCalendarPopup(True)

        self.dateLayout.addWidget(self.startDate)

        self.toLabel = QLabel(HistoryDialog)
        self.toLabel.setObjectName(u"toLabel")

        self.dateLayout.addWidget(self.toLabel)

        self.endDate = QDateEdit(HistoryDialog)
        self.endDate.setObjectName(u"endDate")
        self.endDate.setCalendarPopup(True)

        self.dateLayout.addWidget(self.endDate)

        self.resetButton = QPushButton(HistoryDialog)
        self.resetButton.setObjectName(u"resetButton")

        self.dateLayout.addWidget(self.resetButton)


        self.mainLayout.addLayout(self.dateLayout)

        self.historyTable = QTableWidget(HistoryDialog)
        self.historyTable.setObjectName(u"historyTable")

        self.mainLayout.addWidget(self.historyTable)

        self.selectionLabel = QLabel(HistoryDialog)
        self.selectionLabel.setObjectName(u"selectionLabel")
        self.selectionLabel.setWordWrap(True)

        self.mainLayout.addWidget(self.selectionLabel)

        self.pageLayout = QHBoxLayout()
        self.pageLayout.setObjectName(u"pageLayout")
        self.previousButton = QPushButton(HistoryDialog)
        self.previousButton.setObjectName(u"previousButton")

        self.pageLayout.addWidget(self.previousButton)

        self.pageLabel = QLabel(HistoryDialog)
        self.pageLabel.setObjectName(u"pageLabel")

        self.pageLayout.addWidget(self.pageLabel)

        self.nextButton = QPushButton(HistoryDialog)
        self.nextButton.setObjectName(u"nextButton")

        self.pageLayout.addWidget(self.nextButton)

        self.selectPageButton = QPushButton(HistoryDialog)
        self.selectPageButton.setObjectName(u"selectPageButton")

        self.pageLayout.addWidget(self.selectPageButton)

        self.clearSelectionButton = QPushButton(HistoryDialog)
        self.clearSelectionButton.setObjectName(u"clearSelectionButton")

        self.pageLayout.addWidget(self.clearSelectionButton)


        self.mainLayout.addLayout(self.pageLayout)

        self.actionLayout = QHBoxLayout()
        self.actionLayout.setObjectName(u"actionLayout")
        self.hideSelectedButton = QPushButton(HistoryDialog)
        self.hideSelectedButton.setObjectName(u"hideSelectedButton")

        self.actionLayout.addWidget(self.hideSelectedButton)

        self.restoreSelectedButton = QPushButton(HistoryDialog)
        self.restoreSelectedButton.setObjectName(u"restoreSelectedButton")

        self.actionLayout.addWidget(self.restoreSelectedButton)

        self.hideFilteredButton = QPushButton(HistoryDialog)
        self.hideFilteredButton.setObjectName(u"hideFilteredButton")

        self.actionLayout.addWidget(self.hideFilteredButton)

        self.restoreFilteredButton = QPushButton(HistoryDialog)
        self.restoreFilteredButton.setObjectName(u"restoreFilteredButton")

        self.actionLayout.addWidget(self.restoreFilteredButton)

        self.closeButton = QPushButton(HistoryDialog)
        self.closeButton.setObjectName(u"closeButton")

        self.actionLayout.addWidget(self.closeButton)


        self.mainLayout.addLayout(self.actionLayout)

        self.deleteLayout = QHBoxLayout()
        self.deleteLayout.setObjectName(u"deleteLayout")
        self.deleteSelectedButton = QPushButton(HistoryDialog)
        self.deleteSelectedButton.setObjectName(u"deleteSelectedButton")

        self.deleteLayout.addWidget(self.deleteSelectedButton)

        self.deleteFilteredButton = QPushButton(HistoryDialog)
        self.deleteFilteredButton.setObjectName(u"deleteFilteredButton")

        self.deleteLayout.addWidget(self.deleteFilteredButton)


        self.mainLayout.addLayout(self.deleteLayout)


        self.retranslateUi(HistoryDialog)

        QMetaObject.connectSlotsByName(HistoryDialog)
    # setupUi

    def retranslateUi(self, HistoryDialog):
        HistoryDialog.setWindowTitle(QCoreApplication.translate("HistoryDialog", u"\u5386\u53f2\u8bb0\u5f55\u7ba1\u7406", None))
        self.descriptionLabel.setText(QCoreApplication.translate("HistoryDialog", u"\u7ba1\u7406\u6570\u636e\u5e93\u4e2d\u7684\u5386\u53f2\u5bf9\u8bdd\u3002\u201c\u6c38\u4e45\u5220\u9664\u201d\u4f1a\u79fb\u9664\u539f\u6d88\u606f\u53ca\u5173\u8054\u6587\u4ef6\uff0cAI \u4e0d\u80fd\u518d\u68c0\u7d22\u5b83\uff1b\u201c\u9690\u85cf\u201d\u4ec5\u6536\u8d77\u663e\u793a\uff0c\u53ef\u968f\u65f6\u6062\u590d\u3002\u957f\u671f\u8bb0\u5fc6\u72ec\u7acb\u7ba1\u7406\uff0c\u4e0d\u968f\u6b64\u5904\u5220\u9664\u3002", None))
        self.keywordEdit.setPlaceholderText(QCoreApplication.translate("HistoryDialog", u"\u641c\u7d22\u6d88\u606f\u6587\u5b57\u6216\u9644\u4ef6\u540d\u79f0", None))
        self.searchButton.setText(QCoreApplication.translate("HistoryDialog", u"\u7b5b\u9009", None))
        self.dateCheck.setText(QCoreApplication.translate("HistoryDialog", u"\u6309\u65e5\u671f\u7b5b\u9009", None))
        self.startDate.setDisplayFormat(QCoreApplication.translate("HistoryDialog", u"yyyy-MM-dd", None))
        self.toLabel.setText(QCoreApplication.translate("HistoryDialog", u"\u81f3", None))
        self.endDate.setDisplayFormat(QCoreApplication.translate("HistoryDialog", u"yyyy-MM-dd", None))
        self.resetButton.setText(QCoreApplication.translate("HistoryDialog", u"\u91cd\u7f6e", None))
        self.selectionLabel.setText(QCoreApplication.translate("HistoryDialog", u"\u70b9\u51fb\u5de6\u4fa7\u65b9\u6846\u591a\u9009\uff0c\u53cc\u51fb\u5185\u5bb9\u67e5\u770b\u539f\u6d88\u606f\u3002", None))
        self.previousButton.setText(QCoreApplication.translate("HistoryDialog", u"\u4e0a\u4e00\u9875", None))
        self.nextButton.setText(QCoreApplication.translate("HistoryDialog", u"\u4e0b\u4e00\u9875", None))
        self.selectPageButton.setText(QCoreApplication.translate("HistoryDialog", u"\u5168\u9009\u672c\u9875", None))
        self.clearSelectionButton.setText(QCoreApplication.translate("HistoryDialog", u"\u53d6\u6d88\u52fe\u9009", None))
        self.hideSelectedButton.setText(QCoreApplication.translate("HistoryDialog", u"\u4ec5\u9690\u85cf\u6240\u9009", None))
        self.restoreSelectedButton.setText(QCoreApplication.translate("HistoryDialog", u"\u6062\u590d\u6240\u9009", None))
        self.hideFilteredButton.setText(QCoreApplication.translate("HistoryDialog", u"\u4ec5\u9690\u85cf\u7b5b\u9009\u7ed3\u679c", None))
        self.restoreFilteredButton.setText(QCoreApplication.translate("HistoryDialog", u"\u6062\u590d\u7b5b\u9009\u7ed3\u679c", None))
        self.closeButton.setText(QCoreApplication.translate("HistoryDialog", u"\u5b8c\u6210", None))
        self.deleteSelectedButton.setText(QCoreApplication.translate("HistoryDialog", u"\u6c38\u4e45\u5220\u9664\u6240\u9009", None))
        self.deleteSelectedButton.setStyleSheet(QCoreApplication.translate("HistoryDialog", u"color: #ae3939;", None))
        self.deleteFilteredButton.setText(QCoreApplication.translate("HistoryDialog", u"\u6c38\u4e45\u5220\u9664\u5168\u90e8\u7b5b\u9009\u7ed3\u679c", None))
        self.deleteFilteredButton.setStyleSheet(QCoreApplication.translate("HistoryDialog", u"color: #ae3939;", None))
    # retranslateUi

