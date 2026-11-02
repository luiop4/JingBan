# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'chat_window.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QFormLayout, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QSpacerItem,
    QSpinBox, QStackedWidget, QToolButton, QVBoxLayout,
    QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.setMinimumSize(QSize(980, 680))
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.rootLayout = QHBoxLayout(self.centralwidget)
        self.rootLayout.setSpacing(0)
        self.rootLayout.setObjectName(u"rootLayout")
        self.rootLayout.setContentsMargins(0, 0, 0, 0)
        self.sidebarFrame = QFrame(self.centralwidget)
        self.sidebarFrame.setObjectName(u"sidebarFrame")
        self.sidebarFrame.setMinimumSize(QSize(220, 0))
        self.sidebarFrame.setMaximumSize(QSize(220, 16777215))
        self.sidebarLayout = QVBoxLayout(self.sidebarFrame)
        self.sidebarLayout.setSpacing(10)
        self.sidebarLayout.setObjectName(u"sidebarLayout")
        self.sidebarLayout.setContentsMargins(16, 20, 16, 16)
        self.brandLayout = QHBoxLayout()
        self.brandLayout.setObjectName(u"brandLayout")
        self.brandMark = QLabel(self.sidebarFrame)
        self.brandMark.setObjectName(u"brandMark")
        self.brandMark.setAlignment(Qt.AlignCenter)

        self.brandLayout.addWidget(self.brandMark)

        self.brandName = QLabel(self.sidebarFrame)
        self.brandName.setObjectName(u"brandName")

        self.brandLayout.addWidget(self.brandName)


        self.sidebarLayout.addLayout(self.brandLayout)

        self.navCaption = QLabel(self.sidebarFrame)
        self.navCaption.setObjectName(u"navCaption")

        self.sidebarLayout.addWidget(self.navCaption)

        self.chatNavButton = QPushButton(self.sidebarFrame)
        self.chatNavButton.setObjectName(u"chatNavButton")
        self.chatNavButton.setCheckable(True)
        self.chatNavButton.setChecked(True)

        self.sidebarLayout.addWidget(self.chatNavButton)

        self.memoryNavButton = QPushButton(self.sidebarFrame)
        self.memoryNavButton.setObjectName(u"memoryNavButton")
        self.memoryNavButton.setCheckable(True)

        self.sidebarLayout.addWidget(self.memoryNavButton)

        self.voiceNavButton = QPushButton(self.sidebarFrame)
        self.voiceNavButton.setObjectName(u"voiceNavButton")
        self.voiceNavButton.setCheckable(True)

        self.sidebarLayout.addWidget(self.voiceNavButton)

        self.qqNavButton = QPushButton(self.sidebarFrame)
        self.qqNavButton.setObjectName(u"qqNavButton")
        self.qqNavButton.setCheckable(True)

        self.sidebarLayout.addWidget(self.qqNavButton)

        self.historyNavButton = QPushButton(self.sidebarFrame)
        self.historyNavButton.setObjectName(u"historyNavButton")
        self.historyNavButton.setCheckable(True)

        self.sidebarLayout.addWidget(self.historyNavButton)

        self.memorySchemeNavButton = QPushButton(self.sidebarFrame)
        self.memorySchemeNavButton.setObjectName(u"memorySchemeNavButton")
        self.memorySchemeNavButton.setCheckable(True)

        self.sidebarLayout.addWidget(self.memorySchemeNavButton)

        self.settingsNavButton = QPushButton(self.sidebarFrame)
        self.settingsNavButton.setObjectName(u"settingsNavButton")
        self.settingsNavButton.setCheckable(True)

        self.sidebarLayout.addWidget(self.settingsNavButton)

        self.pluginNavButton = QPushButton(self.sidebarFrame)
        self.pluginNavButton.setObjectName(u"pluginNavButton")
        self.pluginNavButton.setCheckable(True)

        self.sidebarLayout.addWidget(self.pluginNavButton)

        self.aboutNavButton = QPushButton(self.sidebarFrame)
        self.aboutNavButton.setObjectName(u"aboutNavButton")
        self.aboutNavButton.setCheckable(True)

        self.sidebarLayout.addWidget(self.aboutNavButton)

        self.sideSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.sidebarLayout.addItem(self.sideSpacer)

        self.memoryCard = QFrame(self.sidebarFrame)
        self.memoryCard.setObjectName(u"memoryCard")
        self.memoryCard.setFocusPolicy(Qt.StrongFocus)
        self.memoryCardLayout = QVBoxLayout(self.memoryCard)
        self.memoryCardLayout.setObjectName(u"memoryCardLayout")
        self.memoryTitle = QLabel(self.memoryCard)
        self.memoryTitle.setObjectName(u"memoryTitle")

        self.memoryCardLayout.addWidget(self.memoryTitle)

        self.memoryCountLabel = QLabel(self.memoryCard)
        self.memoryCountLabel.setObjectName(u"memoryCountLabel")

        self.memoryCardLayout.addWidget(self.memoryCountLabel)


        self.sidebarLayout.addWidget(self.memoryCard)

        self.modelStatusLabel = QLabel(self.sidebarFrame)
        self.modelStatusLabel.setObjectName(u"modelStatusLabel")

        self.sidebarLayout.addWidget(self.modelStatusLabel)

        self.profileLabel = QLabel(self.sidebarFrame)
        self.profileLabel.setObjectName(u"profileLabel")

        self.sidebarLayout.addWidget(self.profileLabel)


        self.rootLayout.addWidget(self.sidebarFrame)

        self.mainPanel = QWidget(self.centralwidget)
        self.mainPanel.setObjectName(u"mainPanel")
        self.mainLayout = QVBoxLayout(self.mainPanel)
        self.mainLayout.setSpacing(0)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.headerFrame = QFrame(self.mainPanel)
        self.headerFrame.setObjectName(u"headerFrame")
        self.headerFrame.setMinimumSize(QSize(0, 74))
        self.headerFrame.setMaximumSize(QSize(16777215, 74))
        self.headerLayout = QHBoxLayout(self.headerFrame)
        self.headerLayout.setObjectName(u"headerLayout")
        self.headerLayout.setContentsMargins(28, -1, 28, -1)
        self.titleLayout = QVBoxLayout()
        self.titleLayout.setObjectName(u"titleLayout")
        self.pageTitle = QLabel(self.headerFrame)
        self.pageTitle.setObjectName(u"pageTitle")

        self.titleLayout.addWidget(self.pageTitle)

        self.pageSubtitle = QLabel(self.headerFrame)
        self.pageSubtitle.setObjectName(u"pageSubtitle")

        self.titleLayout.addWidget(self.pageSubtitle)


        self.headerLayout.addLayout(self.titleLayout)

        self.headerSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.headerLayout.addItem(self.headerSpacer)

        self.usageBalanceButton = QPushButton(self.headerFrame)
        self.usageBalanceButton.setObjectName(u"usageBalanceButton")

        self.headerLayout.addWidget(self.usageBalanceButton)

        self.assistantIdentityFrame = QFrame(self.headerFrame)
        self.assistantIdentityFrame.setObjectName(u"assistantIdentityFrame")
        self.assistantIdentityFrame.setFrameShape(QFrame.StyledPanel)
        self.assistantIdentityLayout = QHBoxLayout(self.assistantIdentityFrame)
        self.assistantIdentityLayout.setSpacing(8)
        self.assistantIdentityLayout.setObjectName(u"assistantIdentityLayout")
        self.assistantIdentityLayout.setContentsMargins(7, 5, 12, 5)
        self.headerAssistantAvatar = QLabel(self.assistantIdentityFrame)
        self.headerAssistantAvatar.setObjectName(u"headerAssistantAvatar")
        self.headerAssistantAvatar.setMinimumSize(QSize(34, 34))
        self.headerAssistantAvatar.setMaximumSize(QSize(34, 34))
        self.headerAssistantAvatar.setAlignment(Qt.AlignCenter)

        self.assistantIdentityLayout.addWidget(self.headerAssistantAvatar)

        self.headerAssistantName = QLabel(self.assistantIdentityFrame)
        self.headerAssistantName.setObjectName(u"headerAssistantName")

        self.assistantIdentityLayout.addWidget(self.headerAssistantName)


        self.headerLayout.addWidget(self.assistantIdentityFrame)


        self.mainLayout.addWidget(self.headerFrame)

        self.pageStack = QStackedWidget(self.mainPanel)
        self.pageStack.setObjectName(u"pageStack")
        self.chatPage = QWidget()
        self.chatPage.setObjectName(u"chatPage")
        self.chatPageLayout = QVBoxLayout(self.chatPage)
        self.chatPageLayout.setSpacing(0)
        self.chatPageLayout.setObjectName(u"chatPageLayout")
        self.chatPageLayout.setContentsMargins(0, 0, 0, 0)
        self.chatScroll = QScrollArea(self.chatPage)
        self.chatScroll.setObjectName(u"chatScroll")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.chatScroll.sizePolicy().hasHeightForWidth())
        self.chatScroll.setSizePolicy(sizePolicy)
        self.chatScroll.setWidgetResizable(True)
        self.chatScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chatScroll.setFrameShape(QFrame.NoFrame)
        self.chatMessages = QWidget()
        self.chatMessages.setObjectName(u"chatMessages")
        self.chatMessages.setGeometry(QRect(0, 0, 760, 520))
        self.messageLayout = QVBoxLayout(self.chatMessages)
        self.messageLayout.setSpacing(15)
        self.messageLayout.setObjectName(u"messageLayout")
        self.messageLayout.setContentsMargins(34, 26, 34, 26)
        self.chatScroll.setWidget(self.chatMessages)

        self.chatPageLayout.addWidget(self.chatScroll)

        self.composerWrap = QWidget(self.chatPage)
        self.composerWrap.setObjectName(u"composerWrap")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.composerWrap.sizePolicy().hasHeightForWidth())
        self.composerWrap.setSizePolicy(sizePolicy1)
        self.composerWrapLayout = QVBoxLayout(self.composerWrap)
        self.composerWrapLayout.setSpacing(6)
        self.composerWrapLayout.setObjectName(u"composerWrapLayout")
        self.composerWrapLayout.setContentsMargins(34, 10, 34, 10)
        self.composerFrame = QFrame(self.composerWrap)
        self.composerFrame.setObjectName(u"composerFrame")
        self.composerLayout = QVBoxLayout(self.composerFrame)
        self.composerLayout.setObjectName(u"composerLayout")
        self.composerLayout.setContentsMargins(14, 10, 12, 9)
        self.messageInput = QPlainTextEdit(self.composerFrame)
        self.messageInput.setObjectName(u"messageInput")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.messageInput.sizePolicy().hasHeightForWidth())
        self.messageInput.setSizePolicy(sizePolicy2)
        self.messageInput.setMinimumSize(QSize(0, 58))
        self.messageInput.setMaximumSize(QSize(16777215, 78))

        self.composerLayout.addWidget(self.messageInput)

        self.attachmentSummaryLabel = QLabel(self.composerFrame)
        self.attachmentSummaryLabel.setObjectName(u"attachmentSummaryLabel")
        self.attachmentSummaryLabel.setVisible(False)
        self.attachmentSummaryLabel.setWordWrap(True)

        self.composerLayout.addWidget(self.attachmentSummaryLabel)

        self.toolsLayout = QHBoxLayout()
        self.toolsLayout.setObjectName(u"toolsLayout")
        self.attachButton = QPushButton(self.composerFrame)
        self.attachButton.setObjectName(u"attachButton")
        self.attachButton.setMinimumSize(QSize(0, 32))
        self.attachButton.setMaximumSize(QSize(16777215, 32))

        self.toolsLayout.addWidget(self.attachButton)

        self.stickerLibraryButton = QPushButton(self.composerFrame)
        self.stickerLibraryButton.setObjectName(u"stickerLibraryButton")
        self.stickerLibraryButton.setMinimumSize(QSize(0, 32))
        self.stickerLibraryButton.setMaximumSize(QSize(16777215, 32))

        self.toolsLayout.addWidget(self.stickerLibraryButton)

        self.voiceEnabledCheckBox = QPushButton(self.composerFrame)
        self.voiceEnabledCheckBox.setObjectName(u"voiceEnabledCheckBox")
        self.voiceEnabledCheckBox.setCheckable(True)
        self.voiceEnabledCheckBox.setMinimumSize(QSize(0, 32))
        self.voiceEnabledCheckBox.setMaximumSize(QSize(16777215, 32))

        self.toolsLayout.addWidget(self.voiceEnabledCheckBox)

        self.pauseSpeechButton = QPushButton(self.composerFrame)
        self.pauseSpeechButton.setObjectName(u"pauseSpeechButton")
        self.pauseSpeechButton.setEnabled(False)

        self.toolsLayout.addWidget(self.pauseSpeechButton)

        self.agentMenuButton = QToolButton(self.composerFrame)
        self.agentMenuButton.setObjectName(u"agentMenuButton")
        self.agentMenuButton.setCheckable(True)
        self.agentMenuButton.setMinimumSize(QSize(0, 32))
        self.agentMenuButton.setMaximumSize(QSize(16777215, 32))

        self.toolsLayout.addWidget(self.agentMenuButton)

        self.clearAttachmentsButton = QPushButton(self.composerFrame)
        self.clearAttachmentsButton.setObjectName(u"clearAttachmentsButton")

        self.toolsLayout.addWidget(self.clearAttachmentsButton)

        self.toolsSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.toolsLayout.addItem(self.toolsSpacer)

        self.sendButton = QPushButton(self.composerFrame)
        self.sendButton.setObjectName(u"sendButton")

        self.toolsLayout.addWidget(self.sendButton)


        self.composerLayout.addLayout(self.toolsLayout)


        self.composerWrapLayout.addWidget(self.composerFrame)

        self.footerNote = QLabel(self.composerWrap)
        self.footerNote.setObjectName(u"footerNote")
        self.footerNote.setAlignment(Qt.AlignCenter)

        self.composerWrapLayout.addWidget(self.footerNote)


        self.chatPageLayout.addWidget(self.composerWrap)

        self.pageStack.addWidget(self.chatPage)
        self.memoryPage = QWidget()
        self.memoryPage.setObjectName(u"memoryPage")
        self.memoryContentLayout = QVBoxLayout(self.memoryPage)
        self.memoryContentLayout.setSpacing(14)
        self.memoryContentLayout.setObjectName(u"memoryContentLayout")
        self.memoryContentLayout.setContentsMargins(32, 24, 32, 24)
        self.memoryIntroLabel = QLabel(self.memoryPage)
        self.memoryIntroLabel.setObjectName(u"memoryIntroLabel")
        self.memoryIntroLabel.setWordWrap(True)

        self.memoryContentLayout.addWidget(self.memoryIntroLabel)

        self.autoExtractMemoryCheckBox = QCheckBox(self.memoryPage)
        self.autoExtractMemoryCheckBox.setObjectName(u"autoExtractMemoryCheckBox")

        self.memoryContentLayout.addWidget(self.autoExtractMemoryCheckBox)

        self.memoryToolbar = QHBoxLayout()
        self.memoryToolbar.setObjectName(u"memoryToolbar")
        self.extractMemoryButton = QPushButton(self.memoryPage)
        self.extractMemoryButton.setObjectName(u"extractMemoryButton")

        self.memoryToolbar.addWidget(self.extractMemoryButton)

        self.autoApproveMemoryCheckBox = QCheckBox(self.memoryPage)
        self.autoApproveMemoryCheckBox.setObjectName(u"autoApproveMemoryCheckBox")
        self.autoApproveMemoryCheckBox.setChecked(True)

        self.memoryToolbar.addWidget(self.autoApproveMemoryCheckBox)

        self.memoryToolbarSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.memoryToolbar.addItem(self.memoryToolbarSpacer)

        self.memoryStatusLabel = QLabel(self.memoryPage)
        self.memoryStatusLabel.setObjectName(u"memoryStatusLabel")

        self.memoryToolbar.addWidget(self.memoryStatusLabel)


        self.memoryContentLayout.addLayout(self.memoryToolbar)

        self.memorySearchLayout = QHBoxLayout()
        self.memorySearchLayout.setObjectName(u"memorySearchLayout")
        self.memorySearchEdit = QLineEdit(self.memoryPage)
        self.memorySearchEdit.setObjectName(u"memorySearchEdit")
        self.memorySearchEdit.setClearButtonEnabled(True)

        self.memorySearchLayout.addWidget(self.memorySearchEdit)

        self.memoryFilterCombo = QComboBox(self.memoryPage)
        self.memoryFilterCombo.addItem("")
        self.memoryFilterCombo.addItem("")
        self.memoryFilterCombo.addItem("")
        self.memoryFilterCombo.setObjectName(u"memoryFilterCombo")

        self.memorySearchLayout.addWidget(self.memoryFilterCombo)

        self.refreshMemoryButton = QPushButton(self.memoryPage)
        self.refreshMemoryButton.setObjectName(u"refreshMemoryButton")

        self.memorySearchLayout.addWidget(self.refreshMemoryButton)

        self.newMemoryButton = QPushButton(self.memoryPage)
        self.newMemoryButton.setObjectName(u"newMemoryButton")

        self.memorySearchLayout.addWidget(self.newMemoryButton)

        self.memoryTotalLabel = QLabel(self.memoryPage)
        self.memoryTotalLabel.setObjectName(u"memoryTotalLabel")

        self.memorySearchLayout.addWidget(self.memoryTotalLabel)


        self.memoryContentLayout.addLayout(self.memorySearchLayout)

        self.memoryListWidget = QListWidget(self.memoryPage)
        self.memoryListWidget.setObjectName(u"memoryListWidget")
        self.memoryListWidget.setWordWrap(True)
        self.memoryListWidget.setSpacing(5)
        self.memoryListWidget.setAlternatingRowColors(True)
        self.memoryListWidget.setMinimumSize(QSize(0, 210))

        self.memoryContentLayout.addWidget(self.memoryListWidget)

        self.memoryEditLabel = QLabel(self.memoryPage)
        self.memoryEditLabel.setObjectName(u"memoryEditLabel")

        self.memoryContentLayout.addWidget(self.memoryEditLabel)

        self.memoryDetailsLabel = QLabel(self.memoryPage)
        self.memoryDetailsLabel.setObjectName(u"memoryDetailsLabel")
        self.memoryDetailsLabel.setWordWrap(True)

        self.memoryContentLayout.addWidget(self.memoryDetailsLabel)

        self.memoryEditor = QPlainTextEdit(self.memoryPage)
        self.memoryEditor.setObjectName(u"memoryEditor")
        self.memoryEditor.setMinimumSize(QSize(0, 86))
        self.memoryEditor.setMaximumSize(QSize(16777215, 220))

        self.memoryContentLayout.addWidget(self.memoryEditor)

        self.memoryActions = QHBoxLayout()
        self.memoryActions.setObjectName(u"memoryActions")
        self.addMemoryButton = QPushButton(self.memoryPage)
        self.addMemoryButton.setObjectName(u"addMemoryButton")

        self.memoryActions.addWidget(self.addMemoryButton)

        self.updateMemoryButton = QPushButton(self.memoryPage)
        self.updateMemoryButton.setObjectName(u"updateMemoryButton")

        self.memoryActions.addWidget(self.updateMemoryButton)

        self.approveMemoryButton = QPushButton(self.memoryPage)
        self.approveMemoryButton.setObjectName(u"approveMemoryButton")

        self.memoryActions.addWidget(self.approveMemoryButton)

        self.deleteMemoryButton = QPushButton(self.memoryPage)
        self.deleteMemoryButton.setObjectName(u"deleteMemoryButton")

        self.memoryActions.addWidget(self.deleteMemoryButton)

        self.memoryActionSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.memoryActions.addItem(self.memoryActionSpacer)


        self.memoryContentLayout.addLayout(self.memoryActions)

        self.pageStack.addWidget(self.memoryPage)
        self.voicePage = QWidget()
        self.voicePage.setObjectName(u"voicePage")
        self.voicePageLayout = QVBoxLayout(self.voicePage)
        self.voicePageLayout.setSpacing(12)
        self.voicePageLayout.setObjectName(u"voicePageLayout")
        self.voicePageLayout.setContentsMargins(0, 0, 0, 0)
        self.voiceScroll = QScrollArea(self.voicePage)
        self.voiceScroll.setObjectName(u"voiceScroll")
        self.voiceScroll.setWidgetResizable(True)
        self.voiceScroll.setFrameShape(QFrame.NoFrame)
        self.voiceScrollContent = QWidget()
        self.voiceScrollContent.setObjectName(u"voiceScrollContent")
        self.voiceContentLayout = QVBoxLayout(self.voiceScrollContent)
        self.voiceContentLayout.setSpacing(12)
        self.voiceContentLayout.setObjectName(u"voiceContentLayout")
        self.voiceContentLayout.setContentsMargins(28, 20, 28, 20)
        self.voiceIntroLabel = QLabel(self.voiceScrollContent)
        self.voiceIntroLabel.setObjectName(u"voiceIntroLabel")
        self.voiceIntroLabel.setWordWrap(True)

        self.voiceContentLayout.addWidget(self.voiceIntroLabel)

        self.voiceForm = QFormLayout()
        self.voiceForm.setSpacing(12)
        self.voiceForm.setObjectName(u"voiceForm")
        self.voiceForm.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.voiceProviderLabel = QLabel(self.voiceScrollContent)
        self.voiceProviderLabel.setObjectName(u"voiceProviderLabel")

        self.voiceForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.voiceProviderLabel)

        self.voiceProviderCombo = QComboBox(self.voiceScrollContent)
        self.voiceProviderCombo.setObjectName(u"voiceProviderCombo")

        self.voiceForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.voiceProviderCombo)


        self.voiceContentLayout.addLayout(self.voiceForm)

        self.voiceOnlineGroup = QGroupBox(self.voiceScrollContent)
        self.voiceOnlineGroup.setObjectName(u"voiceOnlineGroup")
        self.voiceOnlineGroupLayout = QVBoxLayout(self.voiceOnlineGroup)
        self.voiceOnlineGroupLayout.setSpacing(12)
        self.voiceOnlineGroupLayout.setObjectName(u"voiceOnlineGroupLayout")
        self.voiceOnlineForm = QFormLayout()
        self.voiceOnlineForm.setSpacing(12)
        self.voiceOnlineForm.setObjectName(u"voiceOnlineForm")
        self.voiceOnlineForm.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.doubaoApiKeyLabel = QLabel(self.voiceOnlineGroup)
        self.doubaoApiKeyLabel.setObjectName(u"doubaoApiKeyLabel")

        self.voiceOnlineForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.doubaoApiKeyLabel)

        self.doubaoApiKeyEdit = QLineEdit(self.voiceOnlineGroup)
        self.doubaoApiKeyEdit.setObjectName(u"doubaoApiKeyEdit")
        self.doubaoApiKeyEdit.setEchoMode(QLineEdit.Password)

        self.voiceOnlineForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.doubaoApiKeyEdit)

        self.doubaoSpeakerLabel = QLabel(self.voiceOnlineGroup)
        self.doubaoSpeakerLabel.setObjectName(u"doubaoSpeakerLabel")

        self.voiceOnlineForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.doubaoSpeakerLabel)

        self.doubaoSpeakerEdit = QLineEdit(self.voiceOnlineGroup)
        self.doubaoSpeakerEdit.setObjectName(u"doubaoSpeakerEdit")

        self.voiceOnlineForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.doubaoSpeakerEdit)

        self.doubaoSpeechRateLabel = QLabel(self.voiceOnlineGroup)
        self.doubaoSpeechRateLabel.setObjectName(u"doubaoSpeechRateLabel")

        self.voiceOnlineForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.doubaoSpeechRateLabel)

        self.doubaoSpeechRateSpin = QSpinBox(self.voiceOnlineGroup)
        self.doubaoSpeechRateSpin.setObjectName(u"doubaoSpeechRateSpin")
        self.doubaoSpeechRateSpin.setMinimum(-50)
        self.doubaoSpeechRateSpin.setMaximum(100)
        self.doubaoSpeechRateSpin.setValue(0)

        self.voiceOnlineForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.doubaoSpeechRateSpin)


        self.voiceOnlineGroupLayout.addLayout(self.voiceOnlineForm)

        self.doubaoHelpLabel = QLabel(self.voiceOnlineGroup)
        self.doubaoHelpLabel.setObjectName(u"doubaoHelpLabel")
        self.doubaoHelpLabel.setWordWrap(True)

        self.voiceOnlineGroupLayout.addWidget(self.doubaoHelpLabel)


        self.voiceContentLayout.addWidget(self.voiceOnlineGroup)

        self.voiceLocalGroup = QGroupBox(self.voiceScrollContent)
        self.voiceLocalGroup.setObjectName(u"voiceLocalGroup")
        self.voiceLocalGroupLayout = QVBoxLayout(self.voiceLocalGroup)
        self.voiceLocalGroupLayout.setSpacing(12)
        self.voiceLocalGroupLayout.setObjectName(u"voiceLocalGroupLayout")
        self.localTtsInfoLabel = QLabel(self.voiceLocalGroup)
        self.localTtsInfoLabel.setObjectName(u"localTtsInfoLabel")
        self.localTtsInfoLabel.setWordWrap(True)

        self.voiceLocalGroupLayout.addWidget(self.localTtsInfoLabel)

        self.localTtsActions = QHBoxLayout()
        self.localTtsActions.setSpacing(12)
        self.localTtsActions.setObjectName(u"localTtsActions")
        self.prepareLocalTtsButton = QPushButton(self.voiceLocalGroup)
        self.prepareLocalTtsButton.setObjectName(u"prepareLocalTtsButton")

        self.localTtsActions.addWidget(self.prepareLocalTtsButton)

        self.cancelLocalTtsButton = QPushButton(self.voiceLocalGroup)
        self.cancelLocalTtsButton.setObjectName(u"cancelLocalTtsButton")

        self.localTtsActions.addWidget(self.cancelLocalTtsButton)

        self.startLocalTtsButton = QPushButton(self.voiceLocalGroup)
        self.startLocalTtsButton.setObjectName(u"startLocalTtsButton")

        self.localTtsActions.addWidget(self.startLocalTtsButton)

        self.removeLocalTtsButton = QPushButton(self.voiceLocalGroup)
        self.removeLocalTtsButton.setObjectName(u"removeLocalTtsButton")

        self.localTtsActions.addWidget(self.removeLocalTtsButton)


        self.voiceLocalGroupLayout.addLayout(self.localTtsActions)

        self.localTtsProgressBar = QProgressBar(self.voiceLocalGroup)
        self.localTtsProgressBar.setObjectName(u"localTtsProgressBar")
        self.localTtsProgressBar.setMinimum(0)
        self.localTtsProgressBar.setMaximum(0)
        self.localTtsProgressBar.setTextVisible(False)

        self.voiceLocalGroupLayout.addWidget(self.localTtsProgressBar)

        self.localTtsLogEdit = QPlainTextEdit(self.voiceLocalGroup)
        self.localTtsLogEdit.setObjectName(u"localTtsLogEdit")
        self.localTtsLogEdit.setReadOnly(True)
        self.localTtsLogEdit.setMinimumSize(QSize(0, 70))
        self.localTtsLogEdit.setMaximumSize(QSize(16777215, 120))

        self.voiceLocalGroupLayout.addWidget(self.localTtsLogEdit)

        self.voiceLocalForm = QFormLayout()
        self.voiceLocalForm.setSpacing(12)
        self.voiceLocalForm.setObjectName(u"voiceLocalForm")
        self.voiceLocalForm.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.voiceReferenceAudioLabel = QLabel(self.voiceLocalGroup)
        self.voiceReferenceAudioLabel.setObjectName(u"voiceReferenceAudioLabel")

        self.voiceLocalForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.voiceReferenceAudioLabel)

        self.voiceReferenceAudioLayout = QHBoxLayout()
        self.voiceReferenceAudioLayout.setObjectName(u"voiceReferenceAudioLayout")
        self.voiceReferenceAudioEdit = QLineEdit(self.voiceLocalGroup)
        self.voiceReferenceAudioEdit.setObjectName(u"voiceReferenceAudioEdit")

        self.voiceReferenceAudioLayout.addWidget(self.voiceReferenceAudioEdit)

        self.voiceBrowseButton = QPushButton(self.voiceLocalGroup)
        self.voiceBrowseButton.setObjectName(u"voiceBrowseButton")

        self.voiceReferenceAudioLayout.addWidget(self.voiceBrowseButton)


        self.voiceLocalForm.setLayout(0, QFormLayout.ItemRole.FieldRole, self.voiceReferenceAudioLayout)

        self.voiceReferenceTextLabel = QLabel(self.voiceLocalGroup)
        self.voiceReferenceTextLabel.setObjectName(u"voiceReferenceTextLabel")

        self.voiceLocalForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.voiceReferenceTextLabel)

        self.voiceReferenceTextEdit = QPlainTextEdit(self.voiceLocalGroup)
        self.voiceReferenceTextEdit.setObjectName(u"voiceReferenceTextEdit")
        self.voiceReferenceTextEdit.setMinimumSize(QSize(0, 64))
        self.voiceReferenceTextEdit.setMaximumSize(QSize(16777215, 86))

        self.voiceLocalForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.voiceReferenceTextEdit)


        self.voiceLocalGroupLayout.addLayout(self.voiceLocalForm)

        self.localReferenceHelpLabel = QLabel(self.voiceLocalGroup)
        self.localReferenceHelpLabel.setObjectName(u"localReferenceHelpLabel")
        self.localReferenceHelpLabel.setWordWrap(True)

        self.voiceLocalGroupLayout.addWidget(self.localReferenceHelpLabel)


        self.voiceContentLayout.addWidget(self.voiceLocalGroup)

        self.voiceAdvancedButton = QPushButton(self.voiceScrollContent)
        self.voiceAdvancedButton.setObjectName(u"voiceAdvancedButton")
        self.voiceAdvancedButton.setCheckable(True)

        self.voiceContentLayout.addWidget(self.voiceAdvancedButton)

        self.voiceOnlineAdvancedGroup = QGroupBox(self.voiceScrollContent)
        self.voiceOnlineAdvancedGroup.setObjectName(u"voiceOnlineAdvancedGroup")
        self.voiceOnlineAdvancedGroupLayout = QVBoxLayout(self.voiceOnlineAdvancedGroup)
        self.voiceOnlineAdvancedGroupLayout.setSpacing(12)
        self.voiceOnlineAdvancedGroupLayout.setObjectName(u"voiceOnlineAdvancedGroupLayout")
        self.voiceOnlineAdvancedForm = QFormLayout()
        self.voiceOnlineAdvancedForm.setSpacing(12)
        self.voiceOnlineAdvancedForm.setObjectName(u"voiceOnlineAdvancedForm")
        self.voiceOnlineAdvancedForm.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.doubaoResourceLabel = QLabel(self.voiceOnlineAdvancedGroup)
        self.doubaoResourceLabel.setObjectName(u"doubaoResourceLabel")

        self.voiceOnlineAdvancedForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.doubaoResourceLabel)

        self.doubaoResourceEdit = QLineEdit(self.voiceOnlineAdvancedGroup)
        self.doubaoResourceEdit.setObjectName(u"doubaoResourceEdit")

        self.voiceOnlineAdvancedForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.doubaoResourceEdit)

        self.doubaoUidLabel = QLabel(self.voiceOnlineAdvancedGroup)
        self.doubaoUidLabel.setObjectName(u"doubaoUidLabel")

        self.voiceOnlineAdvancedForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.doubaoUidLabel)

        self.doubaoUidEdit = QLineEdit(self.voiceOnlineAdvancedGroup)
        self.doubaoUidEdit.setObjectName(u"doubaoUidEdit")

        self.voiceOnlineAdvancedForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.doubaoUidEdit)


        self.voiceOnlineAdvancedGroupLayout.addLayout(self.voiceOnlineAdvancedForm)


        self.voiceContentLayout.addWidget(self.voiceOnlineAdvancedGroup)

        self.voiceLocalAdvancedGroup = QGroupBox(self.voiceScrollContent)
        self.voiceLocalAdvancedGroup.setObjectName(u"voiceLocalAdvancedGroup")
        self.voiceLocalAdvancedGroupLayout = QVBoxLayout(self.voiceLocalAdvancedGroup)
        self.voiceLocalAdvancedGroupLayout.setSpacing(12)
        self.voiceLocalAdvancedGroupLayout.setObjectName(u"voiceLocalAdvancedGroupLayout")
        self.voiceLocalAdvancedForm = QFormLayout()
        self.voiceLocalAdvancedForm.setSpacing(12)
        self.voiceLocalAdvancedForm.setObjectName(u"voiceLocalAdvancedForm")
        self.voiceLocalAdvancedForm.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.voiceEndpointLabel = QLabel(self.voiceLocalAdvancedGroup)
        self.voiceEndpointLabel.setObjectName(u"voiceEndpointLabel")

        self.voiceLocalAdvancedForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.voiceEndpointLabel)

        self.voiceEndpointEdit = QLineEdit(self.voiceLocalAdvancedGroup)
        self.voiceEndpointEdit.setObjectName(u"voiceEndpointEdit")

        self.voiceLocalAdvancedForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.voiceEndpointEdit)

        self.voiceModelLabel = QLabel(self.voiceLocalAdvancedGroup)
        self.voiceModelLabel.setObjectName(u"voiceModelLabel")

        self.voiceLocalAdvancedForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.voiceModelLabel)

        self.voiceModelEdit = QLineEdit(self.voiceLocalAdvancedGroup)
        self.voiceModelEdit.setObjectName(u"voiceModelEdit")

        self.voiceLocalAdvancedForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.voiceModelEdit)


        self.voiceLocalAdvancedGroupLayout.addLayout(self.voiceLocalAdvancedForm)

        self.voiceLocalOptionsWidget = QWidget(self.voiceLocalAdvancedGroup)
        self.voiceLocalOptionsWidget.setObjectName(u"voiceLocalOptionsWidget")
        self.voiceOptionsGrid = QGridLayout(self.voiceLocalOptionsWidget)
        self.voiceOptionsGrid.setObjectName(u"voiceOptionsGrid")
        self.voiceOptionsGrid.setHorizontalSpacing(12)
        self.voiceOptionsGrid.setVerticalSpacing(8)
        self.voiceOptionsGrid.setContentsMargins(0, 0, 0, 0)
        self.voiceLanguageLabel = QLabel(self.voiceLocalOptionsWidget)
        self.voiceLanguageLabel.setObjectName(u"voiceLanguageLabel")

        self.voiceOptionsGrid.addWidget(self.voiceLanguageLabel, 0, 0, 1, 1)

        self.voiceLanguageCombo = QComboBox(self.voiceLocalOptionsWidget)
        self.voiceLanguageCombo.addItem("")
        self.voiceLanguageCombo.addItem("")
        self.voiceLanguageCombo.addItem("")
        self.voiceLanguageCombo.addItem("")
        self.voiceLanguageCombo.addItem("")
        self.voiceLanguageCombo.addItem("")
        self.voiceLanguageCombo.addItem("")
        self.voiceLanguageCombo.addItem("")
        self.voiceLanguageCombo.addItem("")
        self.voiceLanguageCombo.addItem("")
        self.voiceLanguageCombo.addItem("")
        self.voiceLanguageCombo.setObjectName(u"voiceLanguageCombo")

        self.voiceOptionsGrid.addWidget(self.voiceLanguageCombo, 0, 1, 1, 1)

        self.voiceDeviceLabel = QLabel(self.voiceLocalOptionsWidget)
        self.voiceDeviceLabel.setObjectName(u"voiceDeviceLabel")

        self.voiceOptionsGrid.addWidget(self.voiceDeviceLabel, 0, 2, 1, 1)

        self.voiceDeviceCombo = QComboBox(self.voiceLocalOptionsWidget)
        self.voiceDeviceCombo.addItem("")
        self.voiceDeviceCombo.addItem("")
        self.voiceDeviceCombo.addItem("")
        self.voiceDeviceCombo.setObjectName(u"voiceDeviceCombo")

        self.voiceOptionsGrid.addWidget(self.voiceDeviceCombo, 0, 3, 1, 1)

        self.voiceDtypeLabel = QLabel(self.voiceLocalOptionsWidget)
        self.voiceDtypeLabel.setObjectName(u"voiceDtypeLabel")

        self.voiceOptionsGrid.addWidget(self.voiceDtypeLabel, 1, 0, 1, 1)

        self.voiceDtypeCombo = QComboBox(self.voiceLocalOptionsWidget)
        self.voiceDtypeCombo.addItem("")
        self.voiceDtypeCombo.addItem("")
        self.voiceDtypeCombo.addItem("")
        self.voiceDtypeCombo.addItem("")
        self.voiceDtypeCombo.setObjectName(u"voiceDtypeCombo")

        self.voiceOptionsGrid.addWidget(self.voiceDtypeCombo, 1, 1, 1, 1)

        self.voiceSegmentCharsLabel = QLabel(self.voiceLocalOptionsWidget)
        self.voiceSegmentCharsLabel.setObjectName(u"voiceSegmentCharsLabel")

        self.voiceOptionsGrid.addWidget(self.voiceSegmentCharsLabel, 1, 2, 1, 1)

        self.voiceSegmentCharsSpin = QSpinBox(self.voiceLocalOptionsWidget)
        self.voiceSegmentCharsSpin.setObjectName(u"voiceSegmentCharsSpin")
        self.voiceSegmentCharsSpin.setMinimum(20)
        self.voiceSegmentCharsSpin.setMaximum(500)
        self.voiceSegmentCharsSpin.setValue(96)

        self.voiceOptionsGrid.addWidget(self.voiceSegmentCharsSpin, 1, 3, 1, 1)

        self.voiceTemperatureLabel = QLabel(self.voiceLocalOptionsWidget)
        self.voiceTemperatureLabel.setObjectName(u"voiceTemperatureLabel")

        self.voiceOptionsGrid.addWidget(self.voiceTemperatureLabel, 2, 0, 1, 1)

        self.voiceTemperatureSpin = QDoubleSpinBox(self.voiceLocalOptionsWidget)
        self.voiceTemperatureSpin.setObjectName(u"voiceTemperatureSpin")
        self.voiceTemperatureSpin.setDecimals(2)
        self.voiceTemperatureSpin.setMinimum(0.000000000000000)
        self.voiceTemperatureSpin.setMaximum(2.000000000000000)
        self.voiceTemperatureSpin.setSingleStep(0.050000000000000)
        self.voiceTemperatureSpin.setValue(0.700000000000000)

        self.voiceOptionsGrid.addWidget(self.voiceTemperatureSpin, 2, 1, 1, 1)

        self.voiceTopPLabel = QLabel(self.voiceLocalOptionsWidget)
        self.voiceTopPLabel.setObjectName(u"voiceTopPLabel")

        self.voiceOptionsGrid.addWidget(self.voiceTopPLabel, 2, 2, 1, 1)

        self.voiceTopPSpin = QDoubleSpinBox(self.voiceLocalOptionsWidget)
        self.voiceTopPSpin.setObjectName(u"voiceTopPSpin")
        self.voiceTopPSpin.setDecimals(2)
        self.voiceTopPSpin.setMinimum(0.010000000000000)
        self.voiceTopPSpin.setMaximum(1.000000000000000)
        self.voiceTopPSpin.setSingleStep(0.050000000000000)
        self.voiceTopPSpin.setValue(0.800000000000000)

        self.voiceOptionsGrid.addWidget(self.voiceTopPSpin, 2, 3, 1, 1)

        self.voiceTopKLabel = QLabel(self.voiceLocalOptionsWidget)
        self.voiceTopKLabel.setObjectName(u"voiceTopKLabel")

        self.voiceOptionsGrid.addWidget(self.voiceTopKLabel, 3, 0, 1, 1)

        self.voiceTopKSpin = QSpinBox(self.voiceLocalOptionsWidget)
        self.voiceTopKSpin.setObjectName(u"voiceTopKSpin")
        self.voiceTopKSpin.setMinimum(1)
        self.voiceTopKSpin.setMaximum(100)
        self.voiceTopKSpin.setValue(20)

        self.voiceOptionsGrid.addWidget(self.voiceTopKSpin, 3, 1, 1, 1)

        self.voiceRepetitionPenaltyLabel = QLabel(self.voiceLocalOptionsWidget)
        self.voiceRepetitionPenaltyLabel.setObjectName(u"voiceRepetitionPenaltyLabel")

        self.voiceOptionsGrid.addWidget(self.voiceRepetitionPenaltyLabel, 3, 2, 1, 1)

        self.voiceRepetitionPenaltySpin = QDoubleSpinBox(self.voiceLocalOptionsWidget)
        self.voiceRepetitionPenaltySpin.setObjectName(u"voiceRepetitionPenaltySpin")
        self.voiceRepetitionPenaltySpin.setDecimals(2)
        self.voiceRepetitionPenaltySpin.setMinimum(0.500000000000000)
        self.voiceRepetitionPenaltySpin.setMaximum(2.000000000000000)
        self.voiceRepetitionPenaltySpin.setSingleStep(0.050000000000000)
        self.voiceRepetitionPenaltySpin.setValue(1.050000000000000)

        self.voiceOptionsGrid.addWidget(self.voiceRepetitionPenaltySpin, 3, 3, 1, 1)

        self.voiceMaxTokensLabel = QLabel(self.voiceLocalOptionsWidget)
        self.voiceMaxTokensLabel.setObjectName(u"voiceMaxTokensLabel")

        self.voiceOptionsGrid.addWidget(self.voiceMaxTokensLabel, 4, 0, 1, 1)

        self.voiceMaxTokensSpin = QSpinBox(self.voiceLocalOptionsWidget)
        self.voiceMaxTokensSpin.setObjectName(u"voiceMaxTokensSpin")
        self.voiceMaxTokensSpin.setMinimum(64)
        self.voiceMaxTokensSpin.setMaximum(4096)
        self.voiceMaxTokensSpin.setSingleStep(128)
        self.voiceMaxTokensSpin.setValue(512)

        self.voiceOptionsGrid.addWidget(self.voiceMaxTokensSpin, 4, 1, 1, 1)


        self.voiceLocalAdvancedGroupLayout.addWidget(self.voiceLocalOptionsWidget)


        self.voiceContentLayout.addWidget(self.voiceLocalAdvancedGroup)

        self.voiceActions = QHBoxLayout()
        self.voiceActions.setSpacing(12)
        self.voiceActions.setObjectName(u"voiceActions")
        self.saveVoiceButton = QPushButton(self.voiceScrollContent)
        self.saveVoiceButton.setObjectName(u"saveVoiceButton")

        self.voiceActions.addWidget(self.saveVoiceButton)

        self.testVoiceButton = QPushButton(self.voiceScrollContent)
        self.testVoiceButton.setObjectName(u"testVoiceButton")

        self.voiceActions.addWidget(self.testVoiceButton)

        self.pauseVoicePageButton = QPushButton(self.voiceScrollContent)
        self.pauseVoicePageButton.setObjectName(u"pauseVoicePageButton")
        self.pauseVoicePageButton.setEnabled(False)

        self.voiceActions.addWidget(self.pauseVoicePageButton)


        self.voiceContentLayout.addLayout(self.voiceActions)

        self.voiceStatusLabel = QLabel(self.voiceScrollContent)
        self.voiceStatusLabel.setObjectName(u"voiceStatusLabel")
        self.voiceStatusLabel.setWordWrap(True)

        self.voiceContentLayout.addWidget(self.voiceStatusLabel)

        self.voiceBottomSpacer = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.voiceContentLayout.addItem(self.voiceBottomSpacer)

        self.voiceScroll.setWidget(self.voiceScrollContent)

        self.voicePageLayout.addWidget(self.voiceScroll)

        self.pageStack.addWidget(self.voicePage)
        self.qqPage = QWidget()
        self.qqPage.setObjectName(u"qqPage")
        self.qqOuterLayout = QVBoxLayout(self.qqPage)
        self.qqOuterLayout.setObjectName(u"qqOuterLayout")
        self.qqScroll = QScrollArea(self.qqPage)
        self.qqScroll.setObjectName(u"qqScroll")
        self.qqScroll.setWidgetResizable(True)
        self.qqScroll.setFrameShape(QFrame.NoFrame)
        self.qqScrollContent = QWidget()
        self.qqScrollContent.setObjectName(u"qqScrollContent")
        self.qqContentLayout = QVBoxLayout(self.qqScrollContent)
        self.qqContentLayout.setSpacing(13)
        self.qqContentLayout.setObjectName(u"qqContentLayout")
        self.qqContentLayout.setContentsMargins(34, 26, 34, 26)
        self.qqIntroLabel = QLabel(self.qqScrollContent)
        self.qqIntroLabel.setObjectName(u"qqIntroLabel")
        self.qqIntroLabel.setWordWrap(True)

        self.qqContentLayout.addWidget(self.qqIntroLabel)

        self.onebotContainer = QWidget(self.qqScrollContent)
        self.onebotContainer.setObjectName(u"onebotContainer")
        self.onebotLayout = QVBoxLayout(self.onebotContainer)
        self.onebotLayout.setObjectName(u"onebotLayout")
        self.onebotLayout.setContentsMargins(0, 0, 0, 0)

        self.qqContentLayout.addWidget(self.onebotContainer)

        self.qqConnectionCard = QGroupBox(self.qqScrollContent)
        self.qqConnectionCard.setObjectName(u"qqConnectionCard")
        self.qqConnectionCardLayout = QVBoxLayout(self.qqConnectionCard)
        self.qqConnectionCardLayout.setObjectName(u"qqConnectionCardLayout")
        self.qqForm = QFormLayout()
        self.qqForm.setObjectName(u"qqForm")
        self.qqUrlLabel = QLabel(self.qqConnectionCard)
        self.qqUrlLabel.setObjectName(u"qqUrlLabel")

        self.qqForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.qqUrlLabel)

        self.qqUrlEdit = QLineEdit(self.qqConnectionCard)
        self.qqUrlEdit.setObjectName(u"qqUrlEdit")

        self.qqForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.qqUrlEdit)

        self.qqTokenLabel = QLabel(self.qqConnectionCard)
        self.qqTokenLabel.setObjectName(u"qqTokenLabel")

        self.qqForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.qqTokenLabel)

        self.qqTokenEdit = QLineEdit(self.qqConnectionCard)
        self.qqTokenEdit.setObjectName(u"qqTokenEdit")
        self.qqTokenEdit.setEchoMode(QLineEdit.Password)

        self.qqForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.qqTokenEdit)

        self.qqAllowlistLabel = QLabel(self.qqConnectionCard)
        self.qqAllowlistLabel.setObjectName(u"qqAllowlistLabel")

        self.qqForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.qqAllowlistLabel)

        self.qqAllowlistEdit = QLineEdit(self.qqConnectionCard)
        self.qqAllowlistEdit.setObjectName(u"qqAllowlistEdit")

        self.qqForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.qqAllowlistEdit)


        self.qqConnectionCardLayout.addLayout(self.qqForm)


        self.qqContentLayout.addWidget(self.qqConnectionCard)

        self.qqReplyCard = QGroupBox(self.qqScrollContent)
        self.qqReplyCard.setObjectName(u"qqReplyCard")
        self.qqReplyCardLayout = QVBoxLayout(self.qqReplyCard)
        self.qqReplyCardLayout.setObjectName(u"qqReplyCardLayout")
        self.qqAutoReplyCheckBox = QCheckBox(self.qqReplyCard)
        self.qqAutoReplyCheckBox.setObjectName(u"qqAutoReplyCheckBox")

        self.qqReplyCardLayout.addWidget(self.qqAutoReplyCheckBox)

        self.qqStickerCheckBox = QCheckBox(self.qqReplyCard)
        self.qqStickerCheckBox.setObjectName(u"qqStickerCheckBox")

        self.qqReplyCardLayout.addWidget(self.qqStickerCheckBox)

        self.qqVoiceCheckBox = QCheckBox(self.qqReplyCard)
        self.qqVoiceCheckBox.setObjectName(u"qqVoiceCheckBox")

        self.qqReplyCardLayout.addWidget(self.qqVoiceCheckBox)


        self.qqContentLayout.addWidget(self.qqReplyCard)

        self.qqManualCard = QGroupBox(self.qqScrollContent)
        self.qqManualCard.setObjectName(u"qqManualCard")
        self.qqManualCardLayout = QVBoxLayout(self.qqManualCard)
        self.qqManualCardLayout.setObjectName(u"qqManualCardLayout")
        self.qqManualLayout = QHBoxLayout()
        self.qqManualLayout.setObjectName(u"qqManualLayout")
        self.qqRecipientEdit = QLineEdit(self.qqManualCard)
        self.qqRecipientEdit.setObjectName(u"qqRecipientEdit")

        self.qqManualLayout.addWidget(self.qqRecipientEdit)

        self.qqSendImageButton = QPushButton(self.qqManualCard)
        self.qqSendImageButton.setObjectName(u"qqSendImageButton")

        self.qqManualLayout.addWidget(self.qqSendImageButton)

        self.qqSendVoiceButton = QPushButton(self.qqManualCard)
        self.qqSendVoiceButton.setObjectName(u"qqSendVoiceButton")

        self.qqManualLayout.addWidget(self.qqSendVoiceButton)


        self.qqManualCardLayout.addLayout(self.qqManualLayout)


        self.qqContentLayout.addWidget(self.qqManualCard)

        self.qqActions = QHBoxLayout()
        self.qqActions.setObjectName(u"qqActions")
        self.saveQqButton = QPushButton(self.qqScrollContent)
        self.saveQqButton.setObjectName(u"saveQqButton")

        self.qqActions.addWidget(self.saveQqButton)

        self.qqConnectButton = QPushButton(self.qqScrollContent)
        self.qqConnectButton.setObjectName(u"qqConnectButton")

        self.qqActions.addWidget(self.qqConnectButton)

        self.qqStatusLabel = QLabel(self.qqScrollContent)
        self.qqStatusLabel.setObjectName(u"qqStatusLabel")

        self.qqActions.addWidget(self.qqStatusLabel)

        self.qqActionsSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.qqActions.addItem(self.qqActionsSpacer)


        self.qqContentLayout.addLayout(self.qqActions)

        self.qqSafetyNote = QLabel(self.qqScrollContent)
        self.qqSafetyNote.setObjectName(u"qqSafetyNote")
        self.qqSafetyNote.setWordWrap(True)

        self.qqContentLayout.addWidget(self.qqSafetyNote)

        self.qqBottomSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.qqContentLayout.addItem(self.qqBottomSpacer)

        self.qqScroll.setWidget(self.qqScrollContent)

        self.qqOuterLayout.addWidget(self.qqScroll)

        self.pageStack.addWidget(self.qqPage)
        self.settingsPage = QWidget()
        self.settingsPage.setObjectName(u"settingsPage")
        self.settingsContentLayout = QVBoxLayout(self.settingsPage)
        self.settingsContentLayout.setSpacing(13)
        self.settingsContentLayout.setObjectName(u"settingsContentLayout")
        self.settingsContentLayout.setContentsMargins(34, 26, 34, 26)
        self.settingsIntroLabel = QLabel(self.settingsPage)
        self.settingsIntroLabel.setObjectName(u"settingsIntroLabel")
        self.settingsIntroLabel.setWordWrap(True)

        self.settingsContentLayout.addWidget(self.settingsIntroLabel)

        self.assistantDisplaySection = QLabel(self.settingsPage)
        self.assistantDisplaySection.setObjectName(u"assistantDisplaySection")

        self.settingsContentLayout.addWidget(self.assistantDisplaySection)

        self.assistantDisplayForm = QFormLayout()
        self.assistantDisplayForm.setObjectName(u"assistantDisplayForm")
        self.assistantNameLabel = QLabel(self.settingsPage)
        self.assistantNameLabel.setObjectName(u"assistantNameLabel")

        self.assistantDisplayForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.assistantNameLabel)

        self.assistantNameEdit = QLineEdit(self.settingsPage)
        self.assistantNameEdit.setObjectName(u"assistantNameEdit")

        self.assistantDisplayForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.assistantNameEdit)

        self.assistantAvatarLabel = QLabel(self.settingsPage)
        self.assistantAvatarLabel.setObjectName(u"assistantAvatarLabel")

        self.assistantDisplayForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.assistantAvatarLabel)

        self.assistantAvatarLayout = QHBoxLayout()
        self.assistantAvatarLayout.setObjectName(u"assistantAvatarLayout")
        self.assistantAvatarPreview = QLabel(self.settingsPage)
        self.assistantAvatarPreview.setObjectName(u"assistantAvatarPreview")
        self.assistantAvatarPreview.setMinimumSize(QSize(44, 44))
        self.assistantAvatarPreview.setMaximumSize(QSize(44, 44))
        self.assistantAvatarPreview.setAlignment(Qt.AlignCenter)

        self.assistantAvatarLayout.addWidget(self.assistantAvatarPreview)

        self.assistantAvatarEdit = QLineEdit(self.settingsPage)
        self.assistantAvatarEdit.setObjectName(u"assistantAvatarEdit")

        self.assistantAvatarLayout.addWidget(self.assistantAvatarEdit)

        self.assistantAvatarBrowseButton = QPushButton(self.settingsPage)
        self.assistantAvatarBrowseButton.setObjectName(u"assistantAvatarBrowseButton")

        self.assistantAvatarLayout.addWidget(self.assistantAvatarBrowseButton)

        self.assistantAvatarResetButton = QPushButton(self.settingsPage)
        self.assistantAvatarResetButton.setObjectName(u"assistantAvatarResetButton")

        self.assistantAvatarLayout.addWidget(self.assistantAvatarResetButton)


        self.assistantDisplayForm.setLayout(1, QFormLayout.ItemRole.FieldRole, self.assistantAvatarLayout)


        self.settingsContentLayout.addLayout(self.assistantDisplayForm)

        self.settingsForm = QFormLayout()
        self.settingsForm.setObjectName(u"settingsForm")
        self.apiBaseUrlLabel = QLabel(self.settingsPage)
        self.apiBaseUrlLabel.setObjectName(u"apiBaseUrlLabel")

        self.settingsForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.apiBaseUrlLabel)

        self.apiBaseUrlEdit = QLineEdit(self.settingsPage)
        self.apiBaseUrlEdit.setObjectName(u"apiBaseUrlEdit")

        self.settingsForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.apiBaseUrlEdit)

        self.apiKeyLabel = QLabel(self.settingsPage)
        self.apiKeyLabel.setObjectName(u"apiKeyLabel")

        self.settingsForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.apiKeyLabel)

        self.apiKeyEdit = QLineEdit(self.settingsPage)
        self.apiKeyEdit.setObjectName(u"apiKeyEdit")
        self.apiKeyEdit.setEchoMode(QLineEdit.Password)

        self.settingsForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.apiKeyEdit)

        self.showApiKeySpacerLabel = QLabel(self.settingsPage)
        self.showApiKeySpacerLabel.setObjectName(u"showApiKeySpacerLabel")

        self.settingsForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.showApiKeySpacerLabel)

        self.showApiKeyCheckBox = QCheckBox(self.settingsPage)
        self.showApiKeyCheckBox.setObjectName(u"showApiKeyCheckBox")

        self.settingsForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.showApiKeyCheckBox)

        self.modelLabel = QLabel(self.settingsPage)
        self.modelLabel.setObjectName(u"modelLabel")

        self.settingsForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.modelLabel)

        self.modelEdit = QLineEdit(self.settingsPage)
        self.modelEdit.setObjectName(u"modelEdit")

        self.settingsForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.modelEdit)

        self.thinkingEnabledCheckBox = QCheckBox(self.settingsPage)
        self.thinkingEnabledCheckBox.setObjectName(u"thinkingEnabledCheckBox")

        self.settingsForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.thinkingEnabledCheckBox)


        self.settingsContentLayout.addLayout(self.settingsForm)

        self.systemPromptLabel = QLabel(self.settingsPage)
        self.systemPromptLabel.setObjectName(u"systemPromptLabel")

        self.settingsContentLayout.addWidget(self.systemPromptLabel)

        self.systemPromptEdit = QPlainTextEdit(self.settingsPage)
        self.systemPromptEdit.setObjectName(u"systemPromptEdit")
        self.systemPromptEdit.setMinimumSize(QSize(0, 112))
        self.systemPromptEdit.setMaximumSize(QSize(16777215, 150))

        self.settingsContentLayout.addWidget(self.systemPromptEdit)

        self.settingsActions = QHBoxLayout()
        self.settingsActions.setObjectName(u"settingsActions")
        self.saveSettingsButton = QPushButton(self.settingsPage)
        self.saveSettingsButton.setObjectName(u"saveSettingsButton")

        self.settingsActions.addWidget(self.saveSettingsButton)

        self.settingsStatusLabel = QLabel(self.settingsPage)
        self.settingsStatusLabel.setObjectName(u"settingsStatusLabel")

        self.settingsActions.addWidget(self.settingsStatusLabel)

        self.settingsActionsSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.settingsActions.addItem(self.settingsActionsSpacer)


        self.settingsContentLayout.addLayout(self.settingsActions)

        self.voiceHistoryLayout = QHBoxLayout()
        self.voiceHistoryLayout.setObjectName(u"voiceHistoryLayout")
        self.voiceHistoryLabel = QLabel(self.settingsPage)
        self.voiceHistoryLabel.setObjectName(u"voiceHistoryLabel")

        self.voiceHistoryLayout.addWidget(self.voiceHistoryLabel)

        self.voiceHistorySpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.voiceHistoryLayout.addItem(self.voiceHistorySpacer)

        self.clearVoiceHistoryButton = QPushButton(self.settingsPage)
        self.clearVoiceHistoryButton.setObjectName(u"clearVoiceHistoryButton")

        self.voiceHistoryLayout.addWidget(self.clearVoiceHistoryButton)


        self.settingsContentLayout.addLayout(self.voiceHistoryLayout)

        self.dataMigrationButton = QPushButton(self.settingsPage)
        self.dataMigrationButton.setObjectName(u"dataMigrationButton")

        self.settingsContentLayout.addWidget(self.dataMigrationButton)

        self.clearAllDataButton = QPushButton(self.settingsPage)
        self.clearAllDataButton.setObjectName(u"clearAllDataButton")

        self.settingsContentLayout.addWidget(self.clearAllDataButton)

        self.clearAllDataHelp = QLabel(self.settingsPage)
        self.clearAllDataHelp.setObjectName(u"clearAllDataHelp")
        self.clearAllDataHelp.setWordWrap(True)

        self.settingsContentLayout.addWidget(self.clearAllDataHelp)

        self.settingsBottomSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.settingsContentLayout.addItem(self.settingsBottomSpacer)

        self.pageStack.addWidget(self.settingsPage)
        self.historyPage = QWidget()
        self.historyPage.setObjectName(u"historyPage")
        self.historyPageLayout = QVBoxLayout(self.historyPage)
        self.historyPageLayout.setObjectName(u"historyPageLayout")
        self.pageStack.addWidget(self.historyPage)
        self.memorySchemeContainer = QWidget()
        self.memorySchemeContainer.setObjectName(u"memorySchemeContainer")
        self.memorySchemeLayout = QVBoxLayout(self.memorySchemeContainer)
        self.memorySchemeLayout.setObjectName(u"memorySchemeLayout")
        self.pageStack.addWidget(self.memorySchemeContainer)
        self.aboutContainer = QWidget()
        self.aboutContainer.setObjectName(u"aboutContainer")
        self.aboutPageLayout = QVBoxLayout(self.aboutContainer)
        self.aboutPageLayout.setObjectName(u"aboutPageLayout")
        self.aboutPageLayout.setContentsMargins(0, 0, 0, 0)
        self.pageStack.addWidget(self.aboutContainer)
        self.pluginContainer = QWidget()
        self.pluginContainer.setObjectName(u"pluginContainer")
        self.pluginPageLayout = QVBoxLayout(self.pluginContainer)
        self.pluginPageLayout.setObjectName(u"pluginPageLayout")
        self.pluginPageLayout.setContentsMargins(20, 16, 20, 16)
        self.pageStack.addWidget(self.pluginContainer)

        self.mainLayout.addWidget(self.pageStack)


        self.rootLayout.addWidget(self.mainPanel)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        self.pageStack.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"\u9cb8\u4f34 \u00b7 \u6709\u8bb0\u5fc6\u7684\u966a\u4f34", None))
        self.brandMark.setText(QCoreApplication.translate("MainWindow", u"\u2726", None))
        self.brandName.setText(QCoreApplication.translate("MainWindow", u"\u9cb8\u4f34", None))
        self.navCaption.setText(QCoreApplication.translate("MainWindow", u"\u529f\u80fd", None))
        self.chatNavButton.setText(QCoreApplication.translate("MainWindow", u"\u5bf9\u8bdd", None))
        self.memoryNavButton.setText(QCoreApplication.translate("MainWindow", u"\u957f\u671f\u8bb0\u5fc6", None))
        self.voiceNavButton.setText(QCoreApplication.translate("MainWindow", u"\u8bed\u97f3\u5408\u6210", None))
        self.qqNavButton.setText(QCoreApplication.translate("MainWindow", u"QQ \u63a5\u5165", None))
        self.historyNavButton.setText(QCoreApplication.translate("MainWindow", u"\u5386\u53f2\u8bb0\u5f55", None))
        self.memorySchemeNavButton.setText(QCoreApplication.translate("MainWindow", u"\u8bb0\u5fc6\u65b9\u6848", None))
        self.settingsNavButton.setText(QCoreApplication.translate("MainWindow", u"\u8bbe\u7f6e", None))
        self.pluginNavButton.setText(QCoreApplication.translate("MainWindow", u"\u63d2\u4ef6", None))
        self.aboutNavButton.setText(QCoreApplication.translate("MainWindow", u"\u5173\u4e8e", None))
