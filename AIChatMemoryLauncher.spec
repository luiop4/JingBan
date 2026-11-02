# Build the rescue-capable launcher; user configuration and chat data stay external.
from pathlib import Path
import os
import re
import sys

root = Path(SPECPATH)
# Resolve native libraries only from this Python/Qt environment and Windows.
# Other tools on PATH can contain incompatible DLLs with the same file names.
site = Path(sys.prefix) / 'Lib' / 'site-packages'
windows = Path(os.environ.get('SystemRoot', 'C:/Windows'))
library_paths = [site / 'PySide6', site / 'shiboken6', Path(sys.base_prefix),
                 Path(sys.base_prefix) / 'DLLs', Path(sys.executable).parent,
                 windows / 'System32', windows, windows / 'System32' / 'Wbem']
os.environ['PATH'] = os.pathsep.join(str(path) for path in library_paths if path.is_dir())

# This Qt wheel imports Windows' unversioned ICU API. Fail the build if the host
# does not provide that API rather than silently bundling a different ICU ABI.
import pefile
qt_core = pefile.PE(str(site / 'PySide6' / 'Qt6Core.dll'))
icu_imports = {symbol.name for module in qt_core.DIRECTORY_ENTRY_IMPORT
               if module.dll.lower() == b'icuuc.dll' for symbol in module.imports if symbol.name}
if icu_imports:
    system_icu = pefile.PE(str(windows / 'System32' / 'icuuc.dll'))
    exports = {symbol.name for symbol in system_icu.DIRECTORY_ENTRY_EXPORT.symbols if symbol.name}
    if icu_imports - exports:
        raise RuntimeError('Windows ICU does not provide the API required by this Qt build.')
    system_icu.close()
qt_core.close()
datas = [(str(root / name), '.') for name in ('update_core.py', 'update_trust.py', 'startup_support.py', 'author_avatar.png')]
datas += [(str(root / 'assets' / name), 'assets') for name in ('jingban-icon.ico', 'jingban-icon.png', 'mascot_v2.png')]
a = Analysis([str(root / 'launcher.py')], pathex=[str(root)], binaries=[], datas=datas,
             hiddenimports=['ui_launcher', 'portable_runtime', 'update_core', 'update_trust', 'startup_support'],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
# System API forwarders / UCRT / ICU must be provided by Windows. Do not ship
# the copies discovered in unrelated PDF/image tools, even from cached analysis.
def is_windows_api(entry):
    name = Path(entry[0]).name.lower()
    return (name.startswith(('api-ms-win-', 'ext-ms-win-')) or name == 'ucrtbase.dll'
            or re.fullmatch(r'icu.*\.dll', name) is not None)
a.binaries = [entry for entry in a.binaries if not is_windows_api(entry)]
a.datas = [entry for entry in a.datas if not is_windows_api(entry)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='鲸伴', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon=str(root / 'assets' / 'jingban-icon.ico'))
