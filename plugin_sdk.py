"""Public API v1 for local Jingban plugins. Plugins are trusted Python code."""
from __future__ import annotations

import json
from pathlib import Path
import uuid

from PySide6.QtCore import QObject, QThread, QTimer
from PySide6.QtWidgets import QWidget

API_VERSION = 1

PLUGIN_GUIDE = '''鲸伴插件开发 · API v1

目录结构：plugins/my_plugin/plugin.json、main.py，可附带 assets 等文件。
导入文件夹或复制到 plugins 后点“刷新列表”。首次导入不会自动执行。
插件是本地 Python 代码，与鲸伴具有相同系统权限，只启用可信代码。

plugin.json：
{"id":"my_plugin","name":"我的插件","version":"1.0.0","api_version":1,
 "entry":"main.py","description":"插件说明","author":"作者","permissions":[]}

main.py：
class Plugin:
    def __init__(self, context):
        self.context = context
    def start(self):
        self.context.notify("插件已启动")
    def stop(self):
        pass
def create_plugin(context):
    return Plugin(context)

生命周期：create_plugin(context) → start() → stop()。
可选 show_settings()，在插件页点“打开 / 设置”调用。
停用或重载时必须停止自己的线程、网络请求及计时器。不要阻塞界面线程。
相对导入请用 from .helpers import ...，不修改软件全局 sys.path。

context 接口：
  plugin_dir / data_dir / app_version：资源目录、独立数据目录、软件版本。
  resource_path("assets/icon.png")：取得本插件内资源路径。
  load_settings(defaults={}) / save_settings(dict)：插件独立 JSON 设置。
  track(qobject)：托管窗口、计时器等 QObject，停用时关闭、停止并释放。
  on_cleanup(callback)：注册停用时调用的清理函数。
  subscribe("message", callback)：已保存的消息，参数为 role/content/source/created_at。
      需在 manifest 的 permissions 中声明 chat_events。
  subscribe("voice_state", callback)：playing / paused / idle。
  subscribe("chat_state", callback)：state/source，state 为 thinking / idle / error。
  subscribe("data_cleared", callback)：聊天清空通知，无参数。
  open_chat()：显示聊天窗口。
  draft_message(text)：填入输入框，由用户自行发送，不自动调用 API。
  notify(text)：在软件状态栏显示提示。
  request_disable()：停用当前插件。

聊天事件来自已保存的消息，不含密钥或模型的深度思考。Python 插件不在沙箱中；
这些 API 限定数据接口，不代表对 Python 代码施加了系统权限隔离。
插件目录、plugin_data 和 plugins.json 不会被程序联网更新覆盖。
插件有自己的数据，如需响应“清空全部”，订阅 data_cleared 并自行清理对应状态。
内置“快捷短语”展示设置存储、窗口生命周期和填入聊天输入框的用法。
'''


class PluginContext:
    def __init__(self, manager, record):
        self._manager, self._record = manager, record
        self.plugin_dir = Path(record['directory'])
        self.data_dir = manager.root / 'plugin_data' / record['id']
        if self.data_dir.resolve() != self.data_dir:
            raise ValueError('插件数据目录不能指向其他位置。')
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.app_version = manager.app_version
        self._objects, self._cleanup = [], []
        self._disposed = False

    def resource_path(self, name):
        path = (self.plugin_dir / name).resolve()
        if not path.is_relative_to(self.plugin_dir.resolve()):
            raise ValueError('资源必须位于本插件目录内。')
        return path

    def load_settings(self, defaults=None):
        values = dict(defaults or {})
        try:
            saved = json.loads((self.data_dir / 'settings.json').read_text(encoding='utf-8'))
            if isinstance(saved, dict):
                values.update(saved)
        except (OSError, ValueError):
            pass
        return values

    def save_settings(self, values):
        target = self.data_dir / 'settings.json'
        temporary = self.data_dir / (uuid.uuid4().hex + '.tmp')
        try:
            temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def track(self, obj):
        if not isinstance(obj, QObject):
            raise TypeError('track 只接受 QObject。')
        if isinstance(obj, QThread):
            raise TypeError('线程请在插件 stop() 中自行取消并等待结束；track 用于窗口、计时器等普通 QObject。')
        self._objects.append(obj)
        return obj

    def on_cleanup(self, callback):
        self._cleanup.append(callback)

    def subscribe(self, name, callback):
        if name == 'message' and 'chat_events' not in self._record.get('permissions', []):
            raise PermissionError('请在 plugin.json 的 permissions 中声明 chat_events。')
        signal = self._manager.events.get(name)
        if signal is None:
            raise ValueError('未知插件事件：' + name)
        def guarded(*args):
            if self._disposed:
                return
            try:
                callback(*args)
            except (Exception, SystemExit) as error:
                self._manager.runtime_error(self._record['id'], error)
        signal.connect(guarded)
        self.on_cleanup(lambda: signal.disconnect(guarded))

    def open_chat(self):
        window = self._manager.window
        window.showNormal()
        window.show_page(0)
        window.raise_()
        window.activateWindow()

    def draft_message(self, text):
        self.open_chat()
        self._manager.window.messageInput.setPlainText(str(text))

    def notify(self, text):
        self._manager.window.statusBar().showMessage(str(text)[:500], 7000)

    def request_disable(self):
        QTimer.singleShot(0, lambda: self._manager.set_enabled(self._record['id'], False))

    def dispose(self):
        self._disposed = True
        errors = []
        for callback in reversed(self._cleanup):
            try:
                callback()
            except (Exception, SystemExit) as error:
                errors.append(str(error))
        self._cleanup.clear()
        for obj in reversed(self._objects):
            try:
                if isinstance(obj, QTimer):
                    obj.stop()
                if isinstance(obj, QWidget):
                    obj.close()
                obj.deleteLater()
            except RuntimeError:
                pass
        self._objects.clear()
        return errors
