"""Keep settings usable at small window sizes and high display scaling."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QScrollArea, QVBoxLayout, QFormLayout,
                              QLineEdit, QAbstractButton, QSizePolicy, QLayout)


def setup(window):
    page = window.settingsPage
    content = QWidget()
    content.setObjectName('settingsScrollContent')
    # Qt transfers the existing layout, including later insertions, to content.
    content.setLayout(window.settingsContentLayout)
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea(page)
    scroll.setObjectName('settingsScroll')
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(content)
    outer.addWidget(scroll)
    window.settingsContentLayout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    for form in (window.assistantDisplayForm, window.settingsForm):
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(12)
    for field in content.findChildren(QLineEdit):
        field.setMinimumSize(0, 38)
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    window.assistantAvatarLayout.setStretch(1, 1)
    for button in (window.assistantAvatarBrowseButton, window.assistantAvatarResetButton):
        button.setMinimumWidth(0)
        button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    window.systemPromptEdit.setMinimumHeight(170)
    window.systemPromptEdit.setMaximumHeight(240)
    window.settingsStatusLabel.setWordWrap(True)
    for button in content.findChildren(QAbstractButton):
        button.setMinimumHeight(30)
    window.settings_scroll = scroll
