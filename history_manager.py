"""历史管理逻辑；布局保存在 history_manager.ui，可用 Qt Designer 编辑。"""
from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import QDialog, QTableWidgetItem, QAbstractItemView, QHeaderView, QMessageBox
from dialogs import FishDialog
from message_cards import show_original
from ui_history_manager import Ui_HistoryDialog


class HistoryManager(QDialog, Ui_HistoryDialog):
    records_changed = Signal()

    def __init__(self, window, root, embedded=False):
        super().__init__(window)
        self.setupUi(self)
        if embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
            self.setMinimumSize(0, 0)
            self.closeButton.hide()
        self.resize(960, 620)
        self.window = window
        self.root = root
        self.database = window.database
        self.page = 0
        self.changed = False
        self.filters = {}
        self.rows = []
        self.total = 0
        self.stateCombo.addItem('聊天中', 'visible')
        self.stateCombo.addItem('已隐藏', 'hidden')
        self.stateCombo.addItem('全部记录', 'all')
        self.stateCombo.setCurrentIndex(2)
        self.startDate.setDate(QDate.currentDate().addMonths(-1))
        self.endDate.setDate(QDate.currentDate())
        self.startDate.setEnabled(False)
        self.endDate.setEnabled(False)
        self.dateCheck.toggled.connect(self.startDate.setEnabled)
        self.dateCheck.toggled.connect(self.endDate.setEnabled)
        table = self.historyTable
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(['勾选', '时间', '发送者', '内容', '状态'])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setWordWrap(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setDefaultSectionSize(46)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.itemChanged.connect(self.update_selection)
        table.cellDoubleClicked.connect(lambda row, column: show_original(window, self.rows[row]['id'], root) if column != 0 else None)
        self.searchButton.clicked.connect(self.apply_filters)
        self.keywordEdit.returnPressed.connect(self.apply_filters)
        self.stateCombo.currentIndexChanged.connect(self.apply_filters)
        self.resetButton.clicked.connect(self.reset_filters)
        self.previousButton.clicked.connect(lambda: self.change_page(-1))
        self.nextButton.clicked.connect(lambda: self.change_page(1))
        self.selectPageButton.clicked.connect(self.toggle_page)
        self.clearSelectionButton.clicked.connect(lambda: self.set_page_checked(False))
        self.hideSelectedButton.clicked.connect(lambda: self.change_visibility(True, False))
        self.restoreSelectedButton.clicked.connect(lambda: self.change_visibility(False, False))
        self.hideFilteredButton.clicked.connect(lambda: self.change_visibility(True, True))
        self.restoreFilteredButton.clicked.connect(lambda: self.change_visibility(False, True))
        self.deleteSelectedButton.clicked.connect(lambda: self.delete_records(False))
        self.deleteFilteredButton.clicked.connect(lambda: self.delete_records(True))
        self.closeButton.clicked.connect(self.accept)
        self.apply_filters()

    def apply_filters(self):
        if self.dateCheck.isChecked() and self.startDate.date() > self.endDate.date():
            FishDialog.information(self, '日期范围无效', '开始日期不能晚于结束日期。')
            return
        self.filters = {'keyword': self.keywordEdit.text().strip(), 'state': self.stateCombo.currentData()}
        if self.dateCheck.isChecked():
            self.filters.update(start=self.startDate.date().toString('yyyy-MM-dd'), end=self.endDate.date().toString('yyyy-MM-dd'))
        self.page = 0
        self.refresh()

    def reset_filters(self):
        self.keywordEdit.clear()
        self.dateCheck.setChecked(False)
        self.stateCombo.setCurrentIndex(2)
        self.apply_filters()

    def change_page(self, offset):
        self.page = max(0, self.page + offset)
        self.refresh()

    def refresh(self):
        self.rows, self.total = self.database.history_page(self.filters, self.page)
        last_page = max(0, (self.total-1)//100)
        if self.page > last_page:
            self.page = last_page
            self.rows, self.total = self.database.history_page(self.filters, self.page)
        self.historyTable.blockSignals(True)
        self.historyTable.setRowCount(0)
        self.historyTable.setRowCount(len(self.rows))
        for index, message in enumerate(self.rows):
            role = 'assistant' if message['role'] == 'assistant' else 'user'
            name = self.window.app_settings.get(role, {}).get('name', message['role'])
            if message['source'] == 'qq':
                name += ' · QQ ' + (message['peer_name'] or message['peer_id'])
            elif message['source'] == 'dsh':
                name += ' · DSH · ' + message['peer_name']
            content = message['content'].replace('\n', ' ')
            values = [message['created_at'].replace('T', ' ')[:19], name, content[:160] or '（附件或表情）', '已隐藏' if message['hidden'] else '聊天中']
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            check.setCheckState(Qt.CheckState.Unchecked)
            self.historyTable.setItem(index, 0, check)
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setToolTip(message['content'][:1500])
                self.historyTable.setItem(index, column, item)
        self.historyTable.blockSignals(False)
        self.pageLabel.setText(f'共 {self.total} 条 · 第 {self.page+1}/{last_page+1} 页 · 每页 100 条')
        self.previousButton.setEnabled(self.page > 0)
        self.nextButton.setEnabled(self.page < last_page)
        self.hideFilteredButton.setEnabled(self.total > 0 and self.filters.get('state') != 'hidden')
        self.restoreFilteredButton.setEnabled(self.total > 0 and self.filters.get('state') != 'visible')
        self.deleteFilteredButton.setEnabled(self.total > 0)
        self.update_selection()

    def checked_ids(self):
        return [message['id'] for row, message in enumerate(self.rows)
                if self.historyTable.item(row, 0) is not None
                and self.historyTable.item(row, 0).checkState() == Qt.CheckState.Checked]

    def set_page_checked(self, checked):
        self.historyTable.blockSignals(True)
        for row in range(len(self.rows)):
            self.historyTable.item(row, 0).setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.historyTable.blockSignals(False)
        self.update_selection()

    def toggle_page(self):
        self.set_page_checked(len(self.checked_ids()) != len(self.rows))

    def update_selection(self, *_args):
        selected = self.checked_ids()
        self.selectionLabel.setText(f'已勾选 {len(selected)} 条 · 点击左侧方框多选 · 换页或筛选会清空勾选 · 双击内容查看')
        self.selectPageButton.setText('取消本页全选' if selected and len(selected) == len(self.rows) else '全选本页')
        self.clearSelectionButton.setEnabled(bool(selected))
        self.hideSelectedButton.setEnabled(bool(selected))
        self.restoreSelectedButton.setEnabled(bool(selected))
        self.deleteSelectedButton.setEnabled(bool(selected))

    def delete_records(self, all_filtered):
        if self.window.active_worker is not None or (
                self.window.memory_worker is not None and self.window.memory_worker.isRunning()):
            FishDialog.information(self, '正在处理对话', '请等回复或记忆提取结束后再删除。')
            return
        ids = (self.database.history_ids(self.filters) if all_filtered else
               self.checked_ids())
        if not ids:
            return
        scope = '当前筛选结果（包括其他页）' if all_filtered else '所选记录'
        confirmation = QMessageBox(self.window)
        confirmation.setWindowTitle('永久删除历史对话')
        confirmation.setIcon(QMessageBox.Icon.Warning)
        confirmation.setText(
                f'将从数据库永久删除{scope}，共 {len(ids)} 条消息。\n'
                '关联附件、语音、操作过程与引用会一并移除，无法恢复。\n\n'
                'AI 以后不能再检索这些原消息。长期记忆不会改动；其他消息或长期记忆中'
                '若也记载了同一件事，AI 仍可能知道。\n'
                '如需删除一段完整对话，请同时选中你的消息和 AI 的回复。')
        delete_button = confirmation.addButton(f'永久删除 {len(ids)} 条', QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = confirmation.addButton('取消', QMessageBox.ButtonRole.RejectRole)
        confirmation.setDefaultButton(cancel_button)
        confirmation.setEscapeButton(cancel_button)
        confirmation.exec()
        if confirmation.clickedButton() != delete_button:
            return
        if self.window.active_worker is not None or (
                self.window.memory_worker is not None and self.window.memory_worker.isRunning()):
            FishDialog.information(self, '正在处理对话', '当前有回复或记忆提取任务，请稍后删除。')
            return
        try:
            count, audio, attachments = self.database.delete_history_records(ids)
        except Exception as error:
            FishDialog.information(self, '删除未完成', str(error))
            return
        # 只清理项目的附件副本，不触碰用户最初上传的文件。
        self.window._remove_reply_audio_files(audio)
        attachment_root = (self.root / 'data' / 'attachments').resolve()
        failed = 0
        for value in attachments:
            path = (self.root / value).resolve()
            if path.is_relative_to(attachment_root):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    failed += 1
        self.changed = self.changed or bool(count)
        self.records_changed.emit()
        self.refresh()
        self.selectionLabel.setText(
            f'已从数据库删除 {count} 条消息，长期记忆未改动。'
            + (f' {failed} 个附件文件被占用，未能清理。' if failed else ''))
        QMessageBox.information(self.window, '删除完成', self.selectionLabel.text())

    def change_visibility(self, hidden, all_filtered):
        if self.window.active_worker is not None:
            FishDialog.information(self, '正在回复', '请等回复完成后再清理或恢复记录。')
            return
        ids = None if all_filtered else self.checked_ids()
        if not all_filtered and not ids:
            return
        count = self.total if all_filtered else len(ids)
        action = '隐藏' if hidden else '恢复'
        scope = '当前已应用筛选条件下的全部记录（包含其他页）' if all_filtered else '选中的记录'
        if not FishDialog.question(self, action + '历史记录',
                f'将{action}{scope}，范围内共 {count} 条。\n\n'
                + ('只移出聊天界面，原文、附件、记忆和引用均保留，可随时恢复。' if hidden else '恢复后会重新进入聊天列表；主界面仍只加载最近 300 条，其他记录可在此查看。'),
                confirm_text=action):
            return
        try:
            if self.window.active_worker is not None:
                return
            changed = self.database.set_history_hidden(hidden, ids=ids, filters=self.filters)
        except Exception as error:
            FishDialog.information(self, '操作未完成', str(error))
            return
        self.changed = self.changed or bool(changed)
        if changed:
            self.records_changed.emit()
        self.refresh()
        self.selectionLabel.setText(f'已{action} {changed} 条，AI 记忆未改动。')
