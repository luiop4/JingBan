"""Native plugin example: saved phrases that fill the chat composer."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
                              QPlainTextEdit, QPushButton)
from dialogs import FishDialog


MANIFEST = {
    'id': 'jingban_quick_phrases', 'name': '快捷短语', 'version': '1.0.0',
    'api_version': 1, 'author': '鲸伴', 'builtin': True, 'permissions': [],
    'description': '原生插件示例：保存常用提问，点选后填入聊天输入框，由你确认发送。',
}


class QuickPhrases:
    def __init__(self, context):
        self.context = context
        self.dialog = None
        self.phrases = []

    def start(self):
        values = self.context.load_settings({'phrases': ['帮我梳理一下今天要做的事。', '把这段内容整理成简短的要点。']})
        phrases = values.get('phrases', [])
        phrases = phrases if isinstance(phrases, list) else []
        self.phrases = [text[:4000] for text in phrases
                        if isinstance(text, str) and text.strip()][:200]

    def stop(self):
        if self.dialog is not None:
            self.dialog.close()

    def show_settings(self):
        if self.dialog is None:
            dialog = self.dialog = self.context.track(QDialog())
            dialog.setWindowTitle('快捷短语 · 原生插件示例')
            dialog.resize(520, 450)
            layout = QVBoxLayout(dialog)
            label = QLabel('选中短语可编辑、删除，或填入聊天输入框。修改后点击“保存短语”。')
            label.setWordWrap(True)
            layout.addWidget(label)
            self.list = QListWidget(dialog)
            layout.addWidget(self.list)
            self.editor = QPlainTextEdit(dialog)
            self.editor.setPlaceholderText('输入常用短语…')
            self.editor.setMaximumHeight(110)
            layout.addWidget(self.editor)
            actions = QHBoxLayout()
            for title, callback in (('新增', self.add), ('保存短语', self.save),
                                    ('删除', self.remove), ('填入聊天', self.use)):
                button = QPushButton(title, dialog)
                button.clicked.connect(callback)
                actions.addWidget(button)
            layout.addLayout(actions)
            self.list.currentRowChanged.connect(self.select)
            self.list.itemDoubleClicked.connect(lambda _item: self.use())
            self.refresh()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def refresh(self, index=0):
        self.list.blockSignals(True)
        self.list.clear()
        self.list.addItems([text.replace('\n', ' ')[:90] for text in self.phrases])
        self.list.blockSignals(False)
        self.list.setCurrentRow(index if self.phrases else -1)
        self.select(self.list.currentRow())

    def select(self, index):
        self.editor.setPlainText(self.phrases[index] if 0 <= index < len(self.phrases) else '')

    def add(self):
        if len(self.phrases) >= 200:
            self.context.notify('最多保存 200 条短语。')
            return
        self.list.setCurrentRow(-1)
        self.editor.clear()
        self.editor.setFocus()

    def persist(self, values):
        try:
            self.context.save_settings({'phrases': values})
        except (OSError, ValueError) as error:
            FishDialog.information(self.dialog, '短语保存失败', str(error), 'warning')
            return False
        self.phrases = values
        return True

    def save(self):
        text = self.editor.toPlainText().strip()
        if not text or len(text) > 4000:
            self.context.notify('短语需要 1～4000 个字符。')
            return
        index = self.list.currentRow()
        updated = list(self.phrases)
        if index < 0:
            if len(updated) >= 200:
                self.context.notify('最多保存 200 条短语。')
                return
            updated.append(text)
            index = len(updated) - 1
        else:
            updated[index] = text
        if self.persist(updated):
            self.refresh(index)

    def remove(self):
        index = self.list.currentRow()
        if index < 0:
            return
        updated = list(self.phrases)
        updated.pop(index)
        if self.persist(updated):
            self.refresh(min(index, len(updated) - 1))

    def use(self):
        text = self.editor.toPlainText().strip()
        if text and len(text) <= 4000:
            self.context.draft_message(text)
            self.dialog.hide()


def create_plugin(context):
    return QuickPhrases(context)
