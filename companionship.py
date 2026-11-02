"""Purpose-driven companion decisions and opt-in, on-demand observation."""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import os
import random
import time
from collections import deque
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, QPoint, QBuffer, QIODevice, Qt, QEvent
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QToolButton, QMenu, QSystemTrayIcon, QStyle

DEFAULT_PROACTIVE = {
    "enabled": False,
    "observe_window": True,
    "observe_screen": True,
    "interval_minutes": 5,
    "max_unanswered": 2,
    "allow_actions": True,
    "self_directed": True,
    "away_activities": True,
    "interests_hint": "",
    "notifications": True,
    "notification_sound": True,
    "playful_computer": False,
}


def foreground_state(include_title: bool = True) -> dict:
    if os.name != "nt":
        return {"available": False}
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.OpenInputDesktop.restype = wintypes.HANDLE
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    user32.GetUserObjectInformationW.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    desktop = user32.OpenInputDesktop(0, False, 1)
    if not desktop:
        return {"available": False}
    try:
        name, needed = ctypes.create_unicode_buffer(256), wintypes.DWORD()
        ok = user32.GetUserObjectInformationW(desktop, 2, name, ctypes.sizeof(name), ctypes.byref(needed))
        if not ok or name.value.lower() != "default":
            return {"available": False}
    finally:
        user32.CloseDesktop(desktop)

    class LastInput(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    last = LastInput()
    last.cbSize = ctypes.sizeof(last)
    user32.GetLastInputInfo(ctypes.byref(last))
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetTickCount.restype = wintypes.DWORD
    idle = ((kernel32.GetTickCount() - last.dwTime) & 0xFFFFFFFF) / 1000
    user32.GetForegroundWindow.restype = wintypes.HWND
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"available": False}
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    title = ctypes.create_unicode_buffer(512)
    if include_title:
        user32.GetWindowTextW(hwnd, title, len(title))
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    class MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32)]
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    monitor = MonitorInfo()
    monitor.cbSize = ctypes.sizeof(monitor)
    user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(monitor))
    return {"available": True, "title": title.value, "idle_seconds": int(idle),
            "screen_name": monitor.szDevice, "window_id": int(hwnd),
            "window_rect": (rect.left, rect.top, rect.right, rect.bottom),
            "monitor_rect": (monitor.rcMonitor.left, monitor.rcMonitor.top,
                             monitor.rcMonitor.right, monitor.rcMonitor.bottom),
            "screen_point": (max(0, rect.right - rect.left) // 2 + rect.left,
                             max(0, rect.bottom - rect.top) // 2 + rect.top)}


def screen_image(state: dict) -> dict | None:
    screen = next((s for s in QApplication.screens() if s.name() == state.get("screen_name")), None)
    screen = screen or QApplication.screenAt(QPoint(*state["screen_point"])) or QApplication.primaryScreen()
    if screen is None:
        return None
    pixmap = screen.grabWindow(0)
    if pixmap.isNull():
        return None
    pixmap = pixmap.scaled(1280, 800, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not pixmap.save(buffer, "JPEG", 70):
        return None
    encoded = base64.b64encode(bytes(buffer.data())).decode("ascii")
    state['image_size'] = (pixmap.width(), pixmap.height())
    state['captured_at'] = time.monotonic()
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encoded}}


class ProactiveController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.last_trigger = time.monotonic()
        self.unanswered = 0
        self.failures = 0
        self.unread = 0
        self.last_title = ""
        self.next_due = 0.0
        self.plan_revision = ''
        self.decision_worker = None
        self.epoch = 0
        self.attention_due = 0.0
        self.pending_forced = False
        self.status = '还没有开始新的打算。'
        self.activity_status = ''
        from companion_life import initialize_cursor
        initialize_cursor(window.database)
        from companion_life import overview
        if any(not row['handled'] and row['kind'] != 'conversation' for row in overview(window.database)['events']):
            self.attention_due = time.monotonic()+15
        self._schedule_next()
        from agency import recover
        recover(window.database)
        icon = window.windowIcon()
        if icon.isNull():
            icon = window.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        self.tray = QSystemTrayIcon(icon, window)
        self.tray.setToolTip("鲸伴")
        self.tray.messageClicked.connect(self.open_chat)
        self.tray.activated.connect(self._tray_activated)
        tray_menu = QMenu(window)
        tray_menu.addAction("打开聊天", self.open_chat)
        tray_menu.addAction("收起到托盘", window.hide_to_tray)
        tray_menu.addAction("暂停自主活动", lambda: self.set_enabled(False))
        tray_menu.addAction('停止电脑玩闹（也可按Esc）', lambda: window.computer_play.stop(pause=True))
        tray_menu.addAction('恢复电脑玩闹', lambda: setattr(window.computer_play, 'paused', False))
        tray_menu.addSeparator()
        tray_menu.addAction("退出鲸伴", window.request_exit)
        self.tray.setContextMenu(tray_menu)
        window.installEventFilter(self)
        self.button = QToolButton(window.composerFrame)
        self.button.setMinimumHeight(34)
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self.show_settings)
        self.button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        menu = QMenu(self.button)
        self.enabled_action = QAction("开启鲸鱼心跳", menu)
        self.enabled_action.setCheckable(True)
        self.enabled_action.setChecked(self.options()["enabled"])
        self.enabled_action.toggled.connect(self.set_enabled)
        menu.addAction(self.enabled_action)
        self.now_action = menu.addAction("现在找我聊聊")
        self.now_action.triggered.connect(lambda: self.tick(force=True))
        menu.addAction("暂停自主活动", lambda: self.set_enabled(False))
        menu.addAction("查看她的打算与活动…", self.show_activities)
        menu.addAction("互动设置…", self.show_settings)
        self.button.setMenu(menu)
        window.toolsLayout.insertWidget(window.toolsLayout.indexOf(window.agentMenuButton) + 1, self.button)
        self.refresh()
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def options(self):
        return {**DEFAULT_PROACTIVE, **self.window.settings.get("proactive", {})}

    def refresh(self):
        enabled = self.options()["enabled"]
        from interaction_modes import is_work
        label = "● 鲸鱼心跳" if enabled else "○ 鲸鱼心跳"
        if enabled and is_work(self.window):
            label = '○ 心跳 · 工作暂缓'
        self.button.setStyleSheet("""
            QToolButton { background: %s; color: %s; border: 1px solid %s;
                border-radius: 12px; padding: 6px 23px 6px 12px; font-weight: 600; }
            QToolButton:hover { background: #E0E8FC; color: #344F96; }
            QToolButton::menu-button { width: 18px; border: none; border-left: 1px solid #CBD6ED; }
        """ % (("#EAF0FF", "#3E5FA8", "#C9D6F2") if enabled else
               ("#F3F5F9", "#69768A", "#DEE4EF")))
        self.button.setText(f"{label} · {self.unread} 条未读" if self.unread else label)
        self.button.setToolTip(self.status + "\n点击查看她的打算与互动设置。")
        self.now_action.setEnabled(enabled)
        self.tray.setToolTip(f'鲸伴 · {self.unread} 条未读' if self.unread else '鲸伴')
        # Keep a way back to the application even when heartbeat/alerts are off.
        # Qt re-adds a visible tray icon if Explorer's notification area appears later.
        self.tray.setVisible(True)

    def _schedule_next(self):
        options = self.options()
        from agency import state
        current = state(self.window.database)
        self.plan_revision = current.get('plan_revision', '')
        if self.failures:
            self.next_due = time.monotonic()+60*min(32, 2**min(self.failures, 5))
            return
        if current is not None:
            if current.get('resume_at'):
                try:
                    due = datetime.fromisoformat(current['resume_at']).timestamp()
                    self.next_due = time.monotonic()+max(0, due-datetime.now().timestamp())
                    return
                except (ValueError, TypeError, OverflowError, OSError):
                    pass
            if options['self_directed'] and current.get('status') == 'working' and current.get('next_step'):
                self.next_due = time.monotonic()+random.uniform(5, 15)
                return
        threshold = max(1, int(options["max_unanswered"]))
        backoff = max(1 if options['self_directed'] else min(4, 1 + self.unanswered // threshold),
                      min(8, 2 ** min(self.failures, 3)))
        base = 120  # Bootstrap only; accepted plans supply their own resume_at.
        self.next_due = time.monotonic() + random.uniform(0.5, 1.5) * base * backoff

    def reset_conversation(self):
        self.epoch += 1
        self.attention_due = 0.0
        self.pending_forced = False
        from companion_life import initialize_cursor
        initialize_cursor(self.window.database)
        self.status = '聊天与自己的活动记录已重置。'
        panel = getattr(self.window, 'heartbeat_panel', None)
        if panel is not None:
            panel.reset_data_view()
        self.last_trigger = time.monotonic()
        self.unanswered = self.failures = self.unread = 0
        self.last_title = ''
        self._schedule_next()
        # Discard old notification text as well as its unread badge.
        self.tray.hide()
        self.refresh()

    def open_chat(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()
        self.unread = 0
        self.refresh()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open_chat()

    def eventFilter(self, watched, event):
        if watched is self.window and event.type() == QEvent.Type.WindowActivate and self.unread:
            self.unread = 0
            self.refresh()
        return super().eventFilter(watched, event)

    def notify(self, text, title=None, count_unread=True):
        if self.window.isActiveWindow() and not self.window.isMinimized():
            return
        if count_unread:
            self.unread += 1
        self.refresh()
        if not self.options()["notifications"]:
            return
        name = self.window.app_settings.get("assistant", {}).get("name", "她")
        QApplication.alert(self.window, 0)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
            self.tray.showMessage(title or f"{name}找你聊聊", " ".join(text.split())[:160],
                                  QSystemTrayIcon.MessageIcon.Information, 10000)
        if self.options()["notification_sound"]:
            QApplication.beep()

    def delivered(self, answer):
        self.unanswered += 1
        self.failures = 0
        self._schedule_next()
        self.notify(answer)

    def set_enabled(self, enabled):
        options = self.options()
        options["enabled"] = bool(enabled)
        self.window.settings["proactive"] = options
        self.window.write_config()
        self.enabled_action.blockSignals(True)
        self.enabled_action.setChecked(bool(enabled))
        self.enabled_action.blockSignals(False)
        if not enabled:
            self.cancel_active()
        self.user_spoke()
        self.refresh()

    def cancel_active(self):
        play = getattr(self.window, 'computer_play', None)
        if play:
            play.stop('自主活动已暂停。')
        self.epoch += 1
        self.pending_forced = False
        if self.decision_worker:
            self.decision_worker.requestInterruption()
        self.window.jobs = deque(job for job in self.window.jobs if not job.get('proactive'))
        if (self.window.active_job or {}).get("proactive") and self.window.active_worker:
            episode = (self.window.active_job or {}).get('agency_episode')
            visits = getattr(self.window, 'bilibili_visits', None)
            if episode and visits and visits.session.get('agency_episode') == episode:
                visits.stop_session('自主活动已暂停。', cancel_share=True)
            self.window.active_worker.requestInterruption()
        elif not self.options()['enabled']:
            visits = getattr(self.window, 'bilibili_visits', None)
            if visits and visits.session.get('agency_episode'):
                visits.stop_session('自主活动已暂停。', cancel_share=True)

    def show_activities(self):
        self.show_settings('journal')

    def user_spoke(self):
        self.epoch += 1
        self.pending_forced = False
        if self.decision_worker:
            self.decision_worker.requestInterruption()
        self.last_trigger = time.monotonic()
        self.unanswered = 0
        self.failures = 0
        self._schedule_next()
        # A new conversation can change her priorities even if she previously
        # chose a long rest. This is attention, not an automatic outgoing line.
        self.attention_due = time.monotonic()+random.uniform(30, 90)

    def show_settings(self, section='overview'):
        panel = getattr(self.window, 'heartbeat_panel', None)
        if panel is None:
            return
        self.window.show_page(9)
        panel.open_section(section if isinstance(section, str) else 'overview')

    def invalidate_decision(self):
        self.epoch += 1
        if self.decision_worker:
            self.decision_worker.requestInterruption()

    def update_options(self, changes):
        old = self.options()
        options = {**old, **{key: value for key, value in changes.items() if key in DEFAULT_PROACTIVE}}
        if old == options:
            return
        self.window.settings['proactive'] = options
        self.window.write_config()
        revoked = any(old[key] and not options[key] for key in
                      ('enabled', 'allow_actions', 'observe_window', 'observe_screen', 'self_directed', 'away_activities', 'playful_computer'))
        if revoked:
            self.cancel_active()
        else:
            self.invalidate_decision()
        if options['playful_computer'] and not old['playful_computer']:
            self.window.computer_play.paused = False
        self.enabled_action.blockSignals(True)
        self.enabled_action.setChecked(bool(options['enabled']))
        self.enabled_action.blockSignals(False)
        self._schedule_next()
        if options['interests_hint'] != old['interests_hint']:
            self.wake_for_experience()
        self.refresh()

    def available(self):
        window = self.window
        panel = getattr(window, 'heartbeat_panel', None)
        if panel is not None and panel.has_editor_focus():
            return False
        return not (getattr(window, '_resetting_data', False) or getattr(window, '_closing', False)
                    or window.active_worker or window.jobs or window.attachment_worker
                    or getattr(window, '_history_manager_open', False) or QApplication.activeModalWidget()
                    or window.messageInput.toPlainText().strip() or window.pending_attachments)

    def wake_for_experience(self):
        # A real result can attract attention before an otherwise idle wake.
        # Never interrupt a conversation or a concrete wait for the user's reply.
        if self.options()['enabled']:
            due = time.monotonic()+15
            self.attention_due = min(self.attention_due, due) if self.attention_due else due
        social = getattr(self.window, 'qq_social', None)
        if social is not None:
            social.notice_experience()

    def tick(self, force=False):
        window, options = self.window, self.options()
        from interaction_modes import is_work
        if is_work(window) and not force and not self.pending_forced:
            return
        if not options['enabled']:
            return
        if force:
            self.pending_forced = True
        force = bool(self.pending_forced)
        if force and self.decision_worker:
            self.decision_worker.requestInterruption()
        if not self.available() or self.decision_worker:
            if force:
                self.status = '记着了，当前事情结束后找你聊。'
                self.refresh()
            return
        from chat_flow import pending
        if not force and pending(window.database, 'local'):
            return
        if not window.settings['deepseek'].get('api_key', '').strip():
            return
        from agency import state as own_state
        if own_state(window.database).get('plan_revision', '') != self.plan_revision:
            self._schedule_next()
        due = min(self.next_due, self.attention_due) if self.attention_due else self.next_due
        if not force and time.monotonic() < due:
            return
        self.last_trigger = time.monotonic()
        self._schedule_next()
        # Metadata is cheap; no automatic screenshot or image-model request.
        presence = foreground_state(bool(options['observe_window']))
        away = not presence.get('available') or presence.get('idle_seconds', 0) > 1800
        if away and not force and not (options['away_activities'] and options['self_directed']):
            return
        visits = getattr(window, 'bilibili_visits', None)
        presence['bilibili_busy'] = bool(visits and (visits.worker or visits.pending_request or visits.session_active))
        presence['computer_tools_available'] = bool(options['allow_actions'] and window.agentEnabledCheckBox.isChecked())
        presence['computer_auto_approve'] = bool(presence['computer_tools_available'] and window.agentAutoApproveAction.isChecked())
        presence['computer_play_available'] = bool(options['playful_computer'] and presence['computer_tools_available']
                                                  and not window.computer_play.paused)
        presence['bilibili_enabled'] = bool(visits and window.qq_account_service.snapshot()[0]['browse_bilibili'])
        from social_life import allowed_actions
        qq_service = window.qq_account_service
        qq_options = qq_service.snapshot()[0]
        qq_bridge = qq_service.bridge
        presence['qq_life'] = {'connected': bool(qq_bridge and qq_bridge.isRunning() and qq_bridge._socket is not None),
                               'available_actions': allowed_actions(qq_options)}
        if force:
            self.pending_forced = False
            # An explicit "talk to me" bypasses background planning but keeps
            # the genuine dialogue wait intact until the user actually replies.
            self._queue_turn({'choice': 'talk', 'goal': '用户现在想让你主动找他聊聊',
                              'reason': '用户点击了现在找我聊聊', 'next_step': '接一个具体话题，简短搭话'},
                             presence, forced=True)
            return
        from companion_life import DecisionWorker, snapshot
        material = snapshot(window.database, options, presence, self.unanswered)
        self.attention_due = 0.0
        worker = DecisionWorker(window.settings['deepseek'], material, self)
        self.decision_worker = worker
        worker.epoch = self.epoch
        worker.options_snapshot = options
        worker.ready.connect(self._decision_ready)
        worker.finished.connect(self._decision_finished)
        worker.finished.connect(worker.deleteLater)
        self.status = '在想接下来做什么…'
        self.refresh()
        worker.start()

    def _decision_ready(self, decision):
        from companion_life import latest_input, accept
        from chat_flow import pending
        worker, window = self.decision_worker, self.window
        if not worker or worker is not self.sender():
            return
        if worker.usage:
            window.database.record_api_usage(worker.api['model'], 'companion_decision', worker.usage)
            window.refresh_usage_badge()
            worker.usage_recorded = True
        if (worker.isInterruptionRequested() or worker.epoch != self.epoch or not self.available()
                or not self.options()['enabled'] or pending(window.database, 'local')
                or worker.material['owner'] != window.database._owner_peer
                or worker.material['input_id'] != latest_input(window.database)
                or worker.options_snapshot != self.options()):
            self.status = '情况变了，先接住新的对话，再重新想。'
            self.next_due = max(self.next_due, time.monotonic()+15)
            return
        if decision.get('error'):
            self.failures += 1
            self.status = '这次内部选择未完成：'+decision['error']
            self._schedule_next()
            return
        self.failures = 0
        if decision['choice'] == 'rest':
            accept(window.database, decision)
            self.status = '先歇一会儿 · '+decision['reason']
            self._schedule_next()
        else:
            self._queue_turn(decision, worker.material['presence'], material=worker.material)
        self.refresh()

    def _queue_turn(self, decision, presence, forced=False, material=None):
        from companion_life import decision_context
        from interaction_modes import is_work
        self.activity_status = ''
        notes = decision_context(decision)
        if not presence.get('available'):
            notes += '\n桌面不可读取或已锁屏；只做后台工作，不尝试解锁。'
        if presence.get('bilibili_busy'):
            notes += '\n当前视频漫游仍在运行；不要另起浏览器或抢控制，可消化已经收到的见闻或做后台工作。'
        self.window.jobs.append({'conversation_key': 'local', 'source': 'local', 'peer_id': '', 'peer_name': '',
            'proactive': True, 'proactive_requested': forced, 'self_directed': bool(self.options()['self_directed'] and not is_work(self.window)),
            'observation': [{'type': 'text', 'text': notes}], 'life_decision': decision if not forced else None,
            'life_input_id': material['input_id'] if material else None,
            'life_owner': material['owner'] if material else None})
        self.status = ('想找你聊 · ' if decision['choice'] == 'talk' else '打算做 · ')+decision['goal']
        self.window.start_next_job()

    def _decision_finished(self):
        worker = self.sender()
        if worker is self.decision_worker:
            if worker.usage and not getattr(worker, 'usage_recorded', False):
                self.window.database.record_api_usage(worker.api['model'], 'companion_decision', worker.usage)
                self.window.refresh_usage_badge()
            if worker.isInterruptionRequested() and self.options()['enabled']:
                self.status = '先接住新的情况，稍后重新选择。'
            self.decision_worker = None
        self.refresh()
