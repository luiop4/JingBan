"""Startup diagnostics and child-process isolation; standard library only."""
from __future__ import annotations

import ctypes
from datetime import datetime
import faulthandler
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import traceback


_LOG_LOCK = threading.RLock()
_SPAWN_LOCK = threading.Lock()
_FAULT_STREAMS = []


def diagnostic_path(root, name):
    for directory in (Path(root) / '.updates' / 'diagnostics',
                      Path(tempfile.gettempdir()) / 'Jingban-diagnostics'):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / name
            with path.open('a', encoding='utf-8'):
                pass
            return path
        except OSError:
            continue
    return None


def startup_log(root, message, name='launcher.log'):
    # Logging must never turn an otherwise recoverable startup error into a crash.
    try:
        with _LOG_LOCK:
            path = diagnostic_path(root, name)
            if path is not None:
                if path.stat().st_size > 2 * 1024**2:
                    path.replace(path.with_suffix('.previous.log'))
                with path.open('a', encoding='utf-8') as stream:
                    stamp = datetime.now().astimezone().isoformat(timespec='seconds')
                    stream.write(f'[{stamp}] {str(message)[:12000]}\n')
    except (OSError, ValueError):
        pass


def native_error(message):
    if os.name == 'nt':
        try:
            ctypes.windll.user32.MessageBoxW(None, str(message)[:1800], '鲸伴启动失败', 0x10)
        except (OSError, AttributeError):
            pass


def install_startup_diagnostics(root, role='launcher'):
    path = diagnostic_path(root, role + '-fault.log')
    if path is not None:
        try:
            # Keep this descriptor open and do not rotate its file while the native
            # fault handler can write to it. A previous session is retained once.
            if path.stat().st_size > 2 * 1024**2:
                path.replace(path.with_suffix('.previous.log'))
            stream = path.open('a', encoding='utf-8', buffering=1)
            stream.write('\nSTART ' + datetime.now().astimezone().isoformat() + '\n')
            stream.flush()
            _FAULT_STREAMS.append(stream)
            faulthandler.enable(file=stream, all_threads=True)
        except (OSError, RuntimeError, ValueError):
            pass
    previous = sys.excepthook

    def report(kind, value, tb):
        details = ''.join(traceback.format_exception(kind, value, tb))
        startup_log(root, details, role + '.log')
        if sys.stderr is not None:
            previous(kind, value, tb)
        elif role == 'launcher':
            location = diagnostic_path(root, role + '.log')
            native_error('启动器发生错误：' + str(value)[:400] + '\n\n诊断日志：' + str(location))

    sys.excepthook = report
    startup_log(root, f'{role} start; pid={os.getpid()}; frozen={bool(getattr(sys, "frozen", False))}', role + '.log')
    return path


def child_environment():
    environment = dict(os.environ)
    for key in ('PYTHONHOME', 'PYTHONPATH', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH',
                'QML_IMPORT_PATH', 'QML2_IMPORT_PATH'):
        environment.pop(key, None)
    for key in list(environment):
        if key.startswith('_PYI_') or key == '_MEIPASS2':
            environment.pop(key, None)
    # A restarted one-file executable must unpack and own its own runtime.
    environment['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    environment['PYTHONUTF8'] = '1'
    environment['PYTHONUNBUFFERED'] = '1'
    environment['PYTHONFAULTHANDLER'] = '1'
    bundle = getattr(sys, '_MEIPASS', None)
    if bundle:
        prefix = os.path.normcase(os.path.abspath(bundle))
        paths = []
        for entry in environment.get('PATH', '').split(os.pathsep):
            if not entry:
                continue
            absolute = os.path.normcase(os.path.abspath(entry.strip('"')))
            try:
                bundled = os.path.commonpath((prefix, absolute)) == prefix
            except ValueError:
                bundled = False
            if not bundled:
                paths.append(entry)
        environment['PATH'] = os.pathsep.join(paths)
    return environment


def spawn_child(command, *, cwd, env=None, **kwargs):
    environment = child_environment() if env is None else env
    # PyInstaller changes SetDllDirectory for its own Qt libraries. Windows
    # children inherit that setting even when a clean env= is supplied.
    with _SPAWN_LOCK:
        kernel = None
        previous = None
        if os.name == 'nt' and getattr(sys, 'frozen', False):
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p]
            kernel.GetDllDirectoryW.restype = ctypes.c_uint32
            kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
            kernel.SetDllDirectoryW.restype = ctypes.c_int
            length = kernel.GetDllDirectoryW(0, None)
            buffer = ctypes.create_unicode_buffer(length + 1)
            if length:
                kernel.GetDllDirectoryW(len(buffer), buffer)
            previous = buffer.value or None
            if not kernel.SetDllDirectoryW(None):
                raise ctypes.WinError(ctypes.get_last_error())
        try:
            return subprocess.Popen(command, cwd=str(cwd), env=environment, **kwargs)
        finally:
            if kernel is not None:
                kernel.SetDllDirectoryW(previous)
