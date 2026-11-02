"""展示独立操作日志；追问近期任务时仅恢复有界摘录，不用于记忆提取。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame
from ui_command_trace import Ui_CommandTrace


class CommandTraceCard(QFrame, Ui_CommandTrace):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setObjectName('commandTraceCard')
        self.detailsPanel.hide()
        self.toggleButton.toggled.connect(self.toggle_details)
        self.reason = '电脑操作'
        self.setStyleSheet('''
            #commandTraceCard { background: #f5f6f8; border: 1px solid #e0e4eb; border-radius: 8px; }
            #commandTraceCard QToolButton { border: 0; background: transparent; text-align: left; padding: 5px; color: #647084; }
            #commandTraceCard QPlainTextEdit { background: #fcfcfd; border: 1px solid #e0e4eb; border-radius: 5px; font-family: Consolas, "Microsoft YaHei"; font-size: 12px; }
            #ephemeralLabel { color: #89909c; font-size: 11px; }
        ''')

    def toggle_details(self, expanded):
        self.detailsPanel.setVisible(expanded)
        self.toggleButton.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def update_progress(self, data):
        if 'reason' in data:
            self.reason = data['reason'].strip() or '电脑操作'
            self.purposeLabel.setText(self.reason)
        if 'cwd' in data:
            self.directoryLabel.setText('目录：' + data['cwd'])
        if 'command' in data:
            self.commandView.setPlainText(data['command'])
        phase = data.get('phase', '执行中')
        elapsed = f" · {data['elapsed']:.1f} 秒" if 'elapsed' in data else ''
        title = self.reason.replace('\n', ' ')
        title = title[:22] + ('…' if len(title) > 22 else '')
        self.toggleButton.setText(f'{phase} · {title}{elapsed}')
        self.toggleButton.setToolTip(self.reason)
        if 'output' in data and data['output'] != self.outputView.toPlainText():
            bar = self.outputView.verticalScrollBar()
            following = bar.maximum() - bar.value() < 20
            old_value = bar.value()
            self.outputView.setPlainText(data['output'])
            bar.setValue(bar.maximum() if following else min(old_value, bar.maximum()))
        summary = phase + elapsed
        if data.get('exit_code') is not None:
            summary += f" · 退出码 {data['exit_code']}"
        if data.get('truncated'):
            summary += ' · 输出较长，仅显示末尾 16 KB'
        self.resultLabel.setText(summary)
