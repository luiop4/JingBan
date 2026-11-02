"""记忆方案页；布局在 memory_scheme.ui，逻辑与生成的 UI 模块分离。"""
import json
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QWidget, QListWidgetItem, QDialog
from dialogs import FishDialog
from standard_memory import EventMemoryWorker, STATUS_LABELS
from ui_event_history import Ui_EventHistoryDialog
from ui_memory_scheme import Ui_MemorySchemePage


class MemorySchemePage(QWidget, Ui_MemorySchemePage):
    def __init__(self, window):
        super().__init__(window)
        self.setupUi(self)
        self.window = window
        self.apply_style()
        self.store = window.database.standard_memory
        self.worker = None
        self.run_status = "待命"
        self.auto_retry_blocked = False
        options = self.store.options()
        self.retrievalCheck.setChecked(options["enabled"])
        self.automaticCheck.setChecked(options["auto"])
        self.retrievalCheck.toggled.connect(self.save_preferences)
        self.automaticCheck.toggled.connect(self.save_preferences)
        self.organizeButton.clicked.connect(lambda: self.start(False))
        self.pauseButton.clicked.connect(self.pause)
        self.clearIndexButton.clicked.connect(self.clear_index)
        self.refreshButton.clicked.connect(self.refresh)
        self.eventsList.itemDoubleClicked.connect(self.show_event_history)
        self.auto_timer = QTimer(self)
        self.auto_timer.setSingleShot(True)
        self.auto_timer.setInterval(10000)
        self.auto_timer.timeout.connect(self.maybe_organize)
        self.refresh()

    def apply_style(self):
        appearance = self.window.app_settings.get("appearance", {})
        colors = {key: self.window._safe_color(appearance.get(key), default)
                  for key, default in {
                      "background": "#F7F8FC", "surface": "#FFFFFF",
                      "accent": "#4F6FDB", "accent_soft": "#E8EDFF",
                      "text": "#273246", "muted": "#778196", "border": "#E3E8F0",
                  }.items()}
        self.setStyleSheet(f"""
            QWidget#MemorySchemePage {{ background: {colors['background']}; }}
            QFrame#overviewCard, QFrame#recallCard, QFrame#automaticCard,
            QFrame#storageCard, QFrame#maintenanceCard {{
                background: {colors['surface']}; border: 1px solid {colors['border']}; border-radius: 12px;
            }}
            QFrame#totalMetric, QFrame#pendingMetric, QFrame#eventsMetric {{
                background: {colors['background']}; border: 0; border-radius: 8px;
            }}
            QLabel {{ background: transparent; border: 0; }}
            QLabel#schemeTitle {{ font-size: 22px; font-weight: 700; }}
            QLabel#stateBadge {{ background: {colors['accent_soft']}; color: {colors['accent']};
                border-radius: 10px; padding: 5px 12px; max-width: 120px; }}
            QLabel#totalValue, QLabel#pendingValue, QLabel#eventsValue {{
                font-size: 27px; font-weight: 600; color: {colors['text']};
            }}
            QLabel#totalCaption, QLabel#pendingCaption, QLabel#eventsCaption,
            QLabel#descriptionLabel, QLabel#statisticsLabel, QLabel#lastSuccessLabel,
            QLabel#previewLabel, QLabel#recallHelp, QLabel#automaticHelp,
            QLabel#costLabel, QLabel#policyLabel, QLabel#storageHelp, QLabel#maintenanceHelp {{
                color: {colors['muted']}; font-size: 12px;
            }}
            QLabel#storageTitle, QLabel#maintenanceTitle {{ font-size: 15px; font-weight: 600; }}
            QLabel#emptyLabel {{ color: {colors['muted']}; padding: 24px; }}
            QProgressBar {{ border: 0; background: {colors['background']}; border-radius: 4px;
                min-height: 8px; max-height: 8px; }}
            QProgressBar::chunk {{ background: {colors['accent']}; border-radius: 4px; }}
            QPushButton#organizeButton {{ background: {colors['accent']}; color: white; border: 0; font-weight: 600; }}
            QPushButton#organizeButton:disabled {{ background: {colors['border']}; color: {colors['muted']}; }}
            QPushButton#clearIndexButton {{ color: #b14d50; }}
            QTabWidget::pane {{ border: 1px solid {colors['border']}; background: {colors['surface']}; border-radius: 10px; }}
            QTabBar::tab {{ background: transparent; color: {colors['muted']}; padding: 10px 18px; border-bottom: 2px solid transparent; }}
            QTabBar::tab:selected {{ color: {colors['accent']}; border-bottom: 2px solid {colors['accent']}; }}
            QListWidget#eventsList {{ background: {colors['surface']}; border: 0; outline: 0; }}
            QListWidget#eventsList::item {{ background: {colors['background']}; border: 1px solid {colors['border']};
                border-radius: 8px; padding: 12px; }}
            QListWidget#eventsList::item:selected {{ background: {colors['accent_soft']}; color: {colors['text']}; }}
            QCheckBox {{ spacing: 10px; padding: 4px 0; font-weight: 600; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; }}
        """)
        self.coverageProgress.setTextVisible(False)

    def save_preferences(self):
        self.store.save_options(enabled=self.retrievalCheck.isChecked(), auto=self.automaticCheck.isChecked())
        if self.retrievalCheck.isChecked() and self.automaticCheck.isChecked():
            self.auto_retry_blocked = False
        if not self.retrievalCheck.isChecked() or not self.automaticCheck.isChecked():
            self.auto_timer.stop()
            if self.worker is not None and self.worker.automatic:
                self.pause()
        self.refresh()

    def schedule(self):
        if getattr(self.window, '_resetting_data', False):
            return
        if not self.auto_retry_blocked:
            self.auto_timer.start()

    def maybe_organize(self):
        if getattr(self.window, '_resetting_data', False):
            return
        options = self.store.options()
        if self.worker is not None or not options["enabled"] or not options["auto"] or self.auto_retry_blocked:
            return
        if self.window.active_worker is not None or self.window.jobs:
            self.auto_timer.start()
            return
        if self.store.new_count() >= 12:
            self.start(True)

    def start(self, automatic=False):
        if getattr(self.window, '_resetting_data', False):
            return
        if self.worker is not None:
            return
        api = dict(self.window.settings["deepseek"])
        if not api.get("api_key", "").strip():
            self.run_status = "未配置 API，事件整理不可用；原始消息和基础历史查询仍可用"
            self.refresh()
            return
        if not automatic:
            if not FishDialog.question(self.window, "整理历史事件",
                    "将分批使用当前聊天 API 整理尚未处理的对话，每批最多 12 条。\n"
                    "这会产生额外 Token 用量；可随时请求暂停，已经完成的批次会保留。\n"
                    "原始聊天、人物提示词和独立长期记忆不会被修改。",
                    confirm_text="开始整理"):
                return
        self.auto_retry_blocked = False
        self.store.save_options(last_error="")
        self.worker = EventMemoryWorker(self.store, api, self, automatic)
        self.worker.progress.connect(self.on_progress)
        self.worker.failed.connect(self.on_failed)
        self.worker.usage_ready.connect(self.record_usage)
        self.worker.events_changed.connect(self.window.refresh_event_notices)
        self.worker.profiles_changed.connect(self.on_profiles_changed)
        self.worker.finished.connect(self.on_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.run_status = "正在准备事件整理"
        self.worker.start()
        self.refresh()

    def pause(self):
        self.auto_timer.stop()
        if self.worker is not None:
            self.worker.requestInterruption()
            self.run_status = "正在暂停；等待当前 API 请求结束，返回后不再保存该批"
        self.auto_retry_blocked = True
        self.refresh()

    def on_progress(self, text):
        self.run_status = text
        self.refresh()

    def on_profiles_changed(self, count):
        self.window.refresh_memories()
        self.window.memoryStatusLabel.setText(f"标准记忆整理新增 {count} 条长期记忆")
        self.window.add_notice(f"长期记忆已整理 · 新增 {count} 条，可在「长期记忆」查看", memory=True)

    def on_failed(self, text):
        self.auto_retry_blocked = True
        self.run_status = text
        self.refresh()

    def on_finished(self):
        self.worker = None
        self.refresh()

    def record_usage(self, usage):
        data = dict(usage)
        model = data.pop("model", "")
        request_id = data.pop("request_id", "")
        self.window.database.record_api_usage(model, "event_memory", data, request_id)
        self.window.refresh_usage_badge()

    def clear_index(self):
        if self.worker is not None:
            return
        if FishDialog.question(self.window, "清空事件索引",
                "只删除事件摘要、关键词索引和整理进度，原始聊天与独立长期记忆保留。\n"
                "同时暂停自动整理；以后可以重新整理，重新整理会产生 API 用量。",
                confirm_text="清空索引", danger=True):
            self.automaticCheck.setChecked(False)
            self.store.clear_index()
            self.window.refresh_event_notices()
            self.run_status = "事件索引已清空"
            self.refresh()

    def refresh(self):
        stats, options = self.store.stats(), self.store.options()
        path = self.window.database.database_path.resolve()
        size = sum(p.stat().st_size for p in (path, path.with_name(path.name + "-wal")) if p.exists())
        self.storageLabel.setText(f"{path}\n\n占用 {size / 1024 / 1024:.2f} MB（数据库及日志）\n"
                                  f"检索方式：{'中文片段全文索引' if stats['fts'] else '兼容文字匹配'}")
        self.totalValue.setText(f"{stats['total']:,}")
        self.pendingValue.setText(f"{stats['pending']:,}")
        self.eventsValue.setText(f"{stats['events']:,}")
        percent = round(stats['done'] * 100 / stats['total']) if stats['total'] else 0
        self.statisticsLabel.setText(
            f"历史整理覆盖率 {percent}%  ·  已整理 {stats['done']:,} / {stats['total']:,} 条")
        self.serviceLabel.setText(f"摘要服务  ·  {self.window.settings['deepseek'].get('model', '')}  ·  "
                                 f"{'API 已配置' if self.window.settings['deepseek'].get('api_key', '').strip() else '请先在设置中配置 API'}")
        self.coverageProgress.setRange(0, max(1, stats["total"]))
        self.coverageProgress.setValue(stats["done"])
        self.coverageProgress.setFormat("历史整理覆盖率 %p%")
        self.statusLabel.setText(self.run_status
                                 + (f"\n最近错误：{options['last_error']}" if options["last_error"] else ""))
        self.lastSuccessLabel.setText(f"最近整理  ·  {options['last_success'] or '尚无完成记录'}")
        busy = self.worker is not None
        self.stateBadge.setText("整理中" if busy else "需处理" if options["last_error"] else
                                "主动回忆开启" if options["enabled"] else "主动回忆关闭")
        self.organizeButton.setText("整理历史" if not stats["done"] else "继续整理" if stats["pending"] else "已全部整理")
        self.organizeButton.setEnabled(not busy and stats["pending"] > 0)
        self.pauseButton.setEnabled(busy)
        self.clearIndexButton.setEnabled(not busy)
        events = self.store.recent_events()
        self.emptyLabel.setVisible(not events)
        self.eventsList.setVisible(bool(events))
        # 状态刷新不重建相同列表，保留正在阅读的滚动位置。
        snapshot = [(e['id'], e['summary'], e['keywords'], e['status'], e['revision']) for e in events]
        if snapshot == getattr(self, "_events_snapshot", None):
            return
        self._events_snapshot = snapshot
        self.eventsList.clear()
        for event in events:
            channel = "本地对话" if event['conversation_key'] == 'local' else event['conversation_key']
            title = event["title"] or "历史事件"
            status = STATUS_LABELS.get(event["status"], event["status"])
            item = QListWidgetItem(f"{title}  ·  {status}\n{event['summary']}\n\n{' · '.join(json.loads(event['keywords']))}\n{channel}  ·  更新 {event['updated_at'][:10]}")
            item.setData(Qt.ItemDataRole.UserRole, event["id"])
            item.setToolTip(f"双击查看变更记录\n会话：{event['conversation_key']}\n最近更新：{event['updated_at']}")
            self.eventsList.addItem(item)

    def show_event_history(self, item):
        event_id = item.data(Qt.ItemDataRole.UserRole)
        changes = self.store.changes(event_id, limit=100)
        dialog = QDialog(self.window)
        ui = Ui_EventHistoryDialog()
        ui.setupUi(dialog)
        blocks = []
        for change in changes:
            before = STATUS_LABELS.get(change["before_status"], "未记录")
            after = STATUS_LABELS.get(change["after_status"], "未明确")
            blocks.append(
                f"{change['created_at'].replace('T', ' ')[:19]}  ·  {change['title']}\n"
                f"状态：{before} → {after}\n"
                + (f"此前：{change['before_summary']}\n" if change["before_summary"] else "")
                + f"更新后：{change['after_summary']}\n来源消息：{change['source_ids']}")
        ui.historyText.setPlainText("\n\n────────────────────\n\n".join(blocks)
                                   or "这条事件尚无变更记录。下次更新时会保留前后状态。")
        ui.closeButton.clicked.connect(dialog.accept)
        dialog.exec()