#if QT_CONFIG(tooltip)
        self.memoryCard.setToolTip(QCoreApplication.translate("MainWindow", u"\u70b9\u51fb\u67e5\u770b\u957f\u671f\u8bb0\u5fc6", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.memoryCard.setAccessibleName(QCoreApplication.translate("MainWindow", u"\u67e5\u770b\u957f\u671f\u8bb0\u5fc6", None))
#endif // QT_CONFIG(accessibility)
        self.memoryTitle.setText(QCoreApplication.translate("MainWindow", u"\u8bb0\u5fc6\u72b6\u6001 \u203a", None))
        self.memoryCountLabel.setText(QCoreApplication.translate("MainWindow", u"\u5df2\u786e\u8ba4 0 \u6761", None))
        self.modelStatusLabel.setText(QCoreApplication.translate("MainWindow", u"\u25cf DeepSeek \u00b7 \u5c1a\u672a\u914d\u7f6e", None))
        self.profileLabel.setText(QCoreApplication.translate("MainWindow", u"\u672c\u5730\u6570\u636e\u4fdd\u5b58\u5728\u6b64\u8bbe\u5907", None))
        self.pageTitle.setText(QCoreApplication.translate("MainWindow", u"\u5bf9\u8bdd", None))
        self.pageSubtitle.setText(QCoreApplication.translate("MainWindow", u"\u4e0e AI \u52a9\u624b\u6301\u7eed\u4ea4\u6d41\uff0c\u6d88\u606f\u4fdd\u5b58\u5728\u672c\u673a", None))
#if QT_CONFIG(tooltip)
        self.usageBalanceButton.setToolTip(QCoreApplication.translate("MainWindow", u"\u67e5\u770b\u672c\u5730 Token \u7528\u91cf\u5e76\u67e5\u8be2 DeepSeek \u4f59\u989d", None))
#endif // QT_CONFIG(tooltip)
        self.usageBalanceButton.setText(QCoreApplication.translate("MainWindow", u"\u7528\u91cf 0", None))
        self.headerAssistantName.setText(QCoreApplication.translate("MainWindow", u"AI \u52a9\u624b", None))
        self.messageInput.setPlaceholderText(QCoreApplication.translate("MainWindow", u"\u8f93\u5165\u6d88\u606f\uff08Ctrl + Enter \u53d1\u9001\uff09", None))
        self.attachmentSummaryLabel.setText("")
#if QT_CONFIG(tooltip)
        self.attachButton.setToolTip(QCoreApplication.translate("MainWindow", u"\u6dfb\u52a0\u56fe\u7247\u6216\u6587\u6863", None))
#endif // QT_CONFIG(tooltip)
        self.attachButton.setText(QCoreApplication.translate("MainWindow", u"\u9644\u4ef6", None))
#if QT_CONFIG(tooltip)
        self.stickerLibraryButton.setToolTip(QCoreApplication.translate("MainWindow", u"\u7ba1\u7406 AI \u53ef\u4ee5\u53d1\u9001\u7684\u672c\u5730\u8868\u60c5\u56fe\u7247", None))
#endif // QT_CONFIG(tooltip)
        self.stickerLibraryButton.setText(QCoreApplication.translate("MainWindow", u"\u8868\u60c5", None))
#if QT_CONFIG(tooltip)
        self.voiceEnabledCheckBox.setToolTip(QCoreApplication.translate("MainWindow", u"\u5f00\u542f\u540e\uff0cAI \u56de\u590d\u4f1a\u5728\u751f\u6210\u65f6\u5408\u6210\u5e76\u64ad\u653e\u8bed\u97f3", None))
#endif // QT_CONFIG(tooltip)
        self.voiceEnabledCheckBox.setText(QCoreApplication.translate("MainWindow", u"\u8bed\u97f3\u56de\u590d", None))
        self.pauseSpeechButton.setText(QCoreApplication.translate("MainWindow", u"\u6682\u505c\u8bed\u97f3", None))
#if QT_CONFIG(tooltip)
        self.pauseSpeechButton.setToolTip(QCoreApplication.translate("MainWindow", u"\u6682\u505c\u64ad\u653e\u5e76\u4e2d\u65ad\u5f53\u524d\u8bed\u97f3\u8bf7\u6c42\uff1b\u7ee7\u7eed\u65f6\u91cd\u65b0\u5408\u6210\u672a\u5b8c\u6210\u7684\u77ed\u53e5\uff0c\u8be5\u53e5\u53ef\u80fd\u90e8\u5206\u91cd\u590d\u3002", None))
#endif // QT_CONFIG(tooltip)
        self.agentMenuButton.setText(QCoreApplication.translate("MainWindow", u"\u7535\u8111\u64cd\u4f5c", None))
#if QT_CONFIG(tooltip)
        self.agentMenuButton.setToolTip(QCoreApplication.translate("MainWindow", u"\u542f\u7528\u540e AI \u53ef\u63d0\u51fa PowerShell \u547d\u4ee4\uff1b\u6bcf\u6b21\u987b\u786e\u8ba4\u3002\u4ec5\u9650\u672c\u673a\u804a\u5929\uff0c\u4e0d\u5411 QQ \u5f00\u653e\u3002", None))
#endif // QT_CONFIG(tooltip)
        self.clearAttachmentsButton.setText(QCoreApplication.translate("MainWindow", u"\u6e05\u9664", None))
        self.sendButton.setText(QCoreApplication.translate("MainWindow", u"\u53d1\u9001", None))
        self.footerNote.setText(QCoreApplication.translate("MainWindow", u"API \u5bc6\u94a5\u5728\u300c\u8bbe\u7f6e\u300d\u9875\u914d\u7f6e\uff1bQQ \u81ea\u52a8\u56de\u590d\u9ed8\u8ba4\u5173\u95ed\u3002", None))
        self.memoryIntroLabel.setText(QCoreApplication.translate("MainWindow", u"\u7ba1\u7406\u5168\u90e8\u957f\u671f\u8bb0\u5fc6\u3002\u9009\u4e2d\u6761\u76ee\u53ef\u67e5\u770b\u4e0e\u4fee\u6539\uff1b\u624b\u52a8\u4fee\u8ba2\u540e\u4f1a\u72ec\u7acb\u4fdd\u7559\u3002\u6b64\u5904\u7ba1\u7406\u7684\u662f\u957f\u671f\u8bb0\u5fc6\uff0c\u539f\u59cb\u5bf9\u8bdd\u8bf7\u5230\u201c\u5386\u53f2\u8bb0\u5f55\u201d\u67e5\u770b\u3002", None))
        self.autoExtractMemoryCheckBox.setText(QCoreApplication.translate("MainWindow", u"\u968f\u6807\u51c6\u8bb0\u5fc6\u6574\u7406\u81ea\u52a8\u63d0\u53d6\u957f\u671f\u8bb0\u5fc6\uff08\u672c\u5730\u5bf9\u8bdd\uff09", None))
#if QT_CONFIG(tooltip)
        self.autoExtractMemoryCheckBox.setToolTip(QCoreApplication.translate("MainWindow", u"\u4f9d\u8d56\u201c\u8bb0\u5fc6\u65b9\u6848\u201d\u7684\u81ea\u52a8\u6574\u7406\uff0c\u6216\u624b\u52a8\u70b9\u51fb\u6574\u7406\u5386\u53f2\u3002\u81ea\u52a8\u786e\u8ba4\u53ea\u51b3\u5b9a\u7ed3\u679c\u662f\u5426\u7acb\u5373\u7528\u4e8e\u56de\u7b54\u3002", None))
#endif // QT_CONFIG(tooltip)
        self.extractMemoryButton.setText(QCoreApplication.translate("MainWindow", u"\u4ece\u672c\u5730\u5bf9\u8bdd\u63d0\u53d6\u8bb0\u5fc6", None))
        self.autoApproveMemoryCheckBox.setText(QCoreApplication.translate("MainWindow", u"\u81ea\u52a8\u786e\u8ba4\u65b0\u63d0\u53d6\u7684\u8bb0\u5fc6", None))
        self.memoryStatusLabel.setText(QCoreApplication.translate("MainWindow", u"\u786e\u8ba4\u540e\u624d\u4f1a\u7528\u4e8e\u56de\u7b54", None))
        self.memorySearchEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"\u641c\u7d22\u8bb0\u5fc6\u5185\u5bb9", None))
        self.memoryFilterCombo.setItemText(0, QCoreApplication.translate("MainWindow", u"\u5168\u90e8\u72b6\u6001", None))
        self.memoryFilterCombo.setItemText(1, QCoreApplication.translate("MainWindow", u"\u5df2\u786e\u8ba4", None))
        self.memoryFilterCombo.setItemText(2, QCoreApplication.translate("MainWindow", u"\u5f85\u786e\u8ba4", None))

        self.refreshMemoryButton.setText(QCoreApplication.translate("MainWindow", u"\u5237\u65b0", None))
        self.newMemoryButton.setText(QCoreApplication.translate("MainWindow", u"\u65b0\u5efa\u8bb0\u5fc6", None))
        self.memoryTotalLabel.setText(QCoreApplication.translate("MainWindow", u"\u5168\u90e8 0 \u6761", None))
        self.memoryEditLabel.setText(QCoreApplication.translate("MainWindow", u"\u65b0\u589e\u6216\u7f16\u8f91\u8bb0\u5fc6", None))
        self.memoryDetailsLabel.setText(QCoreApplication.translate("MainWindow", u"\u9009\u62e9\u4e00\u6761\u8bb0\u5fc6\u67e5\u770b\u8be6\u60c5\uff0c\u6216\u65b0\u5efa\u8bb0\u5fc6", None))
        self.memoryEditor.setPlaceholderText(QCoreApplication.translate("MainWindow", u"\u4f8b\u5982\uff1a\u6211\u559c\u6b22\u5148\u770b\u7b80\u5355\u793a\u4f8b\uff0c\u518d\u9010\u6b65\u589e\u52a0\u529f\u80fd\u3002", None))
        self.addMemoryButton.setText(QCoreApplication.translate("MainWindow", u"\u6dfb\u52a0\u4e3a\u5df2\u786e\u8ba4", None))
        self.updateMemoryButton.setText(QCoreApplication.translate("MainWindow", u"\u4fdd\u5b58\u4fee\u6539", None))
        self.approveMemoryButton.setText(QCoreApplication.translate("MainWindow", u"\u786e\u8ba4\u8fd9\u6761\u8bb0\u5fc6", None))
        self.deleteMemoryButton.setText(QCoreApplication.translate("MainWindow", u"\u5220\u9664", None))
        self.voiceIntroLabel.setText(QCoreApplication.translate("MainWindow", u"\u9009\u62e9\u5408\u6210\u65b9\u5f0f\u540e\uff0c\u70b9\u51fb\u201c\u4fdd\u5b58\u8bed\u97f3\u8bbe\u7f6e\u201d\u5e94\u7528\u3002\u804a\u5929\u9875\u7684\u201c\u8bed\u97f3\u56de\u590d\u201d\u63a7\u5236\u662f\u5426\u81ea\u52a8\u6717\u8bfb\u3002", None))
        self.voiceProviderLabel.setText(QCoreApplication.translate("MainWindow", u"\u5408\u6210\u65b9\u5f0f", None))
        self.voiceOnlineGroup.setTitle(QCoreApplication.translate("MainWindow", u"\u8c46\u5305\u5728\u7ebf\u8bed\u97f3", None))
        self.doubaoApiKeyLabel.setText(QCoreApplication.translate("MainWindow", u"\u8c46\u5305 API Key", None))
        self.doubaoApiKeyEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"\u4ece\u706b\u5c71\u5f15\u64ce\u63a7\u5236\u53f0\u83b7\u53d6", None))
        self.doubaoSpeakerLabel.setText(QCoreApplication.translate("MainWindow", u"\u97f3\u8272 ID", None))
        self.doubaoSpeakerEdit.setText(QCoreApplication.translate("MainWindow", u"zh_female_vv_uranus_bigtts", None))
