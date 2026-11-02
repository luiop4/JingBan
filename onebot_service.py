"""Local NapCat lifecycle, console capture, and QR/login state. No QQ messages are sent here."""
from __future__ import annotations

import codecs
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import threading
import time
import urllib.request
from urllib.parse import urlsplit

from PySide6.QtCore import QThread, Signal

from onebot_process import OneBotProcess
from update_core import atomic_json, file_hash, local_path, read_json, verify_envelope


def find_qq(saved=''):
    if saved:
        candidate = Path(saved.strip().strip('"')).expanduser()
        if candidate.is_file() and candidate.name.lower() == 'qq.exe':
            return candidate.resolve()
        raise ValueError('指定的 QQ.exe 不存在，请重新选择。')
    if os.name == 'nt':
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for name in (r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\QQ',
                         r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\QQ'):
                try:
                    with winreg.OpenKey(hive, name) as key:
                        value = winreg.QueryValueEx(key, 'UninstallString')[0]
                    candidate = Path(value.strip('"')).parent / 'QQ.exe'
                    if candidate.is_file():
                        return candidate
                except OSError:
                    pass
    for prefix in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        for suffix in ('Tencent/QQNT/QQ.exe', 'Tencent/QQ/QQ.exe'):
            candidate = Path(os.environ.get(prefix, 'C:/Program Files')) / suffix
            if candidate.is_file():
                return candidate
    raise ValueError('未找到本机 QQ，请先安装 QQ，或在此页手动选择 QQ.exe。')


def local_endpoint(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'ws' or parsed.hostname not in ('127.0.0.1', 'localhost')
            or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('内置服务请使用 ws://127.0.0.1:端口；其他桥接可用下方“连接本地桥接”。')
    return parsed.port or 3001


def port_busy(port):
    with socket.socket() as connection:
        connection.settimeout(0.3)
        return connection.connect_ex(('127.0.0.1', port)) == 0


def check_runtime(root, cancelled=lambda: False):
    root = Path(root)
    for name in ('NapCatWinBootMain.exe', 'NapCatWinBootHook.dll', 'loadNapCat.js', 'napcat.mjs', 'qqnt.json'):
        if not (root / 'onebot/runtime' / name).is_file():
            raise ValueError('OneBot 组件缺少文件，请点击“退出并修复组件”，完成更新后再启动。')
    manifest = root / '.updates/installed.json'
    if manifest.is_file():
        payload = verify_envelope(read_json(manifest))
        for component in payload.get('components', []):
            if component['id'] == 'onebot':
                for entry in component['files']:
                    if cancelled():
                        return False
                    path = local_path(root, entry['path'])
                    if not path.is_file() or path.stat().st_size != entry['size'] or file_hash(path, cancelled) != entry['sha256']:
                        raise ValueError('OneBot 组件损坏或不完整，请点击“退出并修复组件”。')
    return True


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        raise ValueError('本机 OneBot 管理接口不允许重定向。')


class _ServiceLease:
    def __init__(self, root):
        self.path = Path(root) / 'data/onebot/service.lock'
        self.stream = None

    def acquire(self):
        import msvcrt
        if self.path.parent.is_symlink() or not self.path.parent.resolve().is_relative_to(self.path.parents[2].resolve()):
            raise ValueError('OneBot 数据目录无效。')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open('a+b')
        self.stream.seek(0)
        if not self.stream.read(1):
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        try:
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            self.close()
            raise ValueError('其他鲸伴窗口正在管理内置 OneBot，请在原窗口停止服务后再试。') from error

    def close(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None


_ENTRY = r'''const fs = require('fs');
const {pathToFileURL} = require('url');
const destination = process.env.JINGBAN_ONEBOT_CONSOLE;
for (const stream of [process.stdout, process.stderr]) {
    const original = stream.write.bind(stream);
    stream.write = function(chunk, encoding, callback) {
        try {
            if (fs.existsSync(destination) && fs.statSync(destination).size > 5 * 1024 * 1024) {
                fs.renameSync(destination, destination.replace('console-current.log', 'console-previous.log'));
            }
            fs.appendFileSync(destination, Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk), typeof encoding === 'string' ? encoding : 'utf8'));
        } catch (_) { return original(chunk, encoding, callback); }
        const done = typeof encoding === 'function' ? encoding : callback;
        if (typeof done === 'function') process.nextTick(done);
        return true;
    };
}
import(pathToFileURL(process.env.NAPCAT_MAIN_PATH).href).catch(error => {
    console.error(error && error.stack || error);
    process.exitCode = 1;
});
'''


class OneBotService(QThread):
    status_changed = Signal(str)
    log_received = Signal(str)
    qr_received = Signal(bytes)
    login_changed = Signal(object)
    ready = Signal()

    def __init__(self, root, config, parent=None):
        super().__init__(parent)
        self.root = Path(root).resolve()
        self.config = config
        self.stop_requested = threading.Event()
        self.refresh_requested = threading.Event()
        self.error = ''
        self.process_started = False
        self._credential = ''
        self._web_token = ''
        self._next_auth = 0.0
        self._last_login = None
        self._quick_account = ''
        self._login_poll_started = 0.0
        self._qr_fallback = False
        self._remembered = False
        self._console_offset = 0
        self._console_identity = None
        self._console_decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self._http = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirects())

    def stop(self):
        self.stop_requested.set()

    def refresh_qr(self):
        self.refresh_requested.set()

    def _log(self, value):
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(value)).replace('\r', '')
        for token in (self.config.get('access_token', ''), self._web_token, self._credential):
            if token:
                text = text.replace(token, '[令牌已隐藏]')
        text = re.sub(r'(?i)([?&](?:token|webui_token)=)[^\s&]+', r'\1[已隐藏]', text)
        if text:
            self.log_received.emit(text)

    def _post(self, path, value=None, credential=True):
        headers = {'Content-Type': 'application/json'}
        if credential:
            headers['Authorization'] = 'Bearer ' + self._credential
        request = urllib.request.Request(
            f'http://127.0.0.1:{self.config["onebot"]["webui_port"]}/api/' + path,
            data=json.dumps(value or {}).encode(), headers=headers, method='POST')
        with self._http.open(request, timeout=2) as response:
            result = json.loads(response.read(1024 * 1024))
        if result.get('code') != 0:
            if result.get('message') in ('Unauthorized', 'Authorization Failed'):
                self._credential = ''
            raise ValueError(str(result.get('message', '本地管理接口未就绪')))
        return result.get('data') or {}

    def _poll_login(self):
        if not self._credential:
            now = time.monotonic()
            if now < self._next_auth:
                return
            self._next_auth = now + 8
            value = self._post('auth/login', {'hash': hashlib.sha256((self._web_token + '.napcat').encode()).hexdigest()}, False)
            if value.get('require2FA'):
                raise ValueError('WebUI 启用了二次验证，请使用外部桥接连接。')
            self._credential = value['Credential']
        if self.refresh_requested.is_set():
            self.refresh_requested.clear()
            self._qr_fallback = True
            self.status_changed.emit('正在刷新二维码…')
            self._post('QQLogin/RefreshQRcode')
        value = self._post('QQLogin/CheckLoginStatus')
        if not self._login_poll_started:
            self._login_poll_started = time.monotonic()
        if value.get('isLogin') and not self._remembered:
            try:
                info = self._post('QQLogin/GetQQLoginInfo')
                uin = str(info.get('uin', ''))
                if re.fullmatch(r'\d{5,12}', uin) and self.config['onebot'].get('remember_login', True):
                    atomic_json(self.root / 'data/onebot/last-login.json', {'uin': uin})
                    self._post('QQLogin/SetQuickLoginQQ', {'uin': uin})
                    self._log('已记住当前 QQ，下次启动优先复用本机登录态。\n')
            except Exception:
                self._log('QQ 已登录，但记住账号未完成；不会影响本次连接。\n')
            self._remembered = True
        if (not value.get('isLogin') and self._quick_account and not self._qr_fallback
                and not value.get('qrLoginAccepted') and value.get('loginPhase') not in ('qrcode_scanned', 'initializing', 'reconnecting')
                and time.monotonic() - self._login_poll_started >= 35):
            self._qr_fallback = True
            self._log('快速登录尚未成功，已切换二维码登录；登录态可能失效，需要手机重新确认。\n')
            self._post('QQLogin/RefreshQRcode')
        if (not value.get('isLogin') and self._quick_account and not self._qr_fallback
                and value.get('loginPhase') not in ('qrcode_scanned', 'initializing', 'reconnecting')):
            value = {**value, 'loginPhase': 'quick_login'}
        state = (bool(value.get('isLogin')), value.get('loginPhase'), value.get('loginError'))
        if state != self._last_login:
            self._last_login = state
            self.login_changed.emit(value)
            if state[0]:
                self.ready.emit()

    def _tail_console(self, path):
        try:
            stat = path.stat()
            identity = (stat.st_ino, stat.st_ctime_ns)
            if identity != self._console_identity or stat.st_size < self._console_offset:
                self._console_identity = identity
                self._console_offset = 0
                self._console_decoder.reset()
            with path.open('rb') as source:
                source.seek(self._console_offset)
                data = source.read(128 * 1024)
                self._console_offset = source.tell()
            self._log(self._console_decoder.decode(data))
        except OSError:
            pass

    def _read_pipe(self, process):
        decoder = codecs.getincrementaldecoder('utf-8')('replace')
        try:
            while data := process.output.read(8192):
                self._log(decoder.decode(data))
        except (OSError, RuntimeError):
            pass
        finally:
            process.output.close()

    def _prepare(self):
        runtime = self.root / 'onebot/runtime'
        state = self.root / 'data/onebot'
        if state.is_symlink() or not state.resolve().is_relative_to(self.root):
            raise ValueError('OneBot 数据目录不能指向项目之外。')
        state.mkdir(parents=True, exist_ok=True)
        (state / 'config').mkdir(exist_ok=True)
        (state / 'cache').mkdir(exist_ok=True)
        web_path = state / 'config/webui.json'
        web = read_json(web_path) if web_path.exists() else {}
        if self.config['onebot'].get('remember_login', True):
            remembered = state / 'last-login.json'
            try:
                saved = read_json(remembered).get('uin', '') if remembered.exists() else web.get('autoLoginAccount', '')
            except (OSError, ValueError, AttributeError):
                saved = ''
                self._log('上次登录账号记录无效，本次使用二维码登录。\n')
            if not saved:
                accounts = [p.stem.removeprefix('onebot11_') for p in (state / 'config').glob('onebot11_*.json')
                            if re.fullmatch(r'onebot11_\d{5,12}', p.stem)]
                saved = accounts[0] if len(accounts) == 1 else ''
            if re.fullmatch(r'\d{5,12}', str(saved)):
                self._quick_account = str(saved)
        web['autoLoginAccount'] = self._quick_account
        self._web_token = web.get('token') or secrets.token_urlsafe(24)
        if web.get('enable2FA'):
            raise ValueError('内置管理配置启用了二次验证，请先使用外部桥接连接。')
        web.update({'host': '127.0.0.1', 'port': self.config['onebot']['webui_port'], 'token': self._web_token, 'loginRate': 10})
        atomic_json(web_path, web)
        server = {'name': 'jingban-local', 'enable': True, 'host': '127.0.0.1',
                  'port': local_endpoint(self.config['ws_url']), 'messagePostFormat': 'array',
                  'reportSelfMessage': False, 'token': self.config['access_token'],
                  'enableForcePushEvent': True, 'debug': False, 'heartInterval': 30000}
        onebot_path = state / 'config/onebot11.json'
        onebot = read_json(onebot_path) if onebot_path.exists() else {}
        onebot['network'] = {'httpServers': [], 'httpSseServers': [], 'httpClients': [],
                             'websocketClients': [], 'websocketServers': [server], 'plugins': []}
        atomic_json(onebot_path, onebot)
        # Existing account-specific network files override the generic defaults.
        for path in (state / 'config').glob('onebot11_*.json'):
            atomic_json(path, onebot)
        entry = state / 'entry.cjs'
        entry.write_text(_ENTRY, encoding='utf-8')
        console = state / 'console-current.log'
        if console.exists():
            console.replace(state / 'console-previous.log')
        qr = state / 'cache/qrcode.png'
        qr.unlink(missing_ok=True)
        environment = dict(os.environ)
        for key in ('PYTHONHOME', 'PYTHONPATH', 'ELECTRON_RUN_AS_NODE', 'NAPCAT_QUICK_ACCOUNT',
                    'NAPCAT_QUICK_PASSWORD', 'NAPCAT_QUICK_PASSWORD_MD5'):
            environment.pop(key, None)
        if self._quick_account:
            environment['NAPCAT_QUICK_ACCOUNT'] = self._quick_account
        environment.update({'NAPCAT_PATCH_PACKAGE': str(runtime / 'qqnt.json'),
                            'NAPCAT_LOAD_PATH': str(entry),
                            'NAPCAT_INJECT_PATH': str(runtime / 'NapCatWinBootHook.dll'),
                            'NAPCAT_LAUNCHER_PATH': str(runtime / 'NapCatWinBootMain.exe'),
                            'NAPCAT_MAIN_PATH': str(runtime / 'napcat.mjs'),
                            'NAPCAT_WORKDIR': str(state), 'JINGBAN_ONEBOT_CONSOLE': str(console),
                            'NAPCAT_WEBUI_PREFERRED_PORT': str(self.config['onebot']['webui_port']),
                            'FORCE_COLOR': '0'})
        return runtime, state, environment, console, qr

    def run(self):
        process = None
        reader = None
        lease = _ServiceLease(self.root)
        try:
            if os.name != 'nt':
                raise ValueError('内置 OneBot 目前支持 Windows。')
            self.status_changed.emit('正在校验 OneBot 组件…')
            if not check_runtime(self.root, self.stop_requested.is_set):
                return
            qq = find_qq(self.config['onebot'].get('qq_path', ''))
            lease.acquire()
            ports = (local_endpoint(self.config['ws_url']), self.config['onebot']['webui_port'])
            if ports[0] == ports[1]:
                raise ValueError('WebSocket 和 WebUI 端口不能相同。')
            for port in ports:
                if port_busy(port):
                    raise ValueError(f'端口 {port} 已被占用。请先关闭原来的 NapCat，或使用下方连接按钮接入已有桥接。')
            runtime, state, environment, console, qr = self._prepare()
            if self.stop_requested.is_set():
                return
            self.status_changed.emit('正在启动 QQ 登录服务…')
            self._log('启动内置 NapCat，控制台输出显示在本页。\n')
            if self._quick_account:
                self.status_changed.emit('正在尝试上次账号快速登录…')
                self._log('优先使用本机 QQ 保存的登录态，不保存账号密码；失败时可刷新二维码。\n')
            process = OneBotProcess([str(runtime / 'NapCatWinBootMain.exe'), str(qq),
                                     str(runtime / 'NapCatWinBootHook.dll')], runtime, environment)
            self.process_started = True
            reader = threading.Thread(target=self._read_pipe, args=(process,), daemon=True)
            reader.start()
            qr_stamp = None
            startup = time.monotonic()
            warned = False
            while not self.stop_requested.is_set():
                self._tail_console(console)
                if not process.active():
                    raise RuntimeError('OneBot 进程已退出，请查看下方启动日志；也请检查本机 QQ 与运行库是否兼容。')
                try:
                    stamp = (qr.stat().st_mtime_ns, qr.stat().st_size)
                    waiting_quick = self._quick_account and not self._qr_fallback and time.monotonic() - startup < 45
                    if stamp != qr_stamp and not waiting_quick and not (self._last_login and self._last_login[0]):
                        data = qr.read_bytes()
                        if data.startswith(b'\x89PNG\r\n\x1a\n'):
                            qr_stamp = stamp
                            self.qr_received.emit(data)
                            self.status_changed.emit('请使用手机 QQ 扫码，并在手机上确认登录')
                except OSError:
                    pass
                try:
                    self._poll_login()
                except Exception as error:
                    if self.refresh_requested.is_set():
                        self.refresh_requested.clear()
                    if time.monotonic() - startup > 40 and not warned:
                        warned = True
                        self._log('登录状态暂未就绪：' + str(error) + '\n')
                        if not (self._last_login and self._last_login[0]):
                            self.status_changed.emit('登录服务尚未就绪，请查看日志')
                self.stop_requested.wait(1)
        except Exception as error:
            if not self.stop_requested.is_set():
                self.error = str(error)
                self.status_changed.emit('启动失败：' + self.error)
                self._log(self.error + '\n')
        finally:
            if process is not None:
                process.close()
                if reader is not None:
                    reader.join(timeout=2)
                self._tail_console(self.root / 'data/onebot/console-current.log')
            lease.close()
            if not self.error:
                self.status_changed.emit('服务已停止')
