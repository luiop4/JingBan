# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'memory_scheme.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QProgressBar,
    QPushButton, QSizePolicy, QTabWidget, QVBoxLayout,
    QWidget)

class Ui_MemorySchemePage(object):
    def setupUi(self, MemorySchemePage):
        if not MemorySchemePage.objectName():
            MemorySchemePage.setObjectName(u"MemorySchemePage")
        self.mainLayout = QVBoxLayout(MemorySchemePage)
        self.mainLayout.setSpacing(12)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(12, -1, 12, -1)
        self.overviewCard = QFrame(MemorySchemePage)
        self.overviewCard.setObjectName(u"overviewCard")
        self.overviewCardLayout = QVBoxLayout(self.overviewCard)
        self.overviewCardLayout.setSpacing(12)
        self.overviewCardLayout.setObjectName(u"overviewCardLayout")
        self.headingLayout = QHBoxLayout()
        self.headingLayout.setSpacing(12)
        self.headingLayout.setObjectName(u"headingLayout")
        self.schemeTitle = QLabel(self.overviewCard)
        self.schemeTitle.setObjectName(u"schemeTitle")
        self.schemeTitle.setWordWrap(True)

        self.headingLayout.addWidget(self.schemeTitle)

        self.stateBadge = QLabel(self.overviewCard)
        self.stateBadge.setObjectName(u"stateBadge")
        self.stateBadge.setWordWrap(True)

        self.headingLayout.addWidget(self.stateBadge)


        self.overviewCardLayout.addLayout(self.headingLayout)

        self.descriptionLabel = QLabel(self.overviewCard)
        self.descriptionLabel.setObjectName(u"descriptionLabel")
        self.descriptionLabel.setWordWrap(True)

        self.overviewCardLayout.addWidget(self.descriptionLabel)

        self.metricsLayout = QHBoxLayout()
        self.metricsLayout.setSpacing(12)
        self.metricsLayout.setObjectName(u"metricsLayout")
        self.totalMetric = QFrame(self.overviewCard)
        self.totalMetric.setObjectName(u"totalMetric")
        self.totalMetricLayout = QVBoxLayout(self.totalMetric)
        self.totalMetricLayout.setSpacing(12)
        self.totalMetricLayout.setObjectName(u"totalMetricLayout")
        self.totalCaption = QLabel(self.totalMetric)
        self.totalCaption.setObjectName(u"totalCaption")
        self.totalCaption.setWordWrap(True)

        self.totalMetricLayout.addWidget(self.totalCaption)

        self.totalValue = QLabel(self.totalMetric)
        self.totalValue.setObjectName(u"totalValue")
        self.totalValue.setWordWrap(True)

        self.totalMetricLayout.addWidget(self.totalValue)


        self.metricsLayout.addWidget(self.totalMetric)

        self.pendingMetric = QFrame(self.overviewCard)
        self.pendingMetric.setObjectName(u"pendingMetric")
        self.pendingMetricLayout = QVBoxLayout(self.pendingMetric)
        self.pendingMetricLayout.setSpacing(12)
        self.pendingMetricLayout.setObjectName(u"pendingMetricLayout")
        self.pendingCaption = QLabel(self.pendingMetric)
        self.pendingCaption.setObjectName(u"pendingCaption")
        self.pendingCaption.setWordWrap(True)

        self.pendingMetricLayout.addWidget(self.pendingCaption)

        self.pendingValue = QLabel(self.pendingMetric)
        self.pendingValue.setObjectName(u"pendingValue")
        self.pendingValue.setWordWrap(True)

        self.pendingMetricLayout.addWidget(self.pendingValue)


        self.metricsLayout.addWidget(self.pendingMetric)

        self.eventsMetric = QFrame(self.overviewCard)
        self.eventsMetric.setObjectName(u"eventsMetric")
        self.eventsMetricLayout = QVBoxLayout(self.eventsMetric)
        self.eventsMetricLayout.setSpacing(12)
        self.eventsMetricLayout.setObjectName(u"eventsMetricLayout")
        self.eventsCaption = QLabel(self.eventsMetric)
        self.eventsCaption.setObjectName(u"eventsCaption")
        self.eventsCaption.setWordWrap(True)

        self.eventsMetricLayout.addWidget(self.eventsCaption)

        self.eventsValue = QLabel(self.eventsMetric)
        self.eventsValue.setObjectName(u"eventsValue")
        self.eventsValue.setWordWrap(True)

        self.eventsMetricLayout.addWidget(self.eventsValue)


        self.metricsLayout.addWidget(self.eventsMetric)


        self.overviewCardLayout.addLayout(self.metricsLayout)

        self.statisticsLabel = QLabel(self.overviewCard)
        self.statisticsLabel.setObjectName(u"statisticsLabel")
        self.statisticsLabel.setWordWrap(True)

        self.overviewCardLayout.addWidget(self.statisticsLabel)

        self.coverageProgress = QProgressBar(self.overviewCard)
        self.coverageProgress.setObjectName(u"coverageProgress")

        self.overviewCardLayout.addWidget(self.coverageProgress)

        self.actionsLayout = QHBoxLayout()
        self.actionsLayout.setSpacing(12)
        self.actionsLayout.setObjectName(u"actionsLayout")
        self.organizeButton = QPushButton(self.overviewCard)
        self.organizeButton.setObjectName(u"organizeButton")

        self.actionsLayout.addWidget(self.organizeButton)

        self.pauseButton = QPushButton(self.overviewCard)
        self.pauseButton.setObjectName(u"pauseButton")

        self.actionsLayout.addWidget(self.pauseButton)

        self.refreshButton = QPushButton(self.overviewCard)
        self.refreshButton.setObjectName(u"refreshButton")

        self.actionsLayout.addWidget(self.refreshButton)


        self.overviewCardLayout.addLayout(self.actionsLayout)

        self.statusLabel = QLabel(self.overviewCard)
        self.statusLabel.setObjectName(u"statusLabel")
        self.statusLabel.setWordWrap(True)

        self.overviewCardLayout.addWidget(self.statusLabel)

        self.lastSuccessLabel = QLabel(self.overviewCard)
        self.lastSuccessLabel.setObjectName(u"lastSuccessLabel")
        self.lastSuccessLabel.setWordWrap(True)

        self.overviewCardLayout.addWidget(self.lastSuccessLabel)


        self.mainLayout.addWidget(self.overviewCard)

        self.detailTabs = QTabWidget(MemorySchemePage)
        self.detailTabs.setObjectName(u"detailTabs")
        self.eventsTab = QWidget()
        self.eventsTab.setObjectName(u"eventsTab")
        self.eventsTabLayout = QVBoxLayout(self.eventsTab)
        self.eventsTabLayout.setSpacing(12)
        self.eventsTabLayout.setObjectName(u"eventsTabLayout")
        self.previewLabel = QLabel(self.eventsTab)
        self.previewLabel.setObjectName(u"previewLabel")
        self.previewLabel.setWordWrap(True)

        self.eventsTabLayout.addWidget(self.previewLabel)

        self.emptyLabel = QLabel(self.eventsTab)
        self.emptyLabel.setObjectName(u"emptyLabel")
        self.emptyLabel.setWordWrap(True)

        self.eventsTabLayout.addWidget(self.emptyLabel)

        self.eventsList = QListWidget(self.eventsTab)
        self.eventsList.setObjectName(u"eventsList")
        self.eventsList.setWordWrap(True)
        self.eventsList.setSpacing(6)
        self.eventsList.setMinimumSize(QSize(0, 220))

        self.eventsTabLayout.addWidget(self.eventsList)

        self.detailTabs.addTab(self.eventsTab, "")
        self.behaviorTab = QWidget()
        self.behaviorTab.setObjectName(u"behaviorTab")
        self.behaviorTabLayout = QVBoxLayout(self.behaviorTab)
        self.behaviorTabLayout.setSpacing(12)
        self.behaviorTabLayout.setObjectName(u"behaviorTabLayout")
        self.recallCard = QFrame(self.behaviorTab)
        self.recallCard.setObjectName(u"recallCard")
        self.recallCardLayout = QVBoxLayout(self.recallCard)
        self.recallCardLayout.setSpacing(12)
        self.recallCardLayout.setObjectName(u"recallCardLayout")
        self.retrievalCheck = QCheckBox(self.recallCard)
        self.retrievalCheck.setObjectName(u"retrievalCheck")

        self.recallCardLayout.addWidget(self.retrievalCheck)

        self.recallHelp = QLabel(self.recallCard)
        self.recallHelp.setObjectName(u"recallHelp")
        self.recallHelp.setWordWrap(True)

        self.recallCardLayout.addWidget(self.recallHelp)


        self.behaviorTabLayout.addWidget(self.recallCard)

        self.automaticCard = QFrame(self.behaviorTab)
        self.automaticCard.setObjectName(u"automaticCard")
        self.automaticCardLayout = QVBoxLayout(self.automaticCard)
        self.automaticCardLayout.setSpacing(12)
        self.automaticCardLayout.setObjectName(u"automaticCardLayout")
        self.automaticCheck = QCheckBox(self.automaticCard)
        self.automaticCheck.setObjectName(u"automaticCheck")

        self.automaticCardLayout.addWidget(self.automaticCheck)

        self.automaticHelp = QLabel(self.automaticCard)
        self.automaticHelp.setObjectName(u"automaticHelp")
        self.automaticHelp.setWordWrap(True)

        self.automaticCardLayout.addWidget(self.automaticHelp)


        self.behaviorTabLayout.addWidget(self.automaticCard)

        self.serviceLabel = QLabel(self.behaviorTab)
        self.serviceLabel.setObjectName(u"serviceLabel")
        self.serviceLabel.setWordWrap(True)

        self.behaviorTabLayout.addWidget(self.serviceLabel)

        self.costLabel = QLabel(self.behaviorTab)
        self.costLabel.setObjectName(u"costLabel")
        self.costLabel.setWordWrap(True)

        self.behaviorTabLayout.addWidget(self.costLabel)

        self.policyLabel = QLabel(self.behaviorTab)
        self.policyLabel.setObjectName(u"policyLabel")
        self.policyLabel.setWordWrap(True)

        self.behaviorTabLayout.addWidget(self.policyLabel)

        self.detailTabs.addTab(self.behaviorTab, "")
        self.storageTab = QWidget()
        self.storageTab.setObjectName(u"storageTab")
        self.storageTabLayout = QVBoxLayout(self.storageTab)
        self.storageTabLayout.setSpacing(12)
        self.storageTabLayout.setObjectName(u"storageTabLayout")
        self.storageCard = QFrame(self.storageTab)
        self.storageCard.setObjectName(u"storageCard")
        self.storageCardLayout = QVBoxLayout(self.storageCard)
        self.storageCardLayout.setSpacing(12)
        self.storageCardLayout.setObjectName(u"storageCardLayout")
        self.storageTitle = QLabel(self.storageCard)
        self.storageTitle.setObjectName(u"storageTitle")
        self.storageTitle.setWordWrap(True)

        self.storageCardLayout.addWidget(self.storageTitle)

        self.storageLabel = QLabel(self.storageCard)
        self.storageLabel.setObjectName(u"storageLabel")
        self.storageLabel.setWordWrap(True)
        self.storageLabel.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.storageCardLayout.addWidget(self.storageLabel)

        self.storageHelp = QLabel(self.storageCard)
        self.storageHelp.setObjectName(u"storageHelp")
        self.storageHelp.setWordWrap(True)

        self.storageCardLayout.addWidget(self.storageHelp)


        self.storageTabLayout.addWidget(self.storageCard)

        self.maintenanceCard = QFrame(self.storageTab)
        self.maintenanceCard.setObjectName(u"maintenanceCard")
        self.maintenanceCardLayout = QVBoxLayout(self.maintenanceCard)
        self.maintenanceCardLayout.setSpacing(12)
        self.maintenanceCardLayout.setObjectName(u"maintenanceCardLayout")
        self.maintenanceTitle = QLabel(self.maintenanceCard)
        self.maintenanceTitle.setObjectName(u"maintenanceTitle")
        self.maintenanceTitle.setWordWrap(True)

        self.maintenanceCardLayout.addWidget(self.maintenanceTitle)

        self.maintenanceHelp = QLabel(self.maintenanceCard)
        self.maintenanceHelp.setObjectName(u"maintenanceHelp")
        self.maintenanceHelp.setWordWrap(True)

        self.maintenanceCardLayout.addWidget(self.maintenanceHelp)

        self.clearIndexButton = QPushButton(self.maintenanceCard)
        self.clearIndexButton.setObjectName(u"clearIndexButton")

        self.maintenanceCardLayout.addWidget(self.clearIndexButton)


        self.storageTabLayout.addWidget(self.maintenanceCard)

        self.detailTabs.addTab(self.storageTab, "")

        self.mainLayout.addWidget(self.detailTabs)


        self.retranslateUi(MemorySchemePage)

        QMetaObject.connectSlotsByName(MemorySchemePage)
    # setupUi

    def retranslateUi(self, MemorySchemePage):
        self.schemeTitle.setText(QCoreApplication.translate("MemorySchemePage", u"\u6807\u51c6\u8bb0\u5fc6", None))
        self.stateBadge.setText(QCoreApplication.translate("MemorySchemePage", u"\u5f85\u547d", None))
        self.descriptionLabel.setText(QCoreApplication.translate("MemorySchemePage", u"\u628a\u804a\u8fc7\u7684\u4e8b\u60c5\u6574\u7406\u6210\u4e8b\u4ef6\uff0c\u7ed3\u5408\u5173\u952e\u8bcd\u548c\u539f\u6587\u627e\u56de\u8fc7\u53bb\u3002", None))
        self.totalCaption.setText(QCoreApplication.translate("MemorySchemePage", u"\u5386\u53f2\u6d88\u606f", None))
        self.totalValue.setText(QCoreApplication.translate("MemorySchemePage", u"0", None))
        self.pendingCaption.setText(QCoreApplication.translate("MemorySchemePage", u"\u5f85\u6574\u7406", None))
        self.pendingValue.setText(QCoreApplication.translate("MemorySchemePage", u"0", None))
        self.eventsCaption.setText(QCoreApplication.translate("MemorySchemePage", u"\u4e8b\u4ef6\u6458\u8981", None))
        self.eventsValue.setText(QCoreApplication.translate("MemorySchemePage", u"0", None))
        self.organizeButton.setText(QCoreApplication.translate("MemorySchemePage", u"\u6574\u7406\u5386\u53f2", None))
        self.pauseButton.setText(QCoreApplication.translate("MemorySchemePage", u"\u6682\u505c", None))
        self.refreshButton.setText(QCoreApplication.translate("MemorySchemePage", u"\u5237\u65b0", None))
        self.previewLabel.setText(QCoreApplication.translate("MemorySchemePage", u"\u6700\u8fd1\u66f4\u65b0\u7684 100 \u6761\u4e8b\u4ef6 \u00b7 \u53cc\u51fb\u67e5\u770b\u72b6\u6001\u53d8\u5316\u4e0e\u6765\u6e90", None))
        self.emptyLabel.setText(QCoreApplication.translate("MemorySchemePage", u"\u8fd8\u6ca1\u6709\u4e8b\u4ef6\u6458\u8981\n"
"\u70b9\u51fb\u201c\u6574\u7406\u5386\u53f2\u201d\uff0c\u4ece\u5df2\u6709\u5bf9\u8bdd\u5f00\u59cb\u5efa\u7acb\u8bb0\u5fc6\u3002", None))
        self.detailTabs.setTabText(self.detailTabs.indexOf(self.eventsTab), QCoreApplication.translate("MemorySchemePage", u"\u4e8b\u4ef6\u6458\u8981", None))
        self.retrievalCheck.setText(QCoreApplication.translate("MemorySchemePage", u"\u4e3b\u52a8\u56de\u5fc6", None))
        self.recallHelp.setText(QCoreApplication.translate("MemorySchemePage", u"\u804a\u5929\u65f6\u67e5\u627e\u76f8\u5173\u4e8b\u4ef6\uff0c\u7ed3\u5408\u6700\u8fd1\u7684\u4e0a\u4e0b\u6587\u7406\u89e3\u201c\u4e0a\u6b21\u201d\u201c\u90a3\u4ef6\u4e8b\u201d\u3002\u5173\u95ed\u540e\u4ecd\u53ef\u67e5\u8be2\u539f\u59cb\u5386\u53f2\u3002", None))
        self.automaticCheck.setText(QCoreApplication.translate("MemorySchemePage", u"\u81ea\u52a8\u6574\u7406\u65b0\u589e\u5bf9\u8bdd", None))
        self.automaticHelp.setText(QCoreApplication.translate("MemorySchemePage", u"\u65b0\u589e\u6d88\u606f\u7d2f\u8ba1 12 \u6761\u540e\uff0c\u5728\u56de\u590d\u7ed3\u675f\u65f6\u540e\u53f0\u6574\u7406\u4e00\u6279\u3002\u65e7\u5386\u53f2\u9700\u8981\u624b\u52a8\u5f00\u59cb\uff1b\u6574\u7406\u4e2d\u53ef\u7ee7\u7eed\u804a\u5929\u3002", None))
        self.costLabel.setText(QCoreApplication.translate("MemorySchemePage", u"\u4e8b\u4ef6\u6574\u7406\u4f1a\u4f7f\u7528\u5f53\u524d\u804a\u5929 API\uff0c\u4ea7\u751f\u989d\u5916 Token \u7528\u91cf\u3002\u65e5\u5e38\u5173\u952e\u8bcd\u68c0\u7d22\u5728\u672c\u673a\u5b8c\u6210\u3002", None))
        self.policyLabel.setText(QCoreApplication.translate("MemorySchemePage", u"\u672c\u5730\u4e0e\u5404\u4e2a QQ \u4f1a\u8bdd\u5206\u522b\u6574\u7406\u3002\u9690\u85cf\u6d88\u606f\u4ecd\u53ef\u56de\u5fc6\uff1b\u6c38\u4e45\u5220\u9664\u6765\u6e90\u6d88\u606f\u4f1a\u79fb\u9664\u76f8\u5173\u4e8b\u4ef6\u6458\u8981\u3002\u957f\u6d88\u606f\u53d6\u524d 1600 \u5b57\u6574\u7406\uff0c\u5b8c\u6574\u539f\u6587\u4ecd\u4fdd\u7559\u3002", None))
        self.detailTabs.setTabText(self.detailTabs.indexOf(self.behaviorTab), QCoreApplication.translate("MemorySchemePage", u"\u56de\u5fc6\u4e0e\u6574\u7406", None))
        self.storageTitle.setText(QCoreApplication.translate("MemorySchemePage", u"\u672c\u673a\u5b58\u50a8 \u00b7 SQLite", None))
        self.storageHelp.setText(QCoreApplication.translate("MemorySchemePage", u"\u804a\u5929\u539f\u6587\u3001\u4e8b\u4ef6\u6458\u8981\u548c\u7d22\u5f15\u968f\u6570\u636e\u5e93\u4e00\u8d77\u5907\u4efd\u4e0e\u8fc1\u79fb\u3002\u5386\u53f2\u8bb0\u5f55\u3001\u72ec\u7acb\u957f\u671f\u8bb0\u5fc6\u4ecd\u5728\u5404\u81ea\u9875\u9762\u7ba1\u7406\u3002", None))
        self.maintenanceTitle.setText(QCoreApplication.translate("MemorySchemePage", u"\u91cd\u65b0\u5efa\u7acb\u4e8b\u4ef6\u8bb0\u5fc6", None))
        self.maintenanceHelp.setText(QCoreApplication.translate("MemorySchemePage", u"\u6e05\u7a7a\u540e\u4fdd\u7559\u804a\u5929\u539f\u6587\u4e0e\u72ec\u7acb\u957f\u671f\u8bb0\u5fc6\uff0c\u5e76\u6682\u505c\u81ea\u52a8\u6574\u7406\u3002\u4e0b\u6b21\u6574\u7406\u4f1a\u91cd\u65b0\u4ea7\u751f API \u7528\u91cf\u3002", None))
        self.clearIndexButton.setText(QCoreApplication.translate("MemorySchemePage", u"\u6e05\u7a7a\u4e8b\u4ef6\u7d22\u5f15\u2026", None))
        self.detailTabs.setTabText(self.detailTabs.indexOf(self.storageTab), QCoreApplication.translate("MemorySchemePage", u"\u5b58\u50a8\u4e0e\u7ef4\u62a4", None))
        pass
    # retranslateUi