#if QT_CONFIG(tooltip)
        self.doubaoSpeakerEdit.setToolTip(QCoreApplication.translate("MainWindow", u"\u4ece\u8c46\u5305\u97f3\u8272\u5e93\u590d\u5236\u97f3\u8272 ID\uff0c\u9700\u4e0e\u9ad8\u7ea7\u8bbe\u7f6e\u4e2d\u7684\u6a21\u578b\u5339\u914d\u3002", None))
#endif // QT_CONFIG(tooltip)
        self.doubaoSpeechRateLabel.setText(QCoreApplication.translate("MainWindow", u"\u8bed\u901f", None))
#if QT_CONFIG(tooltip)
        self.doubaoSpeechRateSpin.setToolTip(QCoreApplication.translate("MainWindow", u"-50 \u4e3a\u534a\u901f\uff0c100 \u4e3a 2 \u500d\u901f", None))
#endif // QT_CONFIG(tooltip)
        self.doubaoSpeechRateSpin.setSuffix(QCoreApplication.translate("MainWindow", u" %", None))
        self.doubaoHelpLabel.setText(QCoreApplication.translate("MainWindow", u"\u9996\u6b21\u4f7f\u7528\u9700\u5728\u706b\u5c71\u5f15\u64ce\u63a7\u5236\u53f0\u5f00\u901a\u201c\u8bed\u97f3\u5408\u6210 2.0\u201d\u3002\u586b\u5199\u5bc6\u94a5\u5e76\u4e0d\u7b49\u4e8e\u670d\u52a1\u5df2\u5f00\u901a\uff1b\u8bd5\u542c\u4f1a\u5411\u8c46\u5305\u53d1\u9001\u4e00\u53e5\u793a\u4f8b\u6587\u5b57\uff0c\u5e76\u6309\u5e73\u53f0\u89c4\u5219\u8ba1\u8d39\u3002\u8bed\u901f 0% \u4e3a\u6b63\u5e38\u901f\u5ea6\u3002", None))
        self.voiceLocalGroup.setTitle(QCoreApplication.translate("MainWindow", u"\u672c\u5730 Qwen \u8bed\u97f3", None))
        self.localTtsInfoLabel.setText("")
        self.prepareLocalTtsButton.setText(QCoreApplication.translate("MainWindow", u"\u5b89\u88c5\u672c\u5730\u8bed\u97f3", None))
        self.cancelLocalTtsButton.setText(QCoreApplication.translate("MainWindow", u"\u53d6\u6d88\u5b89\u88c5", None))
        self.startLocalTtsButton.setText(QCoreApplication.translate("MainWindow", u"\u542f\u52a8\u672c\u5730\u670d\u52a1", None))
        self.removeLocalTtsButton.setText(QCoreApplication.translate("MainWindow", u"\u5220\u9664\u672c\u5730\u73af\u5883", None))
        self.voiceReferenceAudioLabel.setText(QCoreApplication.translate("MainWindow", u"\u53c2\u8003\u97f3\u9891", None))
        self.voiceReferenceAudioEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"\u9009\u62e9\u4e00\u6bb5\u4f60\u5e0c\u671b\u6a21\u4eff\u7684\u8bed\u97f3", None))
        self.voiceBrowseButton.setText(QCoreApplication.translate("MainWindow", u"\u9009\u62e9\u6587\u4ef6", None))
        self.voiceReferenceTextLabel.setText(QCoreApplication.translate("MainWindow", u"\u97f3\u9891\u5bf9\u5e94\u6587\u5b57", None))
        self.voiceReferenceTextEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"\u51c6\u786e\u5199\u4e0b\u53c2\u8003\u97f3\u9891\u91cc\u8bf4\u7684\u5185\u5bb9", None))
        self.localReferenceHelpLabel.setText(QCoreApplication.translate("MainWindow", u"\u53c2\u8003\u97f3\u9891\u548c\u5bf9\u5e94\u6587\u5b57\u7528\u4e8e\u6a21\u4eff\u97f3\u8272\u3002\u5b89\u88c5\u73af\u5883\u65f6\u53ef\u4ee5\u5148\u7559\u7a7a\uff0c\u9996\u6b21\u5408\u6210\u524d\u518d\u586b\u5199\u3002", None))
        self.voiceAdvancedButton.setText(QCoreApplication.translate("MainWindow", u"\u9ad8\u7ea7\u53c2\u6570", None))
        self.voiceOnlineAdvancedGroup.setTitle(QCoreApplication.translate("MainWindow", u"\u5728\u7ebf\u9ad8\u7ea7\u53c2\u6570", None))
        self.doubaoResourceLabel.setText(QCoreApplication.translate("MainWindow", u"\u6a21\u578b\u8d44\u6e90 ID", None))
        self.doubaoResourceEdit.setText(QCoreApplication.translate("MainWindow", u"seed-tts-2.0", None))
        self.doubaoUidLabel.setText(QCoreApplication.translate("MainWindow", u"\u7528\u6237\u6807\u8bc6", None))
        self.doubaoUidEdit.setText(QCoreApplication.translate("MainWindow", u"ai-chat-memory", None))
        self.voiceLocalAdvancedGroup.setTitle(QCoreApplication.translate("MainWindow", u"\u672c\u5730\u9ad8\u7ea7\u53c2\u6570", None))
        self.voiceEndpointLabel.setText(QCoreApplication.translate("MainWindow", u"\u672c\u5730\u670d\u52a1\u5730\u5740", None))
        self.voiceEndpointEdit.setText(QCoreApplication.translate("MainWindow", u"http://127.0.0.1:9881", None))
        self.voiceModelLabel.setText(QCoreApplication.translate("MainWindow", u"Qwen3 \u6a21\u578b", None))
        self.voiceModelEdit.setText(QCoreApplication.translate("MainWindow", u"Qwen/Qwen3-TTS-12Hz-0.6B-Base", None))
        self.voiceLanguageLabel.setText(QCoreApplication.translate("MainWindow", u"\u8bed\u97f3\u8bed\u8a00", None))
        self.voiceLanguageCombo.setItemText(0, QCoreApplication.translate("MainWindow", u"Auto", None))
        self.voiceLanguageCombo.setItemText(1, QCoreApplication.translate("MainWindow", u"Chinese", None))
        self.voiceLanguageCombo.setItemText(2, QCoreApplication.translate("MainWindow", u"English", None))
        self.voiceLanguageCombo.setItemText(3, QCoreApplication.translate("MainWindow", u"Japanese", None))
        self.voiceLanguageCombo.setItemText(4, QCoreApplication.translate("MainWindow", u"Korean", None))
        self.voiceLanguageCombo.setItemText(5, QCoreApplication.translate("MainWindow", u"French", None))
        self.voiceLanguageCombo.setItemText(6, QCoreApplication.translate("MainWindow", u"German", None))
        self.voiceLanguageCombo.setItemText(7, QCoreApplication.translate("MainWindow", u"Spanish", None))
        self.voiceLanguageCombo.setItemText(8, QCoreApplication.translate("MainWindow", u"Italian", None))
        self.voiceLanguageCombo.setItemText(9, QCoreApplication.translate("MainWindow", u"Portuguese", None))
        self.voiceLanguageCombo.setItemText(10, QCoreApplication.translate("MainWindow", u"Russian", None))

        self.voiceDeviceLabel.setText(QCoreApplication.translate("MainWindow", u"\u63a8\u7406\u8bbe\u5907", None))
        self.voiceDeviceCombo.setItemText(0, QCoreApplication.translate("MainWindow", u"auto", None))
        self.voiceDeviceCombo.setItemText(1, QCoreApplication.translate("MainWindow", u"cuda:0", None))
        self.voiceDeviceCombo.setItemText(2, QCoreApplication.translate("MainWindow", u"cpu", None))

        self.voiceDtypeLabel.setText(QCoreApplication.translate("MainWindow", u"\u8ba1\u7b97\u7cbe\u5ea6", None))
        self.voiceDtypeCombo.setItemText(0, QCoreApplication.translate("MainWindow", u"auto", None))
        self.voiceDtypeCombo.setItemText(1, QCoreApplication.translate("MainWindow", u"float16", None))
        self.voiceDtypeCombo.setItemText(2, QCoreApplication.translate("MainWindow", u"bfloat16", None))
        self.voiceDtypeCombo.setItemText(3, QCoreApplication.translate("MainWindow", u"float32", None))

        self.voiceSegmentCharsLabel.setText(QCoreApplication.translate("MainWindow", u"\u6bcf\u6bb5\u5b57\u6570", None))
        self.voiceTemperatureLabel.setText(QCoreApplication.translate("MainWindow", u"\u968f\u673a\u5ea6", None))
        self.voiceTopPLabel.setText(QCoreApplication.translate("MainWindow", u"Top P", None))
        self.voiceTopKLabel.setText(QCoreApplication.translate("MainWindow", u"Top K", None))
        self.voiceRepetitionPenaltyLabel.setText(QCoreApplication.translate("MainWindow", u"\u91cd\u590d\u60e9\u7f5a", None))
        self.voiceMaxTokensLabel.setText(QCoreApplication.translate("MainWindow", u"\u6700\u5927\u751f\u6210\u957f\u5ea6", None))
        self.saveVoiceButton.setText(QCoreApplication.translate("MainWindow", u"\u4fdd\u5b58\u8bed\u97f3\u8bbe\u7f6e", None))
        self.testVoiceButton.setText(QCoreApplication.translate("MainWindow", u"\u8bed\u97f3\u8bd5\u542c", None))
        self.pauseVoicePageButton.setText(QCoreApplication.translate("MainWindow", u"\u6682\u505c\u8bed\u97f3", None))
