"""DSH compatibility catalog and its dedicated plugin-management page."""
from __future__ import annotations

from collections import deque
from datetime import datetime
import json
from pathlib import Path
import re
import time
import uuid
import urllib.parse

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame, QGridLayout,
                              QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton,
                              QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from dialogs import FishDialog
from dsh_packages import checked_dir, import_package, inspect_package, read_json, write_json, entry_file
from dsh_runtime import CordisBackend, install_runtime, runtime_ready, prepare_plugin, dependencies_ready


class DshTask(QThread):
    progress = Signal(str)

    def __init__(self, root, action, source=None, parent=None):
        super().__init__(parent)
        self.root, self.action, self.source = root, action, source
        self.result, self.error = None, ''

    def run(self):
        try:
            args = (self.progress.emit, self.isInterruptionRequested)
            if self.action == 'runtime':
                self.result = install_runtime(self.root, *args)
            elif self.action in ('prepare', 'repair'):
                self.result = prepare_plugin(self.root, self.source, *args, force=self.action == 'repair')
            else:
                self.result = import_package(self.root, self.source, *args)
        except Exception as error:
            self.error = str(error)


class PluginBalanceWorker(QThread):
    def __init__(self, api, parent):
        super().__init__(parent)
        self.api, self.result = dict(api), {}

    def run(self):
        from app_controls import balance
        try:
            self.result = balance(self.api, self.isInterruptionRequested)
        except Exception:
            self.result = {'error': '余额查询未成功，请检查鲸伴中的官方API连接与密钥。'}


