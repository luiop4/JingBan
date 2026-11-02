"""消息显示逻辑；代码框布局可在 Qt Designer 打开 code_block.ui 修改。"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QSizePolicy, QToolButton, QVBoxLayout, QWidget
from ui_code_block import Ui_CodeBlock
from message_format import message_parts


class CodeBlock(QFrame, Ui_CodeBlock):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.codeEditor.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setStyleSheet("""
            QFrame#CodeBlock {background:#f3f5f8; border:1px solid #dce1e8; border-radius:8px;}
            QPlainTextEdit {background:#f3f5f8; color:#253247; border:0; padding:4px;}
            QLabel {color:#65738a; font-size:11px;}
            QPushButton {background:#e4e9f0; color:#34445d; border:0; border-radius:5px; padding:5px 10px;}
        """)
        self.copyButton.clicked.connect(self.copy_code)

    def update_code(self, language, content):
        self.languageLabel.setText(language[:60])
        if self.codeEditor.toPlainText() == content:
            return
        bar = self.codeEditor.verticalScrollBar()
        following, position = bar.value() >= bar.maximum() - 2, bar.value()
        self.codeEditor.setPlainText(content)
        self.codeEditor.setFixedHeight(min(360, max(78, (content.count("\n") + 1) * self.codeEditor.fontMetrics().lineSpacing() + 32)))
        bar.setValue(bar.maximum() if following else position)

    def copy_code(self):
        QApplication.clipboard().setText(self.codeEditor.toPlainText())
        self.copyButton.setText("已复制")
        QTimer.singleShot(1200, self, lambda: self.copyButton.setText("复制代码"))


class ReasoningPanel(QFrame):
    """Display the provider's reasoning separately from the reply text."""
    def __init__(self, parent, finished=False):
        super().__init__(parent)
        self.setObjectName('reasoningPanel')
        self.setStyleSheet('''
            QFrame#reasoningPanel {background:#F3F5FA; border:1px solid #DEE4EF; border-radius:8px;}
            QToolButton {background:transparent; border:0; color:#627394; text-align:left; padding:4px;}
            QPlainTextEdit {background:transparent; border:0; color:#657187; font-size:12px;}
        ''')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        self.toggle = QToolButton(self)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setCheckable(True)
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.setToolTip('模型接口返回的思考原文，程序不改写；与单独标注为演绎的角色心声分开保留。')
        self.editor = QPlainTextEdit(self)
        self.editor.setReadOnly(True)
        self.editor.setMinimumWidth(240)
        self.editor.setFixedHeight(180)
        layout.addWidget(self.toggle)
        layout.addWidget(self.editor)
        self.toggle.toggled.connect(self._expand)
        self.toggle.setChecked(not finished)
        self.title = '深度思考'
        self._expand(not finished)
        self.finish('已完成' if finished else '进行中')

    def _expand(self, expanded):
        self.editor.setVisible(expanded)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def append(self, text):
        scrollbar = self.editor.verticalScrollBar()
        following, position = scrollbar.value() >= scrollbar.maximum() - 2, scrollbar.value()
        cursor = QTextCursor(self.editor.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        scrollbar.setValue(scrollbar.maximum() if following else position)

    def finish(self, status='已完成'):
        self.toggle.setText(self.title + ' · ' + status)


class MessageBody(QWidget):
    """保留 text/setText 接口，兼容消息复制、引用、回放与流式更新。"""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        self.blocks = []
        self.reasoning_panel = None
        self.original_reasoning_visible = True
        self.character_aside_mode = False
        self.character_aside_panel = None
        self.character_aside_label = None
        self.character_aside_title = None
        self.character_aside_state = ''
        self._text = ""
        self.setText(text)

    def text(self):
        return self._text

    def set_original_reasoning_visible(self, visible):
        self.original_reasoning_visible = bool(visible)
        if self.reasoning_panel is not None:
            self.reasoning_panel.setVisible(self.original_reasoning_visible)

    def set_character_aside_mode(self, enabled):
        changed = self.character_aside_mode != bool(enabled)
        self.character_aside_mode = bool(enabled)
        if self.reasoning_panel is not None:
            self.reasoning_panel.title = '模型原始思考' if enabled else '深度思考'
            if changed and enabled:
                self.reasoning_panel.toggle.setChecked(False)
            self.reasoning_panel.finish()

    def set_character_aside(self, text, *, state='ready'):
        if not text and state == 'ready':
            return
        self.character_aside_state = state
        self.set_character_aside_mode(True)
        if self.character_aside_panel is None:
            panel = QFrame(self)
            panel.setObjectName('characterAsidePanel')
            panel.setStyleSheet('''QFrame#characterAsidePanel {
                background:#F5F4FB; border:1px solid #E5DFF2; border-radius:9px;}
                QLabel {background:transparent; border:0; color:#716587;}''')
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(12, 9, 12, 10)
            layout.setSpacing(5)
            heading = QHBoxLayout()
            title = QLabel(panel)
            self.character_aside_title = title
            title.setStyleSheet('font-size:11px;color:#9586A9;')
            title.setToolTip('由模型在本次回复中创作的角色独白，不是模型原始推理，也不是操作回执。')
            heading.addWidget(title)
            badge = QLabel('角色演绎', panel)
            badge.setStyleSheet('font-size:10px;color:#A198B3;')
            badge.setToolTip('此处是虚构角色独白，不是模型原始推理。')
            heading.addWidget(badge)
            heading.addStretch()
            layout.addLayout(heading)
            self.character_aside_label = QLabel(panel)
            self.character_aside_label.setWordWrap(True)
            self.character_aside_label.setTextFormat(Qt.TextFormat.PlainText)
            self.character_aside_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(self.character_aside_label)
            self.character_aside_panel = panel
            self.content_layout.insertWidget(0, panel)
        self.character_aside_title.setText({'ready': '思考', 'generating': '思考 · 生成中',
            'unavailable': '思考 · 暂未生成', 'cancelled': '思考 · 未完成'}.get(state, '思考'))
        self.character_aside_label.setText(text or '正在补充这一句心声…')

    def _create_reasoning_panel(self, finished=False):
        self.reasoning_panel = ReasoningPanel(self, finished=finished or self.character_aside_mode)
        if self.character_aside_mode:
            self.reasoning_panel.title = '模型原始思考'
            self.reasoning_panel.finish('已完成' if finished else '进行中')
        self.content_layout.insertWidget(1 if self.character_aside_panel is not None else 0, self.reasoning_panel)
        self.reasoning_panel.setVisible(self.original_reasoning_visible)

    def append_reasoning(self, text):
        if self.reasoning_panel is None:
            self._create_reasoning_panel()
        self.reasoning_panel.append(text)

    def set_reasoning(self, text):
        if not text:
            return
        if self.reasoning_panel is None:
            self._create_reasoning_panel(finished=True)
        if self.reasoning_panel.editor.toPlainText() != text:
            self.reasoning_panel.editor.setPlainText(text)
        self.finish_reasoning()

    def finish_reasoning(self, status='已完成'):
        if self.reasoning_panel is not None:
            self.reasoning_panel.finish(status)
        if status != '已完成' and self.character_aside_state == 'generating':
            self.set_character_aside('补充生成已停止；已收到的回复正文保留。', state='cancelled')

    def setText(self, text):
        self._text = text
        parts = message_parts(text) or [(None, "")]
        for index, (language, content) in enumerate(parts):
            code = language is not None
            if index < len(self.blocks) and isinstance(self.blocks[index], CodeBlock) != code:
                while len(self.blocks) > index:
                    old = self.blocks.pop()
                    self.content_layout.removeWidget(old)
                    old.deleteLater()
            if index == len(self.blocks):
                block = CodeBlock(self) if code else QLabel(self)
                if not code:
                    block.setObjectName("messageBody")
                    block.setWordWrap(True)
                    block.setTextFormat(Qt.TextFormat.PlainText)
                    block.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self.blocks.append(block)
                self.content_layout.addWidget(block)
            if code:
                self.blocks[index].update_code(language, content)
            else:
                self.blocks[index].setText(content.strip("\n"))
        while len(self.blocks) > len(parts):
            old = self.blocks.pop()
            self.content_layout.removeWidget(old)
            old.deleteLater()