#if QT_CONFIG(tooltip)
        self.pauseVoicePageButton.setToolTip(QCoreApplication.translate("MainWindow", u"\u6682\u505c\u64ad\u653e\u548c\u8bed\u97f3\u8bf7\u6c42\uff0c\u7ee7\u7eed\u65f6\u91cd\u65b0\u8bf7\u6c42\u672a\u5b8c\u6210\u7684\u77ed\u53e5\u3002", None))
#endif // QT_CONFIG(tooltip)
        self.voiceStatusLabel.setText("")
        self.qqIntroLabel.setText(QCoreApplication.translate("MainWindow", u"\u5185\u7f6e NapCat / OneBot 11\u3002\u53ef\u5728\u672c\u9875\u542f\u52a8\u670d\u52a1\u3001\u626b\u7801\u767b\u5f55\u548c\u67e5\u770b\u65e5\u5fd7\uff0c\u4e5f\u53ef\u8fde\u63a5\u5df2\u8fd0\u884c\u7684\u5916\u90e8\u6865\u63a5\u3002", None))
        self.qqConnectionCard.setTitle(QCoreApplication.translate("MainWindow", u"\u8fde\u63a5\u3001\u8bbf\u95ee\u4e0e\u81ea\u52a8\u56de\u590d\u767d\u540d\u5355", None))
        self.qqUrlLabel.setText(QCoreApplication.translate("MainWindow", u"WebSocket \u5730\u5740", None))
        self.qqUrlEdit.setText(QCoreApplication.translate("MainWindow", u"ws://127.0.0.1:3001", None))
        self.qqTokenLabel.setText(QCoreApplication.translate("MainWindow", u"\u8bbf\u95ee\u4ee4\u724c\uff08\u53ef\u7559\u7a7a\uff09", None))
        self.qqTokenEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"\u5982\u6865\u63a5\u7a0b\u5e8f\u8bbe\u7f6e\u4e86\u4ee4\u724c", None))
        self.qqAllowlistLabel.setText(QCoreApplication.translate("MainWindow", u"\u81ea\u52a8\u56de\u590d\u767d\u540d\u5355", None))
        self.qqAllowlistEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"QQ \u53f7\u7528\u9017\u53f7\u5206\u9694\uff1b\u7559\u7a7a\u65f6\u4e0d\u4f1a\u81ea\u52a8\u56de\u590d", None))
        self.qqReplyCard.setTitle(QCoreApplication.translate("MainWindow", u"\u81ea\u52a8\u56de\u590d", None))
        self.qqAutoReplyCheckBox.setText(QCoreApplication.translate("MainWindow", u"\u6536\u5230\u767d\u540d\u5355\u5185\u7684 QQ \u79c1\u804a\u540e\u81ea\u52a8\u56de\u590d\uff08\u9ed8\u8ba4\u5173\u95ed\uff09", None))
        self.qqStickerCheckBox.setText(QCoreApplication.translate("MainWindow", u"\u5141\u8bb8 AI \u81ea\u4e3b\u53d1\u9001\u8868\u60c5\u5305", None))
        self.qqVoiceCheckBox.setText(QCoreApplication.translate("MainWindow", u"\u5141\u8bb8 AI \u81ea\u4e3b\u53d1\u9001\u8bed\u97f3\uff08\u53ef\u5728 QQ \u4e2d\u8981\u6c42\u8bed\u97f3\u56de\u590d\uff09", None))
        self.qqManualCard.setTitle(QCoreApplication.translate("MainWindow", u"\u624b\u52a8\u53d1\u9001", None))
        self.qqRecipientEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"\u63a5\u6536\u65b9 QQ \u53f7", None))
        self.qqSendImageButton.setText(QCoreApplication.translate("MainWindow", u"\u53d1\u9001\u8868\u60c5 / \u56fe\u7247", None))
        self.qqSendVoiceButton.setText(QCoreApplication.translate("MainWindow", u"\u53d1\u9001\u8bed\u97f3\u6587\u4ef6", None))
        self.saveQqButton.setText(QCoreApplication.translate("MainWindow", u"\u4fdd\u5b58 QQ \u8bbe\u7f6e", None))
        self.qqConnectButton.setText(QCoreApplication.translate("MainWindow", u"\u8fde\u63a5\u672c\u5730\u6865\u63a5", None))
        self.qqStatusLabel.setText(QCoreApplication.translate("MainWindow", u"\u5c1a\u672a\u8fde\u63a5", None))
        self.qqSafetyNote.setText(QCoreApplication.translate("MainWindow", u"\u5f53\u524d\u4ec5\u63a5\u6536\u79c1\u804a\u4e8b\u4ef6\uff0c\u4e0d\u5904\u7406\u7fa4\u6d88\u606f\u3002\u5f00\u542f\u81ea\u52a8\u56de\u590d\u524d\uff0c\u8bf7\u5148\u586b\u5199\u5141\u8bb8\u56de\u590d\u7684 QQ \u53f7\u3002", None))
        self.settingsIntroLabel.setText(QCoreApplication.translate("MainWindow", u"\u7ba1\u7406 AI \u52a9\u624b\u5f62\u8c61\u3001\u6a21\u578b\u8fde\u63a5\u548c\u672c\u673a\u751f\u6210\u7684\u8bed\u97f3\u6587\u4ef6\u3002", None))
        self.assistantDisplaySection.setText(QCoreApplication.translate("MainWindow", u"\u52a9\u624b\u5f62\u8c61", None))
        self.assistantNameLabel.setText(QCoreApplication.translate("MainWindow", u"AI \u540d\u79f0", None))
        self.assistantNameEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"AI \u52a9\u624b", None))
        self.assistantAvatarLabel.setText(QCoreApplication.translate("MainWindow", u"AI \u5934\u50cf", None))
        self.assistantAvatarEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"\u9ed8\u8ba4\u5934\u50cf\uff1aassets/assistant_avatar.svg", None))
        self.assistantAvatarBrowseButton.setText(QCoreApplication.translate("MainWindow", u"\u9009\u62e9", None))
        self.assistantAvatarResetButton.setText(QCoreApplication.translate("MainWindow", u"\u6062\u590d\u9ed8\u8ba4", None))
        self.apiBaseUrlLabel.setText(QCoreApplication.translate("MainWindow", u"API \u5730\u5740", None))
        self.apiBaseUrlEdit.setText(QCoreApplication.translate("MainWindow", u"https://api.deepseek.com", None))
        self.apiKeyLabel.setText(QCoreApplication.translate("MainWindow", u"API \u5bc6\u94a5", None))
        self.apiKeyEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"\u7c98\u8d34\u4f60\u7684 DeepSeek API \u5bc6\u94a5", None))
        self.showApiKeySpacerLabel.setText("")
        self.showApiKeyCheckBox.setText(QCoreApplication.translate("MainWindow", u"\u663e\u793a\u5bc6\u94a5", None))
        self.modelLabel.setText(QCoreApplication.translate("MainWindow", u"\u6a21\u578b\u540d\u79f0", None))
        self.modelEdit.setText(QCoreApplication.translate("MainWindow", u"deepseek-flash", None))
        self.thinkingEnabledCheckBox.setText(QCoreApplication.translate("MainWindow", u"\u6df1\u5ea6\u601d\u8003\uff08\u56de\u7b54\u5f00\u59cb\u524d\u4f1a\u7b49\u5f85\u66f4\u4e45\uff09", None))
