from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from workers import AccountBalanceWorker


class FishMascot(QLabel):
    """使用参考角色重新绘制的插图，不再通过几何形状拼脸。"""

    def __init__(self, mood: str = "info", parent=None):
        super().__init__(parent)
        root = Path(__file__).resolve().parent
        try:
            settings = json.loads((root / "app_settings.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            settings = {}
        options = settings.get("dialogs", {})
        path = Path(options.get(mood + "_image", options.get("image", "assets/mascot_v2.png")))
        if not path.is_absolute():
            path = root / path
        self.setFixedSize(96, 104)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: transparent; border: none;")
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            pixmap = QPixmap(str(root / "assets" / "mascot_v2.png"))
        if not pixmap.isNull():
            self.setPixmap(pixmap.scaled(96, 104, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.setAccessibleName({"warning": "请确认操作", "success": "操作完成", "info": "提示"}.get(mood, "提示"))


class FishDialog(QDialog):
    """Small animated message/confirmation window with an original fish illustration."""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        text: str,
        mood: str = "info",
        confirm_text: str | None = None,
        cancel_text: str = "取消",
        danger: bool = False,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(460)
        self.setMaximumWidth(640)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(self)
        card.setObjectName("fishDialogCard")
        card.setStyleSheet(
            "QFrame#fishDialogCard { background:#FFFFFF; border:1px solid #E6EAF2; "
            "border-radius:18px; }"
            "QLabel#fishTitle { color:#24324A; font-size:16px; font-weight:700; border:0; }"
            "QLabel#fishBody { color:#596579; font-size:13px; border:0; }"
            "QPushButton { min-width:82px; min-height:34px; padding:0 14px; border-radius:9px; "
            "border:1px solid #E3E7EF; background:#F8F9FC; color:#38445A; }"
            "QPushButton:hover { background:#EEF3FB; }"
            "QPushButton#fishConfirm { border:0; background:#4E79C6; color:white; font-weight:600; }"
            "QPushButton#fishConfirm:hover { background:#3E68B4; }"
            "QPushButton#fishDanger { border:0; background:#C95C5C; color:white; font-weight:600; }"
            "QPushButton#fishDanger:hover { background:#B84747; }"
        )
        outer.addWidget(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        content = QHBoxLayout()
        content.setSpacing(13)
        self.mascot = FishMascot(mood, card)
        content.addWidget(self.mascot, 0, Qt.AlignmentFlag.AlignTop)
        text_column = QVBoxLayout()
        text_column.setSpacing(7)
        title_label = QLabel(title, card)
        title_label.setObjectName("fishTitle")
        title_label.setWordWrap(True)
        body_label = QLabel(text, card)
        body_label.setObjectName("fishBody")
        body_label.setWordWrap(True)
        body_label.setTextFormat(Qt.TextFormat.PlainText)
        body_label.setMaximumWidth(440)
        body_label.setMinimumWidth(280)
        body_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text_column.addWidget(title_label)
        text_column.addWidget(body_label)
        content.addLayout(text_column, 1)
        layout.addLayout(content)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        if confirm_text is not None:
            cancel_button = QPushButton(cancel_text, card)
            cancel_button.clicked.connect(self.reject)
            cancel_button.setDefault(True)
            buttons.addWidget(cancel_button)
        action_button = QPushButton(confirm_text or "知道了", card)
        action_button.setObjectName("fishDanger" if danger else "fishConfirm")
        action_button.clicked.connect(self.accept)
        action_button.setAutoDefault(confirm_text is None)
        buttons.addWidget(action_button)
        layout.addLayout(buttons)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(140)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._rise = QPropertyAnimation(self, b"pos", self)
        self._rise.setDuration(150)
        self._rise.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        target = self.pos()
        self.move(target.x(), target.y() + 4)
        self.setWindowOpacity(0.0)
        self._fade.start()
        self._rise.setStartValue(self.pos())
        self._rise.setEndValue(target)
        self._rise.start()

    @classmethod
    def information(cls, parent: QWidget, title: str, text: str, mood: str = "info") -> None:
        cls(parent, title, text, mood=mood).exec()

    @classmethod
    def question(
        cls,
        parent: QWidget,
        title: str,
        text: str,
        confirm_text: str = "继续",
        danger: bool = False,
    ) -> bool:
        mood = "warning" if danger else "info"
        return cls(
            parent, title, text, mood=mood, confirm_text=confirm_text,
            cancel_text="取消", danger=danger,
        ).exec() == QDialog.DialogCode.Accepted


class UsageDialog(QDialog):
    """Displays locally recorded token usage and the live DeepSeek account balance."""

    def __init__(self, database, api_settings: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.database = database
        self.api_settings = dict(api_settings)
        self.balance_worker: AccountBalanceWorker | None = None
        self.setWindowTitle("API 用量与余额")
        self.setMinimumWidth(510)
        self.setStyleSheet(
            "QDialog { background:#F7F8FB; }"
            "QLabel#usageTitle { color:#26354D; font-size:18px; font-weight:700; }"
            "QLabel#usageHint { color:#7B8494; font-size:11px; }"
            "QFrame#usageCard { background:white; border:1px solid #E5E9F0; border-radius:14px; }"
            "QLabel#usageCardTitle { color:#647087; font-size:12px; font-weight:600; }"
            "QLabel#usageValue { color:#243B63; font-size:21px; font-weight:700; }"
            "QLabel#balanceValue { color:#2864A8; font-size:15px; font-weight:700; }"
            "QPushButton { min-height:34px; padding:0 13px; border:1px solid #DCE2EC; "
            "border-radius:9px; background:white; color:#35445B; }"
            "QPushButton:hover { background:#EEF3FB; }"
            "QPushButton#balanceRefresh { background:#4E79C6; color:white; border:0; font-weight:600; }"
            "QPushButton#balanceRefresh:hover { background:#3E68B4; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(13)

        header = QHBoxLayout()
        header.addWidget(FishMascot("info", self), 0, Qt.AlignmentFlag.AlignTop)
        title_column = QVBoxLayout()
        title = QLabel("API 用量与余额", self)
        title.setObjectName("usageTitle")
        hint = QLabel("累计包含聊天、记忆整理及自主活动。输入含角色、上下文和工具；缓存命中属于输入，不另加一次。", self)
        hint.setObjectName("usageHint")
        hint.setWordWrap(True)
        title_column.addWidget(title)
        title_column.addWidget(hint)
        header.addLayout(title_column, 1)
        layout.addLayout(header)

        self.today_card, self.today_value = self._usage_card("今日 Token", self)
        self.all_card, self.all_value = self._usage_card("累计 Token", self)
        usage_row = QHBoxLayout()
        usage_row.setSpacing(10)
        usage_row.addWidget(self.today_card)
        usage_row.addWidget(self.all_card)
        layout.addLayout(usage_row)

        self.breakdown_label = QLabel(self)
        self.breakdown_label.setObjectName("usageHint")
        self.breakdown_label.setWordWrap(True)
        layout.addWidget(self.breakdown_label)

        balance_card = QFrame(self)
        balance_card.setObjectName("usageCard")
        balance_layout = QVBoxLayout(balance_card)
        balance_layout.setContentsMargins(16, 13, 16, 13)
        balance_layout.setSpacing(6)
        balance_heading = QLabel("账户余额", balance_card)
        balance_heading.setObjectName("usageCardTitle")
        self.balance_value = QLabel("尚未查询", balance_card)
        self.balance_value.setObjectName("balanceValue")
        self.balance_detail = QLabel("", balance_card)
        self.balance_detail.setObjectName("usageHint")
        self.balance_detail.setWordWrap(True)
        balance_layout.addWidget(balance_heading)
        balance_layout.addWidget(self.balance_value)
        balance_layout.addWidget(self.balance_detail)
        layout.addWidget(balance_card)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.refresh_button = QPushButton("查询余额", self)
        self.refresh_button.setObjectName("balanceRefresh")
        close_button = QPushButton("关闭", self)
        self.refresh_button.clicked.connect(self.refresh_balance)
        close_button.clicked.connect(self.accept)
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        self.refresh_usage()
        self.refresh_balance()

    @staticmethod
    def _usage_card(title_text: str, parent: QWidget) -> tuple[QFrame, QLabel]:
        card = QFrame(parent)
        card.setObjectName("usageCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 13, 16, 13)
        card_layout.setSpacing(5)
        heading = QLabel(title_text, card)
        heading.setObjectName("usageCardTitle")
        value = QLabel("0", card)
        value.setObjectName("usageValue")
        card_layout.addWidget(heading)
        card_layout.addWidget(value)
        return card, value

    def refresh_usage(self) -> None:
        summary = self.database.api_usage_summary()
        today = summary["today"]
        total = summary["all_time"]
        self.today_value.setText(f"{int(today['total_tokens']):,}")
        self.all_value.setText(f"{int(total['total_tokens']):,}")
        self.breakdown_label.setText(
            f"今日：输入 {int(today['prompt_tokens']):,} · 输出 {int(today['completion_tokens']):,} · "
            f"缓存命中 {int(today['cached_tokens']):,}\n"
            f"累计：输入 {int(total['prompt_tokens']):,} · 输出 {int(total['completion_tokens']):,} · "
            f"用量记录 {int(total['requests']):,} 条"
        )
        details = self.database.api_usage_details()
        kinds = details['today_by_kind']
        chats = sum(kinds.get(kind, 0) for kind in ('chat', 'qq_chat'))
        memory = sum(kinds.get(kind, 0) for kind in ('memory', 'event_memory', 'memory_extraction'))
        other = sum(kinds.values())-chats-memory
        text = self.breakdown_label.text()+f"\n今日分类：对话 {chats:,} · 记忆整理 {memory:,} · 自主活动及其他 {other:,}"
        latest = details['latest_chat']
        if latest:
            text += (f"\n最近一次对话：输入 {latest['prompt_tokens']:,} · 输出 {latest['completion_tokens']:,} · "
                     f"合计 {latest['total_tokens']:,}（含工具往返和思考补充）")
        self.breakdown_label.setText(text)

    def refresh_balance(self) -> None:
        if self.balance_worker is not None and self.balance_worker.isRunning():
            return
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("查询中…")
        self.balance_value.setText("正在连接 DeepSeek…")
        self.balance_detail.setText("")
        worker = AccountBalanceWorker(self.api_settings, self)
        self.balance_worker = worker
        worker.balance_ready.connect(self._show_balance)
        worker.balance_failed.connect(self._show_balance_error)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(self._balance_worker_finished)
        worker.start()

    def _balance_worker_finished(self) -> None:
        self.balance_worker = None
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("重新查询")

    def _show_balance(self, payload: dict) -> None:
        infos = payload.get("balance_infos", [])
        if not infos:
            self.balance_value.setText("暂无可显示的余额")
            self.balance_detail.setText("接口没有返回余额明细。")
            return
        formatted = []
        details = []
        for info in infos:
            currency = str(info.get("currency", ""))
            total = str(info.get("total_balance", "0"))
            formatted.append(f"{total} {currency}".strip())
            granted = str(info.get("granted_balance", "0"))
            topped_up = str(info.get("topped_up_balance", "0"))
            details.append(f"赠金 {granted} {currency} · 充值 {topped_up} {currency}")
        availability = "可正常调用" if payload.get("is_available") else "余额不足"
        self.balance_value.setText("　/　".join(formatted))
        self.balance_detail.setText(f"{availability} · " + "\n".join(details))

    def _show_balance_error(self, message: str) -> None:
        self.balance_value.setText("暂时无法查询")
        self.balance_detail.setText(message[:260])

    def closeEvent(self, event) -> None:
        if self.balance_worker is not None and self.balance_worker.isRunning():
            self.balance_worker.requestInterruption()
            self.balance_worker.wait(1000)
        super().closeEvent(event)
