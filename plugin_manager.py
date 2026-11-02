"""Discover and manage trusted, locally developed Python plugins."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import types
import uuid

from PySide6.QtCore import QObject, Signal, QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QScrollArea, QFrame, QFileDialog, QDialog, QPlainTextEdit, QTabWidget, QGridLayout, QSizePolicy)

from app_info import application_info
from dialogs import FishDialog
from plugin_sdk import API_VERSION, PLUGIN_GUIDE, PluginContext


class PluginBus(QObject):
    message = Signal(object)
    voice_state = Signal(str)
    chat_state = Signal(object)
    data_cleared = Signal()


class PluginManager(QObject):
    changed = Signal()

    def __init__(self, window, root):
        super().__init__(window)
        self.window, self.root = window, Path(root).resolve()
        self.directory = self.root / 'plugins'
        if self.directory.resolve() != self.directory:
            raise ValueError('plugins 目录不能指向程序目录之外。')
        self.directory.mkdir(exist_ok=True)
        self.app_version = application_info()['version']
        self.bus = PluginBus(self)
        self.events = {name: getattr(self.bus, name) for name in ('message', 'voice_state', 'chat_state', 'data_cleared')}
        self.records, self.active, self.scan_errors = {}, {}, []
        self._stopping = False
        try:
            self.preferences = json.loads((self.root / 'plugins.json').read_text(encoding='utf-8'))
            if not isinstance(self.preferences, dict):
                raise ValueError('插件设置格式错误')
        except (OSError, ValueError):
            self.preferences = {}
        self.scan()
        self.dsh, self.dsh_error = None, ''
        try:
            from dsh_panel import DshManager
            self.dsh = DshManager(self)
        except Exception as error:
            self.dsh_error = str(error)

    @staticmethod
    def read_manifest(directory):
        directory = Path(directory).resolve()
        path = directory / 'plugin.json'
        if path.stat().st_size > 65536:
            raise ValueError('plugin.json 超过 64 KB。')
        info = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(info, dict) or not re.fullmatch(r'[a-z][a-z0-9_]{2,63}', str(info.get('id', ''))):
            raise ValueError('插件 ID 应为 3～64 位小写字母、数字或下划线，以字母开头。')
        if type(info.get('api_version')) is not int or info['api_version'] != API_VERSION:
            raise ValueError('插件 API 版本不兼容，当前支持 API v1。')
        entry = str(info.get('entry', 'main.py'))
        if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]*\.py', entry):
            raise ValueError('entry 必须是插件根目录中的 Python 文件名。')
        if not (directory / entry).is_file() or (directory / entry).resolve().parent != directory:
            raise ValueError('插件入口文件不存在或指向其他目录。')
        for key in ('name', 'version'):
            if not isinstance(info.get(key), str) or not info[key].strip() or len(info[key]) > 100:
                raise ValueError('插件名称和版本不能为空，最多 100 个字符。')
        permissions = info.get('permissions', [])
        if not isinstance(permissions, list) or any(value not in ('chat_events',) for value in permissions):
            raise ValueError('支持的插件权限为 chat_events。')
        return {**info, 'entry': entry, 'directory': str(directory), 'builtin': False}

    def scan(self):
        from quick_phrases_plugin import MANIFEST
        records = {MANIFEST['id']: {**MANIFEST, 'directory': str(self.root)}}
        errors = []
        for directory in sorted(self.directory.iterdir()):
            if directory.name.startswith('.') or not directory.is_dir():
                continue
            try:
                if directory.is_symlink() or directory.resolve().parent != self.directory:
                    raise ValueError('插件目录不能是链接。')
                info = self.read_manifest(directory)
                if info['id'] in records:
                    raise ValueError('插件 ID 重复：' + info['id'])
                records[info['id']] = info
            except (Exception, SystemExit) as error:
                errors.append(directory.name + '：' + str(error))
        # Keep loaded instances pinned to their current manifest until explicitly reloaded.
        for plugin_id, runtime in self.active.items():
            records[plugin_id] = runtime['record']
        for plugin_id, record in records.items():
            record['error'] = self.records.get(plugin_id, {}).get('error', '')
        self.records, self.scan_errors = records, errors
        self.changed.emit()

    def _save(self):
        target = self.root / 'plugins.json'
        temporary = target.with_name('plugins.' + uuid.uuid4().hex + '.tmp')
        try:
            temporary.write_text(json.dumps(self.preferences, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def start_enabled(self):
        for plugin_id in list(self.records):
            if self.preferences.get(plugin_id) is True:
                try:
                    self.set_enabled(plugin_id, True)
                except (Exception, SystemExit) as error:
                    self.runtime_error(plugin_id, error)
        if self.dsh is not None:
            self.dsh.start_enabled()

    def _unload_modules(self, namespace):
        for name in list(sys.modules):
            if name == namespace or name.startswith(namespace + '.'):
                sys.modules.pop(name, None)

    def set_enabled(self, plugin_id, enabled):
        if enabled and plugin_id not in self.active:
            record = self.records[plugin_id]
            context = PluginContext(self, record)
            namespace = 'jingban_plugin_' + plugin_id + '_' + uuid.uuid4().hex
            instance = None
            try:
                if record.get('builtin'):
                    from quick_phrases_plugin import create_plugin
                else:
                    package = types.ModuleType(namespace)
                    package.__path__ = [record['directory']]
                    sys.modules[namespace] = package
                    entry = Path(record['directory']) / record['entry']
                    spec = importlib.util.spec_from_file_location(namespace + '.entry', entry)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[spec.name] = module
                    exec(compile(entry.read_text(encoding='utf-8-sig'), str(entry), 'exec'), module.__dict__)
                    create_plugin = module.create_plugin
                instance = create_plugin(context)
                if not callable(getattr(instance, 'start', None)) or not callable(getattr(instance, 'stop', None)):
                    raise ValueError('create_plugin 必须返回包含 start() 和 stop() 的对象。')
                self.active[plugin_id] = {'instance': instance, 'context': context,
                                          'namespace': namespace, 'record': record}
                instance.start()
                record['error'] = ''
            except (Exception, SystemExit):
                self.active.pop(plugin_id, None)
                if instance is not None and callable(getattr(instance, 'stop', None)):
                    try:
                        instance.stop()
                    except (Exception, SystemExit):
                        pass
                context.dispose()
                self._unload_modules(namespace)
                raise
        elif not enabled:
            runtime = self.active.pop(plugin_id, None)
            if runtime is not None:
                try:
                    runtime['instance'].stop()
                finally:
                    runtime['context'].dispose()
                    self._unload_modules(runtime['namespace'])
        self.preferences[plugin_id] = bool(enabled)
        self._save()
        self.changed.emit()

    def runtime_error(self, plugin_id, error):
        if self._stopping:
            return
        text = type(error).__name__ + ': ' + str(error)
        if plugin_id in self.records:
            self.records[plugin_id]['error'] = text
        self.preferences[plugin_id] = False
        try:
            self._save()
        except OSError:
            pass
        if plugin_id in self.active:
            QTimer.singleShot(0, lambda: self._stop_failed(plugin_id))
        self.changed.emit()

    def _stop_failed(self, plugin_id):
        try:
            self.set_enabled(plugin_id, False)
        except (Exception, SystemExit) as error:
            self.records.get(plugin_id, {})['error'] = str(error)
            self.changed.emit()

    def reload_plugin(self, plugin_id):
        self.set_enabled(plugin_id, False)
        self.scan()
        self.set_enabled(plugin_id, True)

    def shutdown(self):
        if self._stopping:
            return
        self._stopping = True
        if self.dsh is not None:
            self.dsh.shutdown()
        # Preserve enable preferences across application exits.
        for plugin_id, runtime in list(self.active.items()):
            try:
                runtime['instance'].stop()
            except (Exception, SystemExit):
                pass
            finally:
                runtime['context'].dispose()
                self._unload_modules(runtime['namespace'])
        self.active.clear()

    def import_directory(self, source):
        source = Path(source).resolve()
        info = self.read_manifest(source)
        target = self.directory / info['id']
        if target.exists() or info['id'] in self.records:
            raise ValueError('同名插件已存在，请直接编辑原插件后重载，或使用新的插件 ID。')
        paths = list(source.rglob('*'))
        if len(paths) > 3000 or sum(path.stat().st_size for path in paths if path.is_file()) > 100 * 1024**2:
            raise ValueError('插件最多 3000 个文件、100 MB。')
        if any(path.is_symlink() or not path.resolve().is_relative_to(source) for path in paths):
            raise ValueError('插件不能包含链接到其他目录的文件。')
        temporary = self.directory / ('.import-' + uuid.uuid4().hex)
        try:
            shutil.copytree(source, temporary, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
            temporary.rename(target)
        finally:
            if temporary.exists() and temporary.resolve().parent == self.directory and not temporary.is_symlink():
                shutil.rmtree(temporary)
        self.preferences[info['id']] = False
        self._save()
        self.scan()


class PluginPage(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget(self)
        tabs.setMinimumWidth(0)
        tabs.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        outer.addWidget(tabs)
        native_page = QWidget(tabs)
        native_page.setMinimumWidth(0)
        native_page.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(native_page)
        tabs.addTab(native_page, '鲸伴原生插件')
        intro = QLabel('加载自己开发的 Python 插件，扩展桌宠等功能。插件可启用、停用和重载，启用状态会在重启后恢复。', self)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        tip = QLabel('本地插件与软件具有相同系统权限，请仅启用可信来源。首次导入只读取说明，不执行代码。', self)
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#8C6D46; padding:6px 0;')
        layout.addWidget(tip)
        row = QGridLayout()
        for index, (text, callback) in enumerate([('导入插件文件夹', self.import_plugin), ('打开插件目录', self.open_directory),
                               ('刷新列表', manager.scan), ('开发说明 / 模板', self.development)]):
            button = QPushButton(text, self)
            button.clicked.connect(callback)
            row.addWidget(button, index // 2, index % 2)
        layout.addLayout(row)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget(scroll)
        self.cards = QVBoxLayout(container)
        self.cards.setContentsMargins(0, 8, 0, 8)
        self.cards.setSpacing(12)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        manager.changed.connect(self.refresh)
        self.refresh()
        if manager.dsh is not None:
            from dsh_panel import DshPage
            self.dsh_page = DshPage(manager.dsh, tabs)
            tabs.addTab(self.dsh_page, 'DSH 插件兼容')
        else:
            failure = QLabel('DSH 兼容模块未能初始化：' + manager.dsh_error, tabs)
            failure.setTextFormat(Qt.TextFormat.PlainText)
            failure.setWordWrap(True)
            tabs.addTab(failure, 'DSH 插件兼容')

    def refresh(self):
        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for plugin_id, record in self.manager.records.items():
            frame = QFrame(self)
            frame.setStyleSheet('QFrame {border:1px solid #DFE5F0; border-radius:10px; background:#fff;} QLabel {border:0;}')
            box = QVBoxLayout(frame)
            box.setContentsMargins(16, 12, 16, 12)
            enabled = plugin_id in self.manager.active
            for text in (f"{record['name']}  ·  v{record['version']}  ·  {'已启用' if enabled else '已停用'}",
                         str(record.get('description', '')), '作者：' + str(record.get('author', '未填写')) + (' · 内置示例' if record.get('builtin') else ' · 本地插件')):
                label = QLabel(text, frame)
                label.setTextFormat(Qt.TextFormat.PlainText)
                label.setWordWrap(True)
                box.addWidget(label)
            if record.get('error'):
                error = QLabel('错误：' + record['error'], frame)
                error.setTextFormat(Qt.TextFormat.PlainText)
                error.setWordWrap(True)
                error.setStyleSheet('color:#AE4E4E;')
                box.addWidget(error)
            row = QHBoxLayout()
            toggle = QPushButton('停用' if enabled else '启用', frame)
            toggle.clicked.connect(lambda checked=False, key=plugin_id, value=not enabled: self.toggle(key, value))
            row.addWidget(toggle)
            reload_button = QPushButton('重载', frame)
            reload_button.setEnabled(enabled)
            reload_button.clicked.connect(lambda checked=False, key=plugin_id: self.call(key, 'reload'))
            row.addWidget(reload_button)
            settings = QPushButton('打开 / 设置', frame)
            settings.setEnabled(enabled and callable(getattr(self.manager.active[plugin_id]['instance'], 'show_settings', None)))
            settings.clicked.connect(lambda checked=False, key=plugin_id: self.call(key, 'settings'))
            row.addWidget(settings)
            row.addStretch()
            box.addLayout(row)
            self.cards.addWidget(frame)
        for error in self.manager.scan_errors:
            label = QLabel(error, self)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            self.cards.addWidget(label)
        self.cards.addStretch()

    def toggle(self, plugin_id, enabled):
        if enabled:
            record = self.manager.records[plugin_id]
            access = '\n将接收已保存的聊天消息。' if 'chat_events' in record.get('permissions', []) else ''
            if not FishDialog.question(self, '启用插件', f"启用「{record['name']}」并执行其 Python 代码？{access}\n插件与软件具有相同系统权限。", confirm_text='启用插件'):
                return
        try:
            self.manager.set_enabled(plugin_id, enabled)
        except (Exception, SystemExit) as error:
            self.manager.runtime_error(plugin_id, error)

    def call(self, plugin_id, action):
        try:
            if action == 'reload':
                self.manager.reload_plugin(plugin_id)
            else:
                self.manager.active[plugin_id]['instance'].show_settings()
        except (Exception, SystemExit) as error:
            self.manager.runtime_error(plugin_id, error)

    def import_plugin(self):
        source = QFileDialog.getExistingDirectory(self, '选择含 plugin.json 的插件文件夹')
        if source:
            try:
                self.manager.import_directory(source)
            except (Exception, SystemExit) as error:
                FishDialog.information(self, '插件导入失败', str(error), 'warning')

    def open_directory(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.manager.directory)))

    def development(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('插件开发说明 / 模板')
        dialog.resize(700, 620)
        box = QVBoxLayout(dialog)
        text = QPlainTextEdit(dialog)
        text.setReadOnly(True)
        text.setPlainText(PLUGIN_GUIDE)
        box.addWidget(text)
        button = QPushButton('在所选目录生成 my_plugin 开发模板', dialog)
        button.clicked.connect(self.create_template)
        box.addWidget(button)
        dialog.exec()

    def create_template(self):
        directory = QFileDialog.getExistingDirectory(self, '选择模板的保存位置')
        if not directory:
            return
        target = Path(directory) / 'my_plugin'
        try:
            target.mkdir(exist_ok=False)
            (target / 'plugin.json').write_text(json.dumps({'id': 'my_plugin', 'name': '我的插件', 'version': '1.0.0',
                'api_version': 1, 'entry': 'main.py', 'description': '我的第一个鲸伴插件', 'author': '开发者', 'permissions': []}, ensure_ascii=False, indent=2), encoding='utf-8')
            (target / 'main.py').write_text('''class Plugin:
    def __init__(self, context):
        self.context = context
    def start(self):
        self.context.notify("我的插件已启动")
    def stop(self):
        pass

def create_plugin(context):
    return Plugin(context)
''', encoding='utf-8')
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        except OSError as error:
            FishDialog.information(self, '未能创建模板', str(error), 'warning')
