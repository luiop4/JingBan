"""Current-user Windows logon entry, quiet bootstrap and local instance activation."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = '鲸伴'


def startup_command(root):
    from update_core import bundled_helper_python
    root = Path(root).resolve()
    python = bundled_helper_python(root)
    pythonw = python.with_name('pythonw.exe') if python else None
    entry = root / 'app_startup.py'
    if not pythonw or not pythonw.is_file() or not entry.is_file():
        raise ValueError('缺少项目内的无控制台Python或静默入口，请修复软件目录后重试。')
    command = subprocess.list2cmdline([str(pythonw), '-E', '-s', '-X', 'utf8', str(entry), '--autostart'])
    if len(command) > 260:
        raise ValueError('软件目录过长，超出Windows启动项长度限制，请移到较短目录。')
    return command


def registration(root):
    if os.name != 'nt':
        return {'enabled': False, 'other': False, 'error': '开机启动仅支持Windows。'}
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, kind = winreg.QueryValueEx(key, RUN_NAME)
    except FileNotFoundError:
        value, kind = '', winreg.REG_SZ
    expected = startup_command(root)
    enabled = kind == winreg.REG_SZ and isinstance(value, str) and value.casefold() == expected.casefold()
    return {'enabled': enabled, 'other': bool(value) and not enabled}


def configure(root, enabled):
    """Change only this app's Run value; no administrator rights or copied preference."""
    if os.name != 'nt':
        raise ValueError('开机启动仅支持Windows。')
    import winreg
    command = startup_command(root)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                current, _ = winreg.QueryValueEx(key, RUN_NAME)
            except FileNotFoundError:
                current = ''
            if isinstance(current, str) and current.casefold() == command.casefold():
                winreg.DeleteValue(key, RUN_NAME)
    return registration(root)


def install_settings(window, root):
    from PySide6.QtCore import QSignalBlocker
    from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QVBoxLayout
    card = QFrame(window.settingsPage)
    card.setObjectName('startupSettings')
    box = QVBoxLayout(card)
    box.setContentsMargins(0, 2, 0, 4)
    box.setSpacing(3)
    check = QCheckBox('开机自动启动鲸伴，直接驻留托盘', card)
    check.setToolTip('登录Windows后在后台运行，不显示启动页和聊天窗口。点击托盘图标打开，右键可退出。')
    status = QLabel(card)
    status.setWordWrap(True)
    status.setStyleSheet('color:#778196;font-size:12px;')
    for widget in (check, status):
        box.addWidget(widget)
    window.settingsContentLayout.insertWidget(1, card)

    def refresh(message=''):
        try:
            state = registration(root)
            blocker = QSignalBlocker(check)
            check.setChecked(state['enabled'])
            del blocker
            check.setEnabled(os.name == 'nt' and not state.get('error'))
            status.setText(message or state.get('error') or ('已开启 · 下次登录后静默启动。' if state['enabled'] else
                '另一份鲸伴已登记开机启动，勾选将改用当前目录。' if state['other'] else '未开启开机启动。'))
        except (OSError, ValueError) as error:
            status.setText('启动项读取失败：'+str(error)[:200])

    def changed(enabled):
        try:
            configure(root, enabled)
            refresh('已开启，立即生效，无需再点保存。' if enabled else '已关闭当前目录的开机启动。')
        except (OSError, ValueError) as error:
            refresh('启动项未能修改：'+str(error)[:200])
    refresh()
    check.toggled.connect(changed)
    window.startupCheckBox = check
    window.startupStatusLabel = status


def mark_ready():
    path = os.environ.get('AICHAT_STARTUP_READY_FILE', '')
    if path:
        try:
            Path(path).write_text('ready', encoding='utf-8')
        except OSError:
            pass


