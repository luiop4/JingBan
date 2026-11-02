"""Signed file-manifest updater. Standard library only; never imports application code.

The launcher downloads into staging, then a separate process commits after it exits.
Runtime leases stop replacement while any cooperating chat process is still running.
"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.parse
import urllib.request
import uuid
import zipfile

from update_trust import UPDATE_BASE_URL, PUBLIC_MODULUS, PUBLIC_EXPONENT
from startup_support import (child_environment, diagnostic_path, install_startup_diagnostics,
                             native_error, spawn_child, startup_log)

UPDATER_FORMAT = 1
MAX_FILE = 256 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024
ASSETS = {'assets/jingban-icon.ico', 'assets/jingban-icon.png', 'assets/mascot_v2.png',
          'assets/app_icon.svg', 'assets/memory-engine.svg', 'assets/white-whale.svg'}
DOCUMENTS = {'version.json', 'CHANGELOG.txt', 'README.md', 'STANDARD_MEMORY.md',
             'author_avatar.png', '鲸伴.exe', 'AIChatMemoryLauncher.spec'}


class UpdateError(RuntimeError):
    pass


class UpdateBusy(UpdateError):
    pass


class UpdateCancelled(UpdateError):
    pass


def canonical(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def permitted_path(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or value.startswith('/'):
        return False
    parts = value.split('/')
    if any(not part or part in {'.', '..'} or part.endswith((' ', '.'))
           or re.search(r'[\x00-\x1f<>"|?*]', part)
           or re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I) for part in parts):
        return False
    if value in ASSETS or value in DOCUMENTS:
        return True
    if len(parts) > 2 and parts[:2] == ['onebot', 'runtime']:
        return parts[2].lower() not in {'config', 'cache', 'logs', 'plugins', '.env', '__pycache__'}
    return len(parts) == 1 and not value.startswith('_') and (
        Path(value).suffix.lower() in {'.py', '.ui', '.bat'}
        or value.startswith('requirements') and value.endswith('.txt'))


def local_path(root, value):
    if not permitted_path(value):
        raise UpdateError('更新清单含有不允许替换的路径。')
    root = Path(root).resolve()
    target = root.joinpath(*PurePosixPath(value).parts)
    if not target.resolve().is_relative_to(root) or target.is_symlink():
        raise UpdateError('更新路径指向程序目录之外。')
    if target.exists() and not target.is_file():
        raise UpdateError('程序文件位置被文件夹占用：' + value)
    return target


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+(?:\.\d+){1,3}', value):
        raise UpdateError('更新版本格式无效。')
    return tuple(int(part) for part in value.split('.'))


def verify_envelope(envelope):
    try:
        payload = envelope['payload']
        signature = base64.b64decode(envelope['signature'], validate=True)
        modulus = int.from_bytes(base64.b64decode(PUBLIC_MODULUS), 'big')
        exponent = int.from_bytes(base64.b64decode(PUBLIC_EXPONENT), 'big')
        length = (modulus.bit_length() + 7) // 8
        if len(signature) != length or int.from_bytes(signature, 'big') >= modulus:
            raise ValueError('signature size')
        digest = bytes.fromhex('3031300d060960864801650304020105000420') + hashlib.sha256(canonical(payload)).digest()
        expected = b'\x00\x01' + b'\xff' * (length - len(digest) - 3) + b'\x00' + digest
        actual = pow(int.from_bytes(signature, 'big'), exponent, modulus).to_bytes(length, 'big')
        if not hmac.compare_digest(actual, expected):
            raise ValueError('signature mismatch')
        if payload.get('format') != UPDATER_FORMAT or payload.get('min_updater', 1) > UPDATER_FORMAT:
            raise UpdateError('此版本需要更新启动器，请获取新版启动器。')
        version_tuple(payload['version'])
        if type(payload['build']) is not int or payload['build'] < 1:
            raise ValueError('build')
        files = payload['files']
        if not isinstance(files, list) or not 1 <= len(files) <= 500:
            raise ValueError('file count')
        names = set()
        total = 0
        for entry in files:
            path = entry['path']
            if not permitted_path(path) or path.casefold() in names:
                raise ValueError('path')
            names.add(path.casefold())
            size = entry['size']
            if type(size) is not int or not 0 <= size <= MAX_FILE or not re.fullmatch(r'[0-9a-f]{64}', entry['sha256']):
                raise ValueError('file hash or size')
            remote_url(entry['url'])
            total += size
        if total > MAX_TOTAL or not {'main.py', 'launcher.py', 'version.json', 'update_core.py', 'update_trust.py'} <= names:
            raise ValueError('incomplete release')
        components = payload.get('components', [])
        if not isinstance(components, list) or len(components) > 1:
            raise ValueError('components')
        for component in components:
            if component['id'] != 'onebot' or not isinstance(component['version'], str):
                raise ValueError('component identity')
            archive = component['archive']
            if (type(archive['size']) is not int or not 0 < archive['size'] <= MAX_FILE
                    or not re.fullmatch(r'[0-9a-f]{64}', archive['sha256'])):
                raise ValueError('component archive')
            remote_url(archive['url'])
            if not isinstance(component['files'], list) or not 1 <= len(component['files']) <= 5000:
                raise ValueError('component files')
            for entry in component['files']:
                path = entry['path']
                if (not permitted_path(path) or not path.startswith('onebot/runtime/')
                        or path.casefold() in names or type(entry['size']) is not int
                        or not 0 <= entry['size'] <= MAX_FILE
                        or not re.fullmatch(r'[0-9a-f]{64}', entry['sha256'])):
                    raise ValueError('component file')
                names.add(path.casefold())
                total += entry['size']
            if total > MAX_TOTAL:
                raise ValueError('component size')
        return payload
    except UpdateError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as error:
        raise UpdateError('更新清单签名或内容无效，未替换程序文件。') from error


def remote_url(value):
    if not isinstance(value, str):
        raise UpdateError('下载地址无效。')
    url = urllib.parse.urljoin(UPDATE_BASE_URL, value)
    parsed, base = urllib.parse.urlsplit(url), urllib.parse.urlsplit(UPDATE_BASE_URL)
    decoded_path = urllib.parse.unquote(parsed.path)
    if (parsed.scheme != 'https' or parsed.netloc != base.netloc or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not parsed.path.startswith(base.path)
            or '..' in decoded_path.split('/') or '\\' in decoded_path):
        raise UpdateError('更新地址超出了发布目录。')
    return url


class _Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        remote_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(value, timeout=12):
    request = urllib.request.Request(remote_url(value), headers={'User-Agent': 'Jingban-Updater/1', 'Cache-Control': 'no-cache'})
    return urllib.request.build_opener(_Redirects()).open(request, timeout=timeout)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def file_hash(path, cancelled=lambda: False):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            if cancelled():
                raise UpdateCancelled('更新检查已取消。')
            digest.update(chunk)
    return digest.hexdigest()


def matches(path, entry, cancelled=lambda: False):
    try:
        return path.is_file() and path.stat().st_size == entry['size'] and file_hash(path, cancelled) == entry['sha256']
    except OSError:
        return False


def release_entries(payload):
    return payload['files'] + [entry for component in payload.get('components', []) for entry in component['files']]


def component_cache(root, entry, progress, cancelled):
    cache = Path(root) / '.updates' / 'objects' / entry['sha256']
    if matches(cache, entry, cancelled):
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_suffix('.part')
    try:
        with _open(entry['url']) as source, temporary.open('wb') as output:
            size = 0
            digest = hashlib.sha256()
            while chunk := source.read(256 * 1024):
                if cancelled():
                    raise UpdateCancelled('OneBot 下载已取消。')
                size += len(chunk)
                if size > entry['size']:
                    raise UpdateError('OneBot 压缩包大小与清单不符。')
                digest.update(chunk)
                output.write(chunk)
                progress(6 + int(6 * size / entry['size']), f'正在下载 OneBot 组件：{size // 1024}/{entry["size"] // 1024} KB')
        if size != entry['size'] or digest.hexdigest() != entry['sha256']:
            raise UpdateError('OneBot 压缩包校验失败，未替换文件。')
        os.replace(temporary, cache)
    finally:
        temporary.unlink(missing_ok=True)
    return cache


def stage_component(root, job, component, needed, progress, cancelled):
    archive = component_cache(root, component['archive'], progress, cancelled)
    expected = {entry['path']: entry for entry in component['files']}
    with zipfile.ZipFile(archive) as zipped:
        infos = zipped.infolist()
        if len(infos) != len(expected) or {info.filename for info in infos} != set(expected):
            raise UpdateError('OneBot 压缩包文件列表与签名清单不符。')
        for info in infos:
            entry = expected[info.filename]
            if info.file_size != entry['size'] or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise UpdateError('OneBot 压缩包含有无效文件。')
            if info.filename not in needed:
                continue
            if cancelled():
                raise UpdateCancelled('OneBot 文件准备已取消。')
            target = Path(job) / 'payload' / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(info) as source, target.open('wb') as output:
                shutil.copyfileobj(source, output, 256 * 1024)
            if not matches(target, entry, cancelled):
                raise UpdateError('OneBot 解压文件校验失败：' + info.filename)


class WorkspaceLock:
    def __init__(self, root):
        self.path = Path(root) / '.updates' / 'workspace.lock'
        self.stream = None

    def __enter__(self):
        root = self.path.parent.parent.resolve()
        if self.path.parent.is_symlink() or not self.path.parent.resolve().is_relative_to(root):
            raise UpdateError('更新缓存目录指向了程序目录之外。')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open('a+b')
        self.stream.seek(0)
        if not self.stream.read(1):
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.stream.close()
            self.stream = None
            raise UpdateBusy('另一个窗口正在检查或安装更新，请稍后再试。') from error
        return self

    def __exit__(self, *_):
        if self.stream:
            self.stream.close()
            self.stream = None


def process_token(pid):
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
            return str(pid)
        except OSError:
            return ''
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return 'unreadable' if ctypes.get_last_error() == 5 else ''
    try:
        code = wintypes.DWORD()
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
            return ''
        times = [wintypes.FILETIME() for _ in range(4)]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
            return 'unreadable'
        return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
    finally:
        kernel.CloseHandle(handle)


def running_clients(root):
    running = []
    for marker in (Path(root) / '.updates' / 'running').glob('*.json'):
        try:
            pid = int(marker.stem)
            token = process_token(pid)
            record = read_json(marker)
            if token and (token == 'unreadable' or token == record.get('token')):
                running.append(pid)
            else:
                marker.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError, AttributeError):
            # An unreadable live marker must not cause concurrent replacement.
            if marker.stem.isdigit() and process_token(int(marker.stem)):
                running.append(int(marker.stem))
    return running


class RuntimeLease:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / '.updates' / 'running' / f'{os.getpid()}.json'
        with WorkspaceLock(root):
            if (self.root / '.updates' / 'transaction.json').exists():
                raise UpdateBusy('更新尚未完成，请通过启动器完成修复后再打开。')
            atomic_json(self.path, {'pid': os.getpid(), 'token': process_token(os.getpid())})

    def close(self):
        self.path.unlink(missing_ok=True)


def job_directory(root, job_id):
    if not re.fullmatch(r'[0-9a-f]{32}', job_id):
        raise UpdateError('更新任务目录无效。')
    base = Path(root).resolve() / '.updates' / 'jobs'
    if not base.resolve().is_relative_to(Path(root).resolve()):
        raise UpdateError('更新任务目录指向了程序目录之外。')
    path = base / job_id
    if not path.resolve().is_relative_to(base.resolve()) or path.is_symlink():
        raise UpdateError('更新缓存路径无效。')
    return path


def rollback(root, journal):
    job = job_directory(root, journal['job_id'])
    errors = []
    for row in reversed(journal['changes']):
        try:
            target = local_path(root, row['path'])
            backup = job / 'backup' / row['path']
            if row['existed']:
                if not backup.is_file():
                    raise UpdateError('原文件备份缺失：' + row['path'])
                temporary = target.with_name(target.name + '.rollback.tmp')
                shutil.copy2(backup, temporary)
                os.replace(temporary, target)
            elif target.exists():
                # Only remove the newly installed file, never an unrelated replacement.
                if file_hash(target) != row['new_sha256']:
                    raise UpdateError('发现更新期间被其他程序改动的文件：' + row['path'])
                target.unlink()
        except (OSError, UpdateError) as error:
            errors.append(str(error))
    if errors:
        raise UpdateError('恢复旧文件未完成，请保留 .updates 目录并重新运行启动器。' + '；'.join(errors[:2]))
    (Path(root) / '.updates' / 'transaction.json').unlink(missing_ok=True)


def recover(root):
    pointer = Path(root) / '.updates' / 'transaction.json'
    if not pointer.exists():
        return
    if running_clients(root):
        raise UpdateBusy('聊天窗口仍在运行，退出全部窗口后再恢复更新。')
    journal = read_json(pointer)
    if journal.get('phase') == 'committed':
        pointer.unlink()
    else:
        rollback(root, journal)


def prepare_update(root, progress=lambda value, text: None, cancelled=lambda: False, *, cached_only=False,
                   check_only=False, approved_envelope=None, online_required=False):
    root = Path(root).resolve()
    with WorkspaceLock(root):
        recover(root)
        if running_clients(root):
            return {'state': 'busy', 'message': '已有聊天窗口运行，本次不替换文件。'}
        progress(2, '正在连接更新站点…')
        remote_error = None
        try:
            if approved_envelope is not None:
                envelope = approved_envelope
                payload = verify_envelope(envelope)
            elif cached_only:
                raise OSError('仅使用本机签名清单')
            else:
                with _open('latest.json', timeout=3 if check_only else 12) as response:
                    raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise UpdateError('更新清单过大。')
                envelope = json.loads(raw)
                payload = verify_envelope(envelope)
        except Exception as error:
            if approved_envelope is not None:
                raise UpdateError('所选更新的签名或内容无效，没有准备文件。') from error
            remote_error = error
            envelope = None
            payload = None
        if online_required and remote_error is not None:
            return {'state': 'offline', 'message': '暂时无法连接更新服务器，继续启动本地软件。'}
        for filename in (() if approved_envelope is not None else ('installed.json', 'last_manifest.json')):
            try:
                cached = read_json(root / '.updates' / filename)
                known = verify_envelope(cached)
                if payload is None or (version_tuple(known['version']), known['build']) > (version_tuple(payload['version']), payload['build']):
                    envelope, payload = cached, known
            except (OSError, UpdateError, ValueError, TypeError):
                pass
        if payload is None:
            return {'state': 'offline', 'message': '更新站点暂不可用或尚未发布清单，继续使用本地程序。'}
        try:
            local_version = version_tuple(read_json(root / 'version.json')['version'])
        except (OSError, KeyError, ValueError, TypeError, UpdateError):
            local_version = ()
        if version_tuple(payload['version']) < local_version:
            return {'state': 'current', 'message': '服务器版本较旧，保留本地程序。'}
        atomic_json(root / '.updates' / 'last_manifest.json', envelope)
        changes = []
        files = release_entries(payload)
        for index, entry in enumerate(files):
            if cancelled():
                raise UpdateCancelled('更新检查已取消。')
            progress(3 + int(3 * index / len(files)), f'正在校验程序文件 {index + 1}/{len(files)}：{entry["path"]}')
            target = local_path(root, entry['path'])
            if not matches(target, entry, cancelled):
                changes.append(entry)
        if not changes:
            atomic_json(root / '.updates' / 'installed.json', envelope)
            return {'state': 'current', 'message': '程序文件完整。', 'version': payload['version']}
        if check_only:
            return {'state': 'available', 'version': payload['version'], 'count': len(changes),
                    'local_version': '.'.join(str(n) for n in local_version) or '未知',
                    'release_notes': str(payload.get('release_notes') or '此版本没有提供更新说明。')[:60000],
                    'envelope': envelope}
        job_id = uuid.uuid4().hex
        job = job_directory(root, job_id)
        job.mkdir(parents=True)
        total = max(1, sum(entry['size'] for entry in changes))
        downloaded = 0
        component_paths = {entry['path'] for component in payload.get('components', []) for entry in component['files']}
        for index, entry in enumerate(changes):
            if entry['path'] in component_paths:
                continue
            if cancelled():
                raise UpdateCancelled('更新下载已取消。')
            cache = root / '.updates' / 'objects' / entry['sha256']
            cache.parent.mkdir(parents=True, exist_ok=True)
            if not matches(cache, entry, cancelled):
                temporary = cache.with_suffix('.part')
                try:
                    with _open(entry['url']) as response, temporary.open('wb') as output:
                        size = 0
                        digest = hashlib.sha256()
                        while chunk := response.read(256 * 1024):
                            if cancelled():
                                raise UpdateCancelled('更新下载已取消。')
                            size += len(chunk)
                            if size > entry['size']:
                                raise UpdateError('下载文件大小与清单不符。')
                            digest.update(chunk)
                            output.write(chunk)
                            progress(6 + int(6 * (downloaded + size) / total), f'正在补齐或更新 {index + 1}/{len(changes)}：{entry["path"]}')
                        output.flush()
                        os.fsync(output.fileno())
                    if size != entry['size'] or digest.hexdigest() != entry['sha256']:
                        raise UpdateError('下载文件校验失败：' + entry['path'])
                    os.replace(temporary, cache)
                finally:
                    temporary.unlink(missing_ok=True)
            staged = job / 'payload' / entry['path']
            staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cache, staged)
            downloaded += entry['size']
        for component in payload.get('components', []):
            needed = {entry['path'] for entry in changes} & {entry['path'] for entry in component['files']}
            if needed:
                stage_component(root, job, component, needed, progress, cancelled)
        atomic_json(job / 'release.json', envelope)
        atomic_json(job / 'plan.json', {'paths': [entry['path'] for entry in changes], 'components_ready': True})
        return {'state': 'ready', 'job_id': job_id, 'version': payload['version'], 'count': len(changes),
                'offline_cache': remote_error is not None}


def apply_update(root, job_id):
    root = Path(root).resolve()
    job = job_directory(root, job_id)
    with WorkspaceLock(root):
        recover(root)
        if running_clients(root):
            raise UpdateBusy('聊天窗口仍在运行，未替换文件。请退出全部窗口后重试。')
        envelope = read_json(job / 'release.json')
        payload = verify_envelope(envelope)
        plan = read_json(job / 'plan.json')
        # v1.21 ignores the signed optional components field. Its first pass
        # installs the new launcher; that launcher completes components next.
        complete = release_entries(payload) if plan.get('components_ready') else payload['files']
        entries = {entry['path']: entry for entry in complete}
        paths = plan['paths']
        if not isinstance(paths, list) or not paths or len(set(paths)) != len(paths) or any(path not in entries for path in paths):
            raise UpdateError('更新任务清单无效。')
        changes = []
        for path in sorted(paths, key=lambda path: (path == 'version.json', path)):
            target = local_path(root, path)
            entry = entries[path]
            if not matches(job / 'payload' / path, entry):
                raise UpdateError('暂存文件校验失败，未安装。')
            if matches(target, entry):
                continue
            existed = target.exists()
            if existed:
                backup = job / 'backup' / path
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            changes.append({'path': path, 'existed': existed, 'new_sha256': entry['sha256']})
        journal = {'job_id': job_id, 'phase': 'applying', 'changes': changes}
        pointer = root / '.updates' / 'transaction.json'
        atomic_json(pointer, journal)
        try:
            for row in changes:
                target = local_path(root, row['path'])
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(job / 'payload' / row['path'], target)
            # Verify the whole release again, including files that were originally intact.
            if any(not matches(local_path(root, entry['path']), entry) for entry in complete):
                raise UpdateError('安装后的文件校验未通过。')
            atomic_json(root / '.updates' / 'installed.json', envelope)
            journal['phase'] = 'committed'
            atomic_json(pointer, journal)
            pointer.unlink()
            atomic_json(root / '.updates' / 'last_result.json', {'ok': True, 'version': payload['version'], 'count': len(changes)})
        except Exception:
            rollback(root, journal)
            raise


def launch_launcher(root, skip_update=False):
    root = Path(root).resolve()
    python = root / '.app-venv' / 'Scripts' / 'python.exe'
    required = ('launcher.py', 'portable_runtime.py', 'ui_launcher.py', 'update_core.py',
                'update_trust.py', 'startup_support.py')
    if (root / '鲸伴.exe').is_file():
        command = [str(root / '鲸伴.exe')]
    elif python.is_file() and all((root / name).is_file() for name in required):
        command = [str(python), str(root / 'launcher.py')]
    else:
        raise UpdateError('找不到可用启动器，请恢复鲸伴.exe。')
    if skip_update:
        command.append('--skip-update-once')
    environment = child_environment()
    environment['AICHAT_UPDATE_RESTART'] = '1'
    log = diagnostic_path(root, 'launcher-process.log')
    if log is None:
        raise UpdateError('无法写入重启日志，请检查程序目录权限。')
    with log.open('ab') as output:
        return spawn_child(command, cwd=root, env=environment, stdout=output,
                           stderr=subprocess.STDOUT,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def bundled_helper_python(root):
    """Find the existing versioned interpreter without executing or repairing it."""
    root = Path(root)
    try:
        text = (root / '.app-venv' / 'pyvenv.cfg').read_text(encoding='utf-8-sig')
    except OSError:
        text = ''
    match = re.search(r'(?m)^version(?:_info)?\s*=\s*(3\.\d+\.\d+)\s*$', text)
    candidates = ([root / 'runtime' / 'python' / f'cpython-{match[1]}-windows-x86_64-none' / 'python.exe']
                  if match else sorted((root / 'runtime' / 'python').glob('cpython-*-windows-x86_64-none/python.exe')))
    for executable in candidates:
        if (executable.is_file() and executable.resolve().is_relative_to(root.resolve())
                and (executable.parent / 'Lib' / 'encodings' / '__init__.py').is_file()):
            return executable
    return None


def handoff_update(root, job_id):
    root = Path(root).resolve()
    job = job_directory(root, job_id)
    helper = job / 'helper'
    helper.mkdir(exist_ok=True)
    if helper.resolve().parent != job.resolve():
        raise UpdateError('更新助手目录指向了任务目录之外。')
    ready, cancel = helper / 'ready.json', helper / 'cancelled'
    ready.unlink(missing_ok=True)
    cancel.unlink(missing_ok=True)
    parent_pids = [os.getpid()]
    if getattr(sys, 'frozen', False):
        parent_pids.append(os.getppid())  # PyInstaller's one-file bootloader also holds the .exe open.
    parents = [{'pid': pid, 'token': process_token(pid)} for pid in parent_pids]
    # The installed base Python can run the standard-library-only updater. This
    # avoids copying and unpacking a second complete GUI executable every update.
    # A rescue executable remains available when that interpreter is missing.
    base = bundled_helper_python(root)
    if base is not None:
        source = Path(__file__).resolve().parent
        for name in ('update_core.py', 'update_trust.py', 'startup_support.py'):
            shutil.copy2(source / name, helper / name)
        (helper / 'apply.py').write_text(
            'import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parent))\n'
            'from update_core import helper_main\nhelper_main()\n', encoding='utf-8')
        command = [str(base), '-I', '-X', 'faulthandler', '-u', str(helper / 'apply.py')]
    else:
        rescue = job / 'payload' / '鲸伴.exe'
        if not rescue.is_file():
            rescue = root / '鲸伴.exe'
        if not rescue.is_file():
            raise UpdateError('缺少可用的更新执行环境，请恢复内置 Python 或鲸伴.exe。')
        executable = helper / '鲸伴更新助手.exe'
        shutil.copy2(rescue, executable)
        command = [str(executable), '--apply-update']
    log = diagnostic_path(root, 'update-helper-process.log')
    if log is None:
        raise UpdateError('无法写入更新助手日志，请检查程序目录权限。')
    pending = {'ok': False, 'phase': 'helper_start', 'job_id': job_id,
               'message': '更新助手尚未确认启动，原程序未替换。'}
    atomic_json(root / '.updates' / 'last_result.json', pending)
    try:
        with log.open('ab') as output:
            process = spawn_child(command + [str(root), job_id, json.dumps(parents)],
                                  cwd=helper, stdout=output, stderr=subprocess.STDOUT,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except OSError as error:
        message = str(error)
        if getattr(error, 'winerror', 0) in (4551, 1260, 577, 225, 226):
            message = 'Windows 阻止执行更新组件：' + command[0] + '。' + message
        pending['message'] = message
        atomic_json(root / '.updates' / 'last_result.json', pending)
        startup_log(root, traceback.format_exc(), 'update-helper.log')
        # Do not try alternative executables following a policy denial.
        raise UpdateError(message) from error
    return {'process': process, 'ready': ready, 'cancel': cancel, 'job_id': job_id}


def helper_main():
    root, job_id, parents_json = sys.argv[1:4]
    root = Path(root).resolve()
    install_startup_diagnostics(root, 'update-helper')
    job = job_directory(root, job_id)
    cancel = job / 'helper' / 'cancelled'
    try:
        deadline = time.monotonic() + 45
        parents = json.loads(parents_json)
        atomic_json(job / 'helper' / 'ready.json', {'job_id': job_id, 'pid': os.getpid(),
                    'spawn_pid': os.getppid() if getattr(sys, 'frozen', False) else os.getpid()})
        while any(parent['token'] and process_token(parent['pid']) == parent['token'] for parent in parents):
            if cancel.exists():
                startup_log(root, '启动器取消更新交接，未安装。', 'update-helper.log')
                return
            if time.monotonic() > deadline:
                raise UpdateBusy('启动器尚未退出，未安装更新。')
            time.sleep(0.2)
        if cancel.exists():
            return
        startup_log(root, '启动器已退出，开始事务安装。', 'update-helper.log')
        apply_update(root, job_id)
    except Exception as error:
        startup_log(root, traceback.format_exc(), 'update-helper.log')
        atomic_json(root / '.updates' / 'last_result.json', {'ok': False, 'phase': 'install',
                    'job_id': job_id, 'message': str(error)[:600]})
    # An unfinished rollback is handled on the next launcher screen, never by main.py.
    try:
        process = launch_launcher(root, skip_update=True)
        startup_log(root, f'已创建重启进程：pid={process.pid}', 'update-helper.log')
    except Exception as error:
        startup_log(root, traceback.format_exc(), 'update-helper.log')
        previous = read_json(root / '.updates' / 'last_result.json')
        previous.update({'restart_error': str(error)[:600], 'phase': 'restart_failed'})
        atomic_json(root / '.updates' / 'last_result.json', previous)
        native_error('更新交接后未能重新启动鲸伴：' + str(error)[:400]
                     + '\n\n诊断日志：' + str(diagnostic_path(root, 'update-helper.log')))


def worker_main(argv=None):
    """Isolated pre-install worker; its parent can end stalled networking safely."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('check', 'download'), required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--progress', type=Path, required=True)
    parser.add_argument('--proposal', type=Path)
    args = parser.parse_args(argv)
    last_report = 0.0

    def report(value, text):
        nonlocal last_report
        now = time.monotonic()
        if now-last_report >= 0.1:
            atomic_json(args.progress, {'value': int(value), 'text': str(text)[:500]})
            last_report = now
    try:
        approved = read_json(args.proposal) if args.mode == 'download' and args.proposal else None
        if args.mode == 'download' and approved is None:
            raise UpdateError('缺少用户选择的更新清单。')
        result = prepare_update(args.root, report, check_only=args.mode == 'check',
                                online_required=args.mode == 'check', approved_envelope=approved)
    except Exception as error:
        startup_log(args.root, traceback.format_exc())
        result = {'state': 'error', 'message': str(error)[:500]}
    atomic_json(args.result, result)


if __name__ == '__main__':
    worker_main()