#if QT_CONFIG(tooltip)
        self.thinkingEnabledCheckBox.setToolTip(QCoreApplication.translate("MainWindow", u"\u5173\u95ed\u65f6\u76f4\u63a5\u751f\u6210\u56de\u7b54\uff1b\u5f00\u542f\u540e\uff0c\u5728\u804a\u5929\u6c14\u6ce1\u4e2d\u5b9e\u65f6\u5c55\u793a\u6a21\u578b\u8fd4\u56de\u7684\u601d\u8003\u5185\u5bb9\uff0c\u53ef\u5c55\u5f00\u6216\u6536\u8d77\uff0c\u5386\u53f2\u6d88\u606f\u4e5f\u53ef\u67e5\u770b\u3002", None))
#endif // QT_CONFIG(tooltip)
        self.systemPromptLabel.setText(QCoreApplication.translate("MainWindow", u"\u7cfb\u7edf\u63d0\u793a\u8bcd", None))
        self.systemPromptEdit.setPlainText(QCoreApplication.translate("MainWindow", u"\u4f60\u662f\u4e00\u4e2a\u771f\u8bda\u3001\u6e05\u6670\u3001\u8010\u5fc3\u7684 AI \u52a9\u624b\u3002\u7ed3\u5408\u957f\u671f\u8bb0\u5fc6\u56de\u7b54\uff0c\u4f46\u4e0d\u8981\u628a\u8bb0\u5fc6\u5f53\u4f5c\u4e0d\u53ef\u66f4\u6539\u7684\u4e8b\u5b9e\u3002", None))
        self.saveSettingsButton.setText(QCoreApplication.translate("MainWindow", u"\u4fdd\u5b58\u8bbe\u7f6e", None))
        self.settingsStatusLabel.setText(QCoreApplication.translate("MainWindow", u"\u4fee\u6539\u540e\u8bb0\u5f97\u4fdd\u5b58", None))
        self.voiceHistoryLabel.setText(QCoreApplication.translate("MainWindow", u"\u672c\u673a\u751f\u6210\u7684\u56de\u590d\u8bed\u97f3", None))
        self.clearVoiceHistoryButton.setText(QCoreApplication.translate("MainWindow", u"\u6e05\u7406\u5386\u53f2\u8bed\u97f3", None))
        self.dataMigrationButton.setText(QCoreApplication.translate("MainWindow", "数据迁移 · 备份 / 导入 DSH 聊天", None))
        self.clearAllDataButton.setText(QCoreApplication.translate("MainWindow", u"\u6e05\u7a7a\u5168\u90e8\u804a\u5929\u4e0e\u8bb0\u5fc6\u2026", None))
        self.clearAllDataButton.setStyleSheet(QCoreApplication.translate("MainWindow", u"color: #b14d50;", None))
        self.clearAllDataHelp.setText(QCoreApplication.translate("MainWindow", u"\u91cd\u65b0\u5f00\u59cb\u5bf9\u8bdd\uff1a\u6e05\u9664\u804a\u5929\u3001\u8bb0\u5fc6\u53ca\u76f8\u5173\u7f13\u5b58\uff0c\u4fdd\u7559\u63a5\u53e3\u914d\u7f6e\u3001\u89d2\u8272\u548c\u6a21\u578b\u3002\u64cd\u4f5c\u524d\u9700\u8981\u786e\u8ba4\u3002", None))
    # retranslateUi