class SingleInstance:
    """A Windows session mutex prevents races; a user-only pipe raises the resident UI."""
    def __init__(self, root, app, quiet=False):
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
        import ctypes
        from ctypes import wintypes
        self.server, self.handle, self.window = None, None, None
        self.pending_show, self.primary, self.sockets = False, True, set()
        digest = hashlib.sha256(os.path.normcase(str(Path(root).resolve())).encode()).hexdigest()[:32]
        self.name = 'Jingban-'+digest
        if os.name == 'nt':
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.kernel.ProcessIdToSessionId.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
            self.kernel.ProcessIdToSessionId.restype = wintypes.BOOL
            session = wintypes.DWORD()
            if not self.kernel.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.name += '-'+str(session.value)
            self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
            self.kernel.CreateMutexW.restype = wintypes.HANDLE
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.kernel.CloseHandle.restype = wintypes.BOOL
            ctypes.set_last_error(0)
            self.handle = self.kernel.CreateMutexW(None, False, 'Local\\'+self.name)
            error = ctypes.get_last_error()
            if not self.handle:
                raise ctypes.WinError(error)
            self.primary = error != 183  # ERROR_ALREADY_EXISTS
        else:
            probe = QLocalSocket()
            probe.connectToServer(self.name)
            self.primary = not probe.waitForConnected(200)
            probe.abort()
        if not self.primary:
            self.delivered = False
            for _ in range(8):
                client = QLocalSocket()
                client.connectToServer(self.name)
                if client.waitForConnected(350):
                    client.write(b'quiet\n' if quiet else b'show\n')
                    self.delivered = client.bytesToWrite() == 0 or client.waitForBytesWritten(500)
                    client.disconnectFromServer()
                    break
                client.abort()
                time.sleep(0.15)
            self.close()
            return
        self.server = QLocalServer(app)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.setMaxPendingConnections(4)
        if os.name != 'nt':
            QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            self.close()
            raise OSError('无法创建鲸伴本机唤醒通道。')
        self.server.newConnection.connect(self.accept)

    def attach(self, window):
        self.window = window
        if self.pending_show:
            window.companion.open_chat()

    def accept(self):
        from PySide6.QtCore import QTimer
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.setReadBufferSize(64)
            self.sockets.add(socket)
            def read(peer=socket):
                if not peer.canReadLine():
                    return
                message = bytes(peer.readLine(64)).strip()
                if message == b'show':
                    if self.window and not getattr(self.window, '_closing', False):
                        self.window.companion.open_chat()
                    else:
                        self.pending_show = True
                peer.disconnectFromServer()
            def cleanup(peer=socket):
                self.sockets.discard(peer)
                peer.deleteLater()
            socket.readyRead.connect(read)
            socket.disconnected.connect(cleanup)
            QTimer.singleShot(3000, socket, socket.abort)
            read()

    def close(self):
        if self.server:
            self.server.close()
        for socket in list(self.sockets):
            socket.abort()
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def bootstrap():
    """No Qt, shell window, online update check or foreground error dialog at logon."""
    from portable_runtime import prepare_portable_runtime
    from startup_support import child_environment, diagnostic_path, install_startup_diagnostics, spawn_child, startup_log
    from update_core import WorkspaceLock, running_clients
    root = Path(__file__).resolve().parent
    install_startup_diagnostics(root, 'autostart')
    try:
        if '--autostart' not in sys.argv or not registration(root)['enabled']:
            return 0
        with WorkspaceLock(root):
            if running_clients(root):
                return 0
            if (root / '.updates/transaction.json').exists():
                raise RuntimeError('上次更新尚未完成，请手动打开启动器完成修复。')
            prepare_portable_runtime(root)
        python = root / '.app-venv/Scripts/python.exe'
        if not python.is_file() or not (root / 'main.py').is_file():
            raise RuntimeError('缺少聊天程序或项目虚拟环境。')
        log = diagnostic_path(root, 'autostart-chat.log')
        if log is None:
            raise OSError('无法创建启动诊断日志。')
        env = child_environment()
        env.pop('AICHAT_STARTUP_READY_FILE', None)
        with log.open('ab') as output:
            child = spawn_child([str(python), '-X', 'utf8', '-u', str(root / 'main.py'), '--start-in-tray', '--autostart'],
                cwd=root, env=env, stdout=output, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        startup_log(root, f'静默启动聊天进程 pid={child.pid}', 'autostart.log')
        return 0
    except Exception:
        import traceback
        startup_log(root, traceback.format_exc(), 'autostart.log')
        return 1


if __name__ == '__main__':
    raise SystemExit(bootstrap())
