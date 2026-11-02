"""Resolve the application's Python and construct a child-only command environment."""
import os
from pathlib import Path
import shutil
import sys


def runtime_info(root):
    root = Path(root).resolve()
    environment = root / '.app-venv'
    python = environment / 'Scripts' / 'python.exe'
    if not python.is_file():
        python = Path(sys.executable).resolve()
        environment = Path(sys.prefix).resolve()
    site = environment / 'Lib' / 'site-packages'
    binaries = {}
    for name in ('ffmpeg', 'ffprobe'):
        candidates = [root / 'tools' / 'ffmpeg' / 'bin' / f'{name}.exe',
                      root / 'tools' / name / f'{name}.exe', root / 'tools' / f'{name}.exe']
        found = next((str(p) for p in candidates if p.is_file()), None) or shutil.which(name)
        binaries[name] = found or ''
    return {'python': str(python), 'environment': str(environment),
            'yt_dlp_module_available': (site / 'yt_dlp' / '__init__.py').is_file(), **binaries}


def command_environment(root):
    info = runtime_info(root)
    environment = dict(os.environ)
    paths = [str(Path(info['python']).parent)]
    paths.extend(str(Path(info[key]).parent) for key in ('ffmpeg', 'ffprobe') if info[key])
    environment['PATH'] = os.pathsep.join(dict.fromkeys(paths)) + os.pathsep + environment.get('PATH', '')
    environment['VIRTUAL_ENV'] = info['environment']
    environment['PYTHONIOENCODING'] = 'utf-8'
    environment['PYTHONUTF8'] = '1'
    environment.pop('PYTHONHOME', None)
    environment.pop('PYTHONPATH', None)
    python = info['python'].replace("'", "''")
    # Module invocation avoids absolute interpreter paths embedded in copied .exe scripts.
    prelude = f"function global:pip {{ & '{python}' -m pip @args }}\n"
    if info['yt_dlp_module_available']:
        prelude += f"function global:yt-dlp {{ & '{python}' -m yt_dlp @args }}\n"
    return info, environment, prelude