class DshManager(QObject):
    changed = Signal()
    log_added = Signal(str)
    progress = Signal(str)
    task_stopped = Signal()

    def __init__(self, native):
        super().__init__(native)
        self.native, self.window, self.root = native, native.window, native.root
        self.app_version, self.events = native.app_version, native.events
        self.storage = checked_dir(self.root, 'data/dsh')
        self.directory = checked_dir(self.root, 'data/dsh/packages')
        self.log_directory = checked_dir(self.root, 'data/dsh/logs')
        try:
            self.preferences = read_json(self.storage / 'settings.json')
        except (OSError, ValueError):
            self.preferences = {}
        self.preferences = {key: value for key, value in self.preferences.items()
                            if re.fullmatch('[0-9a-f]{20}', key) and isinstance(value, dict)}
        for value in self.preferences.values():
            if not isinstance(value.get('config', {}), dict):
                value['config'] = {}
        self.records, self.active, self.errors = {}, {}, {}
        self.logs = deque(maxlen=600)
        self.worker = None
        self.balance_worker, self.balance_waiters = None, []
        self.balance_cache, self.web_dialogs = None, {}
        self.balance_signature = None
        self._stopping = False
        self._log_second, self._log_count = 0, 0
        self.scan()
        for name in ('message', 'voice_state', 'chat_state', 'data_cleared'):
            self.events[name].connect(lambda *args, key=name: self._forward(key, args[0] if args else None))

    @staticmethod
    def key(value):
        value = str(value).removeprefix('dsh_')
        if not re.fullmatch('[0-9a-f]{20}', value):
            raise ValueError('无效的 DSH 插件标识。')
        return value

    def _save(self):
        write_json(self.storage / 'settings.json', self.preferences)

    def scan(self):
        records = {}
        for directory in sorted(self.directory.iterdir()):
            if not directory.is_dir() or not re.fullmatch('[0-9a-f]{20}', directory.name):
                continue
            try:
                if directory.resolve() != directory:
                    raise ValueError('插件目录不能是链接。')
                report = read_json(directory / 'report.json')
                if report.get('id') != directory.name:
                    raise ValueError('插件导入记录损坏，请重新导入。')
                fresh = {**inspect_package(directory / 'package'), 'id': directory.name}
                if report.get('adapter') == 'pet':
                    # Switching from the old native renderer must not authorize new JS code.
                    self.preferences.setdefault(directory.name, {})['enabled'] = False
                    self._save()
                if report != fresh:
                    write_json(directory / 'report.json', fresh)
                report = fresh
                records[directory.name] = report
            except Exception as error:
                self.append_log(directory.name, str(error))
        self.records = records
        self.changed.emit()

    def append_log(self, key, text):
        second = int(time.monotonic())
        if second != self._log_second:
            self._log_second, self._log_count = second, 0
        self._log_count += 1
        if self._log_count > 80:
            return
        name = self.records.get(key, {}).get('name', key)
        line = f'[{datetime.now():%H:%M:%S}] [{name}] {str(text)[:14000]}'
        self.logs.append(line)
        self.log_added.emit(line)
        try:
            path = self.log_directory / 'runtime.log'
            if path.exists() and path.stat().st_size > 2 * 1024**2:
                path.replace(self.log_directory / 'runtime.previous.log')
            with path.open('a', encoding='utf-8') as stream:
                stream.write(line + '\n')
        except OSError:
            pass

    def is_busy(self):
        return self.worker is not None or self.balance_worker is not None

    def begin(self, action, source=None):
        if self.is_busy():
            raise ValueError('正在处理上一项导入或安装，请等待完成或取消。')
        if self._stopping:
            raise ValueError('插件正在停止，请等待程序退出。')
        if action == 'runtime' and self.active:
            raise ValueError('请先停用后台插件，再安装或整理运行环境。')
        if action in ('prepare', 'repair') and self.active and not runtime_ready(self.root):
            raise ValueError('共享环境需要升级，请先停用已运行的插件。')
        if action in ('prepare', 'repair') and source in self.active:
            raise ValueError('请先停用插件，再准备其依赖。')
        self.worker = DshTask(self.root, action, source, self)
        self.worker.progress.connect(self._progress)
        self.worker.finished.connect(self._task_finished)
        self.worker.start()
        self.changed.emit()

    def _progress(self, text):
        self.progress.emit(text)

    def cancel(self):
        if self.balance_worker:
            self.balance_worker.requestInterruption()
        if self.worker:
            self.worker.requestInterruption()
            self.progress.emit('正在取消，请等待当前下载或文件处理结束…')

    def _task_finished(self):
        worker, self.worker = self.worker, None
        if worker:
            if worker.error:
                self.append_log('系统', worker.error)
                if worker.action in ('prepare', 'repair'):
                    self.errors[worker.source] = worker.error
                self.progress.emit(worker.error)
            else:
                result = worker.result or {}
                if worker.action in ('prepare', 'repair'):
                    self.errors.pop(worker.source, None)
                text = result.get('message') or f"已导入 {result.get('name', '插件')}，默认停用；{result.get('status', '')}。"
                self.append_log('系统', text)
                self.progress.emit(text)
            worker.deleteLater()
        self.scan()
        if worker and not worker.error and worker.action == 'prepare' and not self._stopping:
            try:
                self.set_enabled(worker.source, True)
            except Exception as error:
                self.runtime_error(worker.source, error)
        self.task_stopped.emit()

    def start_enabled(self):
        for key in list(self.records):
            if self.preferences.get(key, {}).get('enabled') is True:
                try:
                    self.set_enabled(key, True)
                except Exception as error:
                    self.runtime_error(key, error)

    def set_enabled(self, key, enabled):
        key = self.key(key)
        if self._stopping:
            return
        if enabled:
            if key in self.active:
                return
            report = self.records[key]
            kind = report['adapter']
            if kind == 'unsupported':
                raise ValueError('当前未适配此插件，请查看兼容说明。')
            self.errors.pop(key, None)
            directory = self.directory / key
            if directory.resolve() != directory:
                raise ValueError('插件目录不能是链接。')
            meta = read_json(directory / 'package' / 'package.json')
            if entry_file(directory / 'package', meta, report['entry']) != report['entry']:
                raise ValueError('插件入口发生变化，请重新导入。')
            if not runtime_ready(self.root) or not dependencies_ready(self.root, key, meta):
                self.begin('prepare', key)
                return
            config = self.preferences.get(key, {}).get('config', {})
            instance = CordisBackend(self.root, directory / 'package', report, config, self,
                                     reply_bubbles=self.preferences.get(key, {}).get('reply_bubbles', True))
            self.active[key] = {'kind': kind, 'instance': instance, 'state': '正在启动'}
            instance.log.connect(lambda text: self.append_log(key, text))
            instance.ready.connect(lambda: self._ready(key))
            instance.failed.connect(lambda text: self.runtime_error(key, text))
            instance.stopped.connect(lambda: self._backend_stopped(key, instance))
            instance.balance_requested.connect(lambda request_id, backend=instance: self.query_balance(backend, request_id))
            instance.web_requested.connect(lambda value, k=key: self.show_web(k))
            try:
                instance.start()
            except Exception:
                self.active.pop(key, None)
                instance.deleteLater()
                raise
            self.preferences.setdefault(key, {})['enabled'] = True
            self.append_log(key, '正在加载原版插件入口…')
        else:
            runtime = self.active.get(key)
            if runtime:
                runtime['state'] = '正在停止'
                runtime['instance'].stop()
            self.preferences.setdefault(key, {})['enabled'] = False
            self.append_log(key, '已请求停用')
        self._save()
        self.changed.emit()

    def _ready(self, key):
        if key in self.active:
            self.active[key]['state'] = '运行中'
            self.changed.emit()
            if self.records[key].get('web_compat') == 'whale-widget':
                QTimer.singleShot(250, lambda: self.show_web(key) if key in self.active else None)

    def _backend_stopped(self, key, instance):
        if self.active.get(key, {}).get('instance') is instance:
            self.active.pop(key, None)
            dialog = self.web_dialogs.pop(key, None)
            if dialog:
                dialog.close()
            instance.deleteLater()
            self.changed.emit()
            if self._stopping and not self.active and not self.worker:
                self.task_stopped.emit()

    def runtime_error(self, key, error):
        if self._stopping:
            return
        key = self.key(key)
        self.errors[key] = str(error)
        self.append_log(key, str(error))
        self.preferences.setdefault(key, {})['enabled'] = False
        try:
            self._save()
        except OSError as save_error:
            self.append_log(key, '未能保存停用状态：' + str(save_error))
        QTimer.singleShot(0, lambda: self._stop_failed(key))
        self.changed.emit()

    def _stop_failed(self, key):
        try:
            self.set_enabled(key, False)
        except Exception as error:
            self.append_log(key, '停用时遇到错误：' + str(error))

    def _forward(self, name, value):
        pet_value = value
        if name == 'message':
            if not isinstance(value, dict) or value.get('source') != 'local':
                return
            content = str(value.get('content', ''))
            value = {**value, 'content': content[:8000]}
            pet_value = {**value, 'content': value['content'] + ('\n（其余内容请在鲸伴聊天窗口查看）' if len(content) > 8000 else '')}
        for key, runtime in list(self.active.items()):
            if runtime['kind'] == 'cordis' and (name == 'data_cleared' or self.preferences.get(key, {}).get('chat_events', False)):
                runtime['instance'].publish_event(name, value)
            elif (runtime['kind'] == 'standalone'
                  and self.records.get(key, {}).get('command') == 'dsh-pet-standalone'
                  and (name == 'data_cleared' or name == 'message'
                       and self.preferences.get(key, {}).get('reply_bubbles', True))):
                runtime['instance'].publish_event(name, pet_value)

    def remove(self, key):
        key = self.key(key)
        if key in self.active or self.is_busy():
            raise ValueError('请先停用插件并等待后台任务结束。')
        source = self.directory / key
        if source.resolve() != source:
            raise ValueError('插件路径异常。')
        removed = checked_dir(self.root, 'data/dsh/removed')
        source.rename(removed / (key + '-' + uuid.uuid4().hex[:10]))
        self.preferences.setdefault(key, {})['enabled'] = False
        self._save()
        self.append_log(key, '已移至 removed 目录，独立设置保留。')
        self.scan()

    def request_shutdown(self):
        if self._stopping:
            return
        self._stopping = True
        self.cancel()
        if self.balance_worker:
            self.balance_worker.requestInterruption()
        for dialog in list(self.web_dialogs.values()):
            dialog.close()
        for runtime in list(self.active.values()):
            runtime['state'] = '正在停止'
            runtime['instance'].stop()
        self.changed.emit()

    def shutdown(self):
        self.request_shutdown()
        if self.worker:
            self.worker.requestInterruption()
            self.worker.wait()
        if self.balance_worker:
            self.balance_worker.requestInterruption()
            self.balance_worker.wait()
        for runtime in list(self.active.values()):
            runtime['instance'].shutdown()
        self.active.clear()

    def open_interface(self, key, *, automatic=False):
        runtime = self.active.get(key)
        report = self.records[key]
        if not runtime or not runtime['instance'].is_ready or not report.get('interface_file'):
            raise ValueError('插件尚未提供可打开的界面。请先启用并等待启动完成。')
        web = bool(report.get('web_compat'))
        state = read_json(runtime['instance'].web_interface if web else self.storage / 'state' / report['interface_file'])
        if state.get('pid') != runtime['instance'].process.processId():
            raise ValueError('插件界面状态已过期，请重新启用。')
        port, token = state.get('port'), state.get('token')
        if type(port) is not int or not 1 <= port <= 65535 or not isinstance(token, str) or len(token) > 256:
            raise ValueError('插件界面状态无效。')
        url = f'http://127.0.0.1:{port}/' + ('' if web else 'standalone-ai/') + '#token=' + urllib.parse.quote(token, safe='')
        if not web:
            QDesktopServices.openUrl(QUrl(url))
            return
        if report.get('web_compat') == 'whale-widget':
            preferences = self.preferences.setdefault(key, {})
            mode = preferences.get('widget_surface', 'window')
            restored_hidden = False
            if mode not in ('window', 'desktop', 'hidden'):
                mode = 'window'
            if mode == 'hidden' and not automatic:
                mode = 'window'
                preferences['widget_surface'] = mode
                self._save()
                restored_hidden = True
            surface = self.web_dialogs.get(key)
            if surface is None:
                try:
                    from whale_widget_host import WhaleWidgetSurface
                    surface = WhaleWidgetSurface(self.window, url, mode, preferences.get('widget_positions', {}), self)
                except ImportError as error:
                    raise ValueError('缺少透明挂件运行组件，请修复应用环境。') from error
                self.web_dialogs[key] = surface
                surface.closed.connect(lambda: self.web_dialogs.pop(key, None) if self.web_dialogs.get(key) is surface else None)
                surface.mode_changed.connect(lambda value: self.set_widget_surface(key, value))
                surface.position_changed.connect(lambda where, position: self.save_widget_position(key, where, position))
                surface.problem.connect(lambda message: self.append_log(key, message))
            elif surface.mode != mode:
                surface.set_mode(mode)
            surface.show()
            if restored_hidden:
                self.changed.emit()
            return
        dialog = self.web_dialogs.get(key)
        if dialog:
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            return
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            QDesktopServices.openUrl(QUrl(url))
            return
        dialog = QDialog(self.window)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setWindowTitle(report['name'] + ' · 插件网页')
        dialog.resize(940, 700)
        layout = QVBoxLayout(dialog)
        if report.get('web_compat') == 'pet':
            restore = QPushButton('恢复桌面显示', dialog)
            restore.clicked.connect(lambda: self.restore_pet(key))
            layout.addWidget(restore)
        view = QWebEngineView(dialog)
        layout.addWidget(view, 1)
        # A plugin may navigate its own page; open other origins in the browser.
        from PySide6.QtWebEngineCore import QWebEnginePage
        class LocalPage(QWebEnginePage):
            def acceptNavigationRequest(self, target, kind, main):
                if main and (target.host() != '127.0.0.1' or target.port() != port or target.scheme() != 'http'):
                    if target.scheme() in ('http', 'https'):
                        QDesktopServices.openUrl(target)
                    return False
                return True
        view.setPage(LocalPage(view))
        self.web_dialogs[key] = dialog
        dialog.destroyed.connect(lambda: self.web_dialogs.pop(key, None))
        view.setUrl(QUrl(url))
        dialog.show()

    def show_web(self, key):
        if (self.records.get(key, {}).get('web_compat') != 'whale-widget'
                and getattr(self.window, '_tray_session', False) and not self.window.isVisible()):
            self.append_log(key, '网页界面已就绪；鲸伴驻留托盘时不弹窗，可在插件页手动打开。')
            return
        if not self._stopping:
            try:
                self.open_interface(key, automatic=True)
            except Exception as error:
                self.append_log(key, str(error))

    def set_widget_surface(self, key, mode):
        if mode not in ('window', 'desktop', 'hidden') or self._stopping:
            return
        preferences = self.preferences.setdefault(key, {})
        changed = preferences.get('widget_surface', 'window') != mode
        preferences['widget_surface'] = mode
        if changed:
            self._save()
        surface = self.web_dialogs.get(key)
        if surface is not None and getattr(surface, 'mode', None) != mode:
            surface.set_mode(mode)
        elif surface is None and key in self.active:
            self.show_web(key)
        if changed:
            self.changed.emit()

    def save_widget_position(self, key, mode, position):
        if self._stopping or mode not in ('window', 'desktop'):
            return
        positions = self.preferences.setdefault(key, {}).setdefault('widget_positions', {})
        if not isinstance(positions, dict):
            positions = self.preferences[key]['widget_positions'] = {}
        positions[mode] = list(position)
        self._save()

    def reload_widget(self, key):
        surface = self.web_dialogs.get(key)
        if surface is not None and hasattr(surface, 'reload'):
            surface.reload()
        else:
            self.open_interface(key)

    def restore_pet(self, key):
        runtime = self.active.get(key)
        if runtime and runtime['instance'].is_ready:
            runtime['instance'].send({'type': 'pet-restore'})

    def query_balance(self, backend, request_id):
        if not re.fullmatch('[0-9a-f]{24}', request_id) or self._stopping:
            return
        import hashlib
        api = self.window.settings['deepseek']
        signature = hashlib.sha256((str(api.get('base_url'))+'\0'+str(api.get('api_key'))).encode()).hexdigest()
        if signature != self.balance_signature:
            self.balance_cache = None
            self.balance_signature = signature
        if self.balance_cache and time.monotonic()-self.balance_cache[0] < 30:
            backend.send({'type': 'balance-result', 'id': request_id, 'result': self.balance_cache[1]})
            return
        if len(self.balance_waiters) >= 50:
            backend.send({'type': 'balance-result', 'id': request_id, 'result': {'error': '余额查询繁忙，请稍后再试。'}})
            return
        self.balance_waiters.append((backend, request_id))
        if not self.balance_worker:
            self.balance_worker = PluginBalanceWorker(self.window.settings['deepseek'], self)
            self.balance_worker.signature = signature
            self.balance_worker.finished.connect(self._balance_finished)
            self.balance_worker.start()

    def _balance_finished(self):
        worker, self.balance_worker = self.balance_worker, None
        if not worker:
            return
        result = worker.result
        import hashlib
        api = self.window.settings['deepseek']
        signature = hashlib.sha256((str(api.get('base_url'))+'\0'+str(api.get('api_key'))).encode()).hexdigest()
        if signature != worker.signature:
            result = {'error': 'API连接已变化，请重新刷新余额。'}
        if not result.get('error'):
            self.balance_cache = (time.monotonic(), result)
        waiters, self.balance_waiters = self.balance_waiters, []
        for backend, request_id in waiters:
            if not self._stopping and any(r['instance'] is backend for r in self.active.values()):
                backend.send({'type': 'balance-result', 'id': request_id, 'result': result})
        worker.deleteLater()
        self.changed.emit()
        self.task_stopped.emit()


class DshPage(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setMinimumWidth(0)
        outer.addWidget(self.scroll)
        content = QWidget(self.scroll)
        content.setMinimumWidth(0)
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        box = QVBoxLayout(content)
        box.setContentsMargins(8, 10, 16, 12)
        box.setSpacing(10)
        self.scroll.setWidget(content)
        heading = QLabel('DSH 插件兼容', content)
        heading.setStyleSheet('font-size:22px; font-weight:700; color:#2C3E63;')
        box.addWidget(heading)
        intro = self.label(box, '导入原版插件包，识别可运行的独立入口或 Cordis 后台入口。首次启用自动准备依赖，插件保留自己的代码和界面。', content)
        intro.setStyleSheet('color:#8A93A6; font-size:12px; line-height:150%;')
        intro_contents = intro
        self.tools = QGridLayout()
        self.tools.setSpacing(8)
        self.tool_buttons = []
        self._tool_columns = 0
        self.card_tools = []
        self.import_buttons = []
        for title, callback in [('导入插件文件夹', self.import_folder), ('导入 ZIP / TGZ', self.import_archive)]:
            button = QPushButton(title, content)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet('QPushButton {background:#3E5FA8; color:#fff; border:none; border-radius:8px; padding:8px 14px; font-weight:600;}'
                                 'QPushButton:hover {background:#4E6FB8;} QPushButton:disabled {background:#B9C4DE;}')
            button.clicked.connect(callback)
            self.import_buttons.append(button)
            self.tool_buttons.append(button)
        self.cancel_button = QPushButton('取消当前任务', content)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(manager.cancel)
        self.runtime_button = QPushButton('准备共享运行环境', content)
        self.runtime_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.runtime_button.clicked.connect(lambda: self.begin('runtime'))
        self.tool_buttons.append(self.runtime_button)
        for title, callback in [('刷新列表', manager.scan), ('打开存储 / 日志目录', self.open_storage)]:
            button = QPushButton(title, content)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(callback)
            self.tool_buttons.append(button)
        self.tool_buttons.append(self.cancel_button)
        for button in self.tool_buttons:
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            if button not in self.import_buttons:
                button.setStyleSheet(
                    'QPushButton {background:#F2F5FB; color:#4A5A80; border:1px solid #DDE4F0; border-radius:8px; padding:7px 14px;}'
                    'QPushButton:hover {background:#E6ECF8; color:#34466C;}'
                    'QPushButton:disabled {color:#A6B0C4; background:#F5F7FB; border-color:#E6EAF2;}')
        box.addLayout(self.tools)
        self.runtime_label = QLabel(content)
        self.runtime_label.setMinimumWidth(0)
        self.runtime_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.runtime_label.setWordWrap(True)
        self.runtime_label.setStyleSheet('color:#6B7A99; font-size:12px;')
        box.addWidget(self.runtime_label)
        self.status = QLabel('导入默认停用。选择插件后点击启用；缺少的运行环境和依赖会自动准备。', content)
        self.status.setMinimumWidth(0)
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Preferred)
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setStyleSheet('color:#8A93A6; font-size:12px; padding:2px 0;')
        box.addWidget(self.status)
        self.progress_bar = QProgressBar(content)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet('QProgressBar {background:#E8EDF6; border:none; border-radius:2px;}'
                                        'QProgressBar::chunk {background:#526BC3; border-radius:2px;}')
        box.addWidget(self.progress_bar)
        self.card_container = QWidget(content)
        self.card_container.setMinimumWidth(0)
        self.card_container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.cards = QVBoxLayout(self.card_container)
        self.cards.setContentsMargins(0, 4, 0, 4)
        self.cards.setSpacing(10)
        box.addWidget(self.card_container)
        self.log_toggle = QToolButton(content)
        self.log_toggle.setText('  运行日志')
        self.log_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.log_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.log_toggle.setCheckable(True)
        self.log_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.log_toggle.setStyleSheet('QToolButton {color:#6B7A99; font-size:12px; padding:4px 2px; border:none;}'
                                      'QToolButton:hover {color:#3E5FA8;}')
        box.addWidget(self.log_toggle)
        self.log_edit = QPlainTextEdit(content)
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(600)
        self.log_edit.setMinimumSize(0, 160)
        self.log_edit.setMaximumHeight(260)
        self.log_edit.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.log_edit.setStyleSheet('QPlainTextEdit {background:#F7F8FB; border:1px solid #E6EAF2; border-radius:8px;'
                                    ' color:#5A6A8C; font-family:Consolas,monospace; font-size:11px; padding:6px;}'
                                    'QPlainTextEdit:focus {border-color:#B9C4DE;}')
        self.log_edit.setPlainText('\n'.join(manager.logs))
        self.log_edit.hide()
        self.log_toggle.toggled.connect(self.show_logs)
        box.addWidget(self.log_edit)
        box.addStretch()
        manager.changed.connect(self.refresh)
        manager.progress.connect(self.status.setText)
        manager.log_added.connect(self.log_edit.appendPlainText)
        self.refresh()

    def show_logs(self, checked):
        self.log_edit.setVisible(checked)
        self.log_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'log_toggle'):
            self.reflow()

    def reflow(self):
        width = self.scroll.viewport().width()
        columns = 3 if width >= 840 else 2 if width >= 420 else 1
        if columns != self._tool_columns:
            self._tool_columns = columns
            while self.tools.count():
                self.tools.takeAt(0)
            for index, button in enumerate(self.tool_buttons):
                self.tools.addWidget(button, index // columns, index % columns)
            for column in range(3):
                self.tools.setColumnStretch(column, 1 if column < columns else 0)
        for grid, buttons in self.card_tools:
            count = 2 if width >= 420 else 1
            while grid.count():
                grid.takeAt(0)
            for index, button in enumerate(buttons):
                grid.addWidget(button, index // count, index % count)

    def label(self, box, text, parent, style=''):
        label = QLabel(str(text), parent)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        if style:
            label.setStyleSheet(style)
        box.addWidget(label)
        return label

    def refresh(self):
        busy = self.manager.is_busy()
        for button in self.import_buttons:
            button.setEnabled(not busy and not self.manager._stopping)
        self.runtime_button.setEnabled(not busy and not self.manager.active and not self.manager._stopping)
        self.runtime_button.setText('重新准备共享环境' if runtime_ready(self.manager.root) else '准备共享运行环境')
        self.runtime_label.setText('运行环境：Node.js / npm / Cordis 已就绪。' if runtime_ready(self.manager.root) else
                                   '运行环境：尚未准备，首次启用插件时自动安装。')
        self.cancel_button.setEnabled(busy)
        self.progress_bar.setRange(0, 0 if busy else 1)
        self.progress_bar.setValue(0)
        signature = json.dumps({'reports': self.manager.records,
                                'bubbles': {k: v.get('reply_bubbles', True) for k, v in self.manager.preferences.items()},
                                'surfaces': {k: v.get('widget_surface', 'window') for k, v in self.manager.preferences.items()}},
                               ensure_ascii=False, sort_keys=True)
        if signature == getattr(self, '_catalog_signature', None):
            self.update_states(busy)
            return
        self._catalog_signature = signature
        self.card_widgets = {}
        self.widget_reload_buttons = {}
        self.card_tools = []
        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        if not self.manager.records:
            empty = self.label(self.cards, '尚未导入插件。\n点击上方「导入插件文件夹」或「导入 ZIP / TGZ」选择原版 DSH 插件包。', self.card_container)
            empty.setStyleSheet('color:#9AA5BC; font-size:13px; padding:28px 10px; border:1px dashed #D4DBE8;'
                                ' border-radius:10px; background:#FAFBFE;')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for key, report in self.manager.records.items():
            frame = QFrame(self.card_container)
            frame.setObjectName('dshCard')
            frame.setMinimumWidth(0)
            frame.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(18, 14, 18, 14)
            layout.setSpacing(6)
            runtime = self.manager.active.get(key)
            state = runtime['state'] if runtime else '已停用'
            if self.manager.worker and self.manager.worker.action in ('prepare', 'repair') and self.manager.worker.source == key:
                state = '正在准备依赖'
            header_row = QHBoxLayout()
            header_row.setSpacing(8)
            name_label = QLabel(str(report['name']), frame)
            name_label.setStyleSheet('font-size:15px; font-weight:700; color:#2C3E63;')
            version_label = QLabel('v' + str(report['version']), frame)
            version_label.setStyleSheet('color:#9AA5BC; font-size:12px;')
            header_row.addWidget(name_label)
            header_row.addWidget(version_label)
            header_row.addStretch(1)
            pill = QLabel(state, frame)
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setStyleSheet('padding:3px 10px; border-radius:8px; font-size:11px; font-weight:600;')
            header_row.addWidget(pill)
            layout.addLayout(header_row)
            desc = self.label(layout, report['status'], frame)
            desc.setStyleSheet('color:#526BC3; font-size:12px;')
            entry = self.label(layout, '入口：' + report.get('entry', '未识别'), frame)
            entry.setStyleSheet('color:#8A93A6; font-size:12px;')
            for text in report.get('details', []):
                det = self.label(layout, text, frame)
                det.setStyleSheet('color:#8A93A6; font-size:12px;')
            self._apply_card_state(frame, pill, state)
            if report.get('web_compat') == 'whale-widget':
                surface_row = QHBoxLayout()
                surface_row.addWidget(QLabel('挂件显示位置', frame))
                surface_choice = QComboBox(frame)
                for label, value in (('鲸伴主窗口', 'window'), ('桌面悬浮', 'desktop'), ('暂时隐藏', 'hidden')):
                    surface_choice.addItem(label, value)
                mode = self.manager.preferences.get(key, {}).get('widget_surface', 'window')
                surface_choice.setCurrentIndex(max(0, surface_choice.findData(mode)))
                surface_choice.currentIndexChanged.connect(
                    lambda index, k=key, combo=surface_choice: self.manager.set_widget_surface(k, combo.itemData(index)))
                surface_choice.setMinimumWidth(0)
                surface_choice.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
                surface_row.addWidget(surface_choice, 1)
                layout.addLayout(surface_row)
                self.label(layout, '角色可直接拖动；桌面模式在鲸伴最小化或驻留托盘时继续显示，空白处鼠标穿透。', frame)
            if report.get('command') == 'dsh-pet-standalone':
                self.label(layout, '鲸伴回复联动：' + ('已开启' if self.manager.preferences.get(key, {}).get('reply_bubbles', True)
                           else '已关闭') + '；可在启动设置中调整。', frame)
            error = self.label(layout, '', frame, 'color:#AE4E4E;')
            error.setMinimumHeight(22)
            error.setStyleSheet('color:#AE4E4E; font-size:12px;')
            row = QGridLayout()
            row.setSpacing(8)
            buttons = []
            toggle = QPushButton('停用' if runtime else '启用', frame)
            toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle.setEnabled(report['adapter'] != 'unsupported' and (bool(runtime) or not busy)
                              and (not runtime or runtime['state'] != '正在停止'))
            toggle.clicked.connect(lambda checked=False, k=key: self.toggle(k, k not in self.manager.active))
            toggle.setEnabled(toggle.isEnabled() and not self.manager._stopping)
            buttons.append(toggle)
            settings = QPushButton('启动设置', frame)
            settings.setCursor(Qt.CursorShape.PointingHandCursor)
            settings.setEnabled(report['adapter'] in ('cordis', 'standalone') and not self.manager._stopping)
            settings.clicked.connect(lambda checked=False, k=key: self.settings(k))
            buttons.append(settings)
            interface = QPushButton('显示挂件' if report.get('web_compat') == 'whale-widget' else '打开插件界面', frame)
            interface.setCursor(Qt.CursorShape.PointingHandCursor)
            interface.setEnabled(bool(runtime) and runtime['instance'].is_ready and bool(report.get('interface_file')))
            interface.clicked.connect(lambda checked=False, k=key: self.open_interface(k))
            buttons.append(interface)
            if report.get('web_compat') == 'whale-widget':
                reload_widget = QPushButton('重新加载挂件', frame)
                reload_widget.setCursor(Qt.CursorShape.PointingHandCursor)
                reload_widget.setEnabled(bool(runtime) and runtime['instance'].is_ready)
                reload_widget.clicked.connect(lambda checked=False, k=key: self.reload_widget(k))
                self.widget_reload_buttons[key] = reload_widget
                buttons.append(reload_widget)
            restore = QPushButton('恢复桌面显示', frame)
            restore.setCursor(Qt.CursorShape.PointingHandCursor)
            restore.clicked.connect(lambda checked=False, k=key: self.manager.restore_pet(k))
            if report.get('web_compat') == 'pet':
                buttons.append(restore)
            else:
                restore.hide()
            repair = QPushButton('准备 / 修复依赖', frame)
            repair.setCursor(Qt.CursorShape.PointingHandCursor)
            repair.setEnabled(not runtime and not busy and report['adapter'] != 'unsupported' and not self.manager._stopping)
            repair.clicked.connect(lambda checked=False, k=key: self.begin('repair', k))
            buttons.append(repair)
            folder = QPushButton('原插件文件', frame)
            folder.setCursor(Qt.CursorShape.PointingHandCursor)
            folder.clicked.connect(lambda checked=False, k=key: QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.manager.directory / k / 'package'))))
            buttons.append(folder)
            remove = QPushButton('移除', frame)
            remove.setCursor(Qt.CursorShape.PointingHandCursor)
            remove.setEnabled(not runtime and not busy)
            remove.clicked.connect(lambda checked=False, k=key: self.remove(k))
            buttons.append(remove)
            secondary = ('QPushButton {background:#F5F7FB; color:#5A6A8C; border:1px solid #E2E7F2; border-radius:7px; padding:6px 12px; font-size:12px;}'
                         'QPushButton:hover {background:#EBF0F9; color:#34466C;}'
                         'QPushButton:disabled {color:#B0B8C8; background:#F7F8FB; border-color:#ECEFF5;}')
            for button in buttons:
                button.setMinimumWidth(0)
                button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
                if button is not toggle:
                    button.setStyleSheet(secondary)
            self.card_tools.append((row, buttons))
            self.card_widgets[key] = (frame, pill, error, toggle, settings, interface, repair, remove, restore)
            layout.addLayout(row)
            self.cards.addWidget(frame)
        self.reflow()
        self.update_states(busy)

    @staticmethod
    def _apply_card_state(frame, pill, state):
        """Color the card border and status pill to match runtime state."""
        if state == '运行中':
            frame.setStyleSheet("QFrame#dshCard {border:1px solid #BFE3CF; border-left:4px solid #3CA876;"
                                " border-radius:10px; background:#FBFFFD;} QLabel {border:0;}")
            pill.setStyleSheet('background:#E3F4EC; color:#2E7D5B; padding:3px 10px; border-radius:8px; font-size:11px; font-weight:600;')
        elif state in ('正在启动', '正在停止', '正在准备依赖'):
            frame.setStyleSheet("QFrame#dshCard {border:1px solid #F2E3B8; border-left:4px solid #E0A93B;"
                                " border-radius:10px; background:#FFFEF8;} QLabel {border:0;}")
            pill.setStyleSheet('background:#FBF1D6; color:#9A6E1A; padding:3px 10px; border-radius:8px; font-size:11px; font-weight:600;')
        else:
            frame.setStyleSheet("QFrame#dshCard {border:1px solid #E2E7F2; border-left:4px solid #C6CEDF;"
                                " border-radius:10px; background:#FFFFFF;} QLabel {border:0;}")
            pill.setStyleSheet('background:#EEF1F7; color:#7A869E; padding:3px 10px; border-radius:8px; font-size:11px; font-weight:600;')
        pill.setText(state)

    @staticmethod
    def _style_toggle(button, runtime, enabled):
        if runtime:
            button.setStyleSheet('QPushButton {background:#fff; color:#C0504D; border:1px solid #E0B4B2; border-radius:7px;'
                                 ' padding:6px 16px; font-weight:600;}'
                                 'QPushButton:hover {background:#FBEBEA;}'
                                 'QPushButton:disabled {color:#C0A8A8; background:#FBF7F7; border-color:#EADCDC;}')
        else:
            button.setStyleSheet('QPushButton {background:#3E5FA8; color:#fff; border:none; border-radius:7px;'
                                 ' padding:6px 16px; font-weight:600;}'
                                 'QPushButton:hover {background:#4E6FB8;}'
                                 'QPushButton:disabled {background:#B9C4DE;}')

    def update_states(self, busy):
        for key, widgets in getattr(self, 'card_widgets', {}).items():
            report = self.manager.records.get(key)
            if not report:
                continue
            frame, pill, error, toggle, settings, interface, repair, remove, restore = widgets
            runtime = self.manager.active.get(key)
            state = runtime['state'] if runtime else '已停用'
            worker = self.manager.worker
            if worker and worker.action in ('prepare', 'repair') and worker.source == key:
                state = '正在准备依赖'
            self._apply_card_state(frame, pill, state)
            error.setText('错误：'+self.manager.errors[key] if key in self.manager.errors else '')
            toggle.setText('停用' if runtime else '启用')
            toggle.setEnabled(report['adapter'] != 'unsupported' and (bool(runtime) or not busy)
                              and (not runtime or state != '正在停止') and not self.manager._stopping)
            self._style_toggle(toggle, runtime, toggle.isEnabled())
            settings.setEnabled(report['adapter'] in ('cordis', 'standalone') and not self.manager._stopping)
            interface.setEnabled(bool(runtime) and runtime['instance'].is_ready and bool(report.get('interface_file')))
            if key in getattr(self, 'widget_reload_buttons', {}):
                self.widget_reload_buttons[key].setEnabled(bool(runtime) and runtime['instance'].is_ready and not self.manager._stopping)
            restore.setEnabled(bool(runtime) and runtime['instance'].is_ready and not self.manager._stopping)
            repair.setEnabled(not runtime and not busy and report['adapter'] != 'unsupported' and not self.manager._stopping)
            remove.setEnabled(not runtime and not busy and not self.manager._stopping)

    def begin(self, action, source=None):
        try:
            self.manager.begin(action, source)
        except Exception as error:
            FishDialog.information(self, 'DSH 插件', str(error), 'warning')

    def import_folder(self):
        source = QFileDialog.getExistingDirectory(self, '选择 DSH 插件文件夹（含 package.json）')
        if source:
            self.begin('import', source)

    def import_archive(self):
        source, _ = QFileDialog.getOpenFileName(self, '选择 DSH 插件发布包', '', '插件包 (*.zip *.tgz *.tar.gz)')
        if source:
            self.begin('import', source)

    def toggle(self, key, enabled):
        try:
            if enabled:
                if not FishDialog.question(self, '启用原版 DSH 插件',
                    '将运行此插件的原始 JavaScript 入口，具有当前用户的系统权限。请仅启用可信来源。\n'
                    '首次启用会准备所需运行环境和依赖；插件自身的桌面运行库可能另行下载。', confirm_text='启用插件'):
                    return
            self.manager.set_enabled(key, enabled)
        except Exception as error:
            self.manager.runtime_error(key, error)

    def settings(self, key):
        try:
            standalone = self.manager.records[key]['adapter'] == 'standalone'
            dialog = QDialog(self)
            dialog.setWindowTitle('DSH 插件启动设置')
            dialog.resize(600, 480)
            box = QVBoxLayout(dialog)
            description = ('独立入口启动选项：arguments 为参数数组，environment 为环境变量对象。保存后下次启用生效。'
                           '原版插件的功能与模型设置请使用“打开插件界面”或插件自己的菜单。' if standalone else
                           '插件配置（JSON 对象），保存后下次启用生效。这里不自动传入鲸伴 API 密钥。')
            self.label(box, description, dialog)
            config = self.manager.preferences.get(key, {})
            editor = QPlainTextEdit(dialog)
            editor.setPlainText(json.dumps(config.get('config') or ({'arguments': [], 'environment': {}} if standalone else {}), ensure_ascii=False, indent=2))
            box.addWidget(editor)
            events = QCheckBox('向本插件开放本地聊天消息、思考和语音状态事件', dialog)
            events.setChecked(bool(config.get('chat_events', False)) and not standalone)
            events.setVisible(not standalone)
            if not standalone:
                box.addWidget(events)
            reply_bubbles = None
            if self.manager.records[key].get('command') == 'dsh-pet-standalone':
                reply_bubbles = QCheckBox('同步鲸伴 AI 回复到桌宠气泡（无需额外调用模型）', dialog)
                reply_bubbles.setChecked(bool(config.get('reply_bubbles', True)))
                box.addWidget(reply_bubbles)
                self.label(box, '同步本地聊天和鲸鱼心跳的新回复；长回复分段显示，新一轮聊天会停止旧回复翻页。'
                           '原插件须已启用桌面显示。此开关保存后立即生效。', dialog)
            error_label = QLabel(dialog)
            error_label.setWordWrap(True)
            error_label.setStyleSheet('color:#AE4E4E;')
            box.addWidget(error_label)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, dialog)
            def save():
                try:
                    if len(editor.toPlainText().encode('utf-8')) > 128 * 1024:
                        raise ValueError('配置最多 128 KB。')
                    value = json.loads(editor.toPlainText())
                    if not isinstance(value, dict):
                        raise ValueError('配置必须是 JSON 对象。')
                    self.manager.preferences.setdefault(key, {}).update(config=value, chat_events=events.isChecked())
                    if reply_bubbles is not None:
                        self.manager.preferences[key]['reply_bubbles'] = reply_bubbles.isChecked()
                    self.manager._save()
                    if reply_bubbles is not None:
                        runtime = self.manager.active.get(key)
                        if runtime:
                            runtime['instance'].set_reply_bubbles(reply_bubbles.isChecked())
                        self.manager.changed.emit()
                    dialog.accept()
                except (ValueError, OSError) as error:
                    error_label.setText(str(error))
            buttons.accepted.connect(save)
            buttons.rejected.connect(dialog.reject)
            box.addWidget(buttons)
            dialog.exec()
            dialog.deleteLater()
        except Exception as error:
            FishDialog.information(self, '插件设置', str(error), 'warning')

    def remove(self, key):
        if FishDialog.question(self, '移除 DSH 插件', '将插件移至本机 removed 目录，保留独立设置；之后可以重新导入。', confirm_text='移除插件'):
            try:
                self.manager.remove(key)
            except Exception as error:
                FishDialog.information(self, '移除失败', str(error), 'warning')

    def open_storage(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.manager.storage)))

    def open_interface(self, key):
        try:
            self.manager.open_interface(key)
        except Exception as error:
            FishDialog.information(self, '插件界面', str(error), 'warning')

    def reload_widget(self, key):
        try:
            self.manager.reload_widget(key)
        except Exception as error:
            FishDialog.information(self, '挂件加载', str(error), 'warning')
