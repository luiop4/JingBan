"""Relocate bundled Windows virtual environments before launching their Python.

Uses only the standard library so the bundled base interpreter can run it even
when the virtual environment still points to the machine it was copied from.
"""
from pathlib import Path
import re
import sys


def relocate_environment(root: Path, name: str, required: bool = True) -> None:
    root = root.resolve()
    environment = root / name
    config = environment / 'pyvenv.cfg'
    executable = environment / 'Scripts' / 'python.exe'
    if not config.is_file() or not executable.is_file():
        if required:
            raise RuntimeError(f'{name} is incomplete. Copy the complete environment or run setup_app.bat.')
        return
    text = config.read_text(encoding='utf-8-sig')
    values = {}
    for line in text.splitlines():
        key, sep, value = line.partition('=')
        if sep:
            values[key.strip().lower()] = value.strip()
    version = values.get('version_info', values.get('version', ''))
    if not re.fullmatch(r'3\.\d+\.\d+', version):
        raise RuntimeError(f'Cannot determine the Python version required by {name}.')
    # Use the versioned directory, never uv's movable alias/junction.
    home = root / 'runtime' / 'python' / f'cpython-{version}-windows-x86_64-none'
    if not (home / 'python.exe').is_file():
        raise RuntimeError(f'Missing bundled Python {version}. Copy runtime/python together with the project.')
    replacements = {'home': str(home), 'base-prefix': str(home), 'base-exec-prefix': str(home),
                    'base-executable': str(home / 'python.exe'), 'executable': str(home / 'python.exe')}
    lines = []
    found_home = False
    for line in text.splitlines():
        key, sep, value = line.partition('=')
        normalized = key.strip().lower()
        if sep and normalized in replacements:
            line = f'{key.strip()} = {replacements[normalized]}'
            found_home |= normalized == 'home'
        lines.append(line)
    if not found_home:
        lines.append(f'home = {home}')
    updated = '\n'.join(lines) + '\n'
    if updated != text:
        temporary = config.with_suffix('.cfg.tmp')
        temporary.write_text(updated, encoding='utf-8')
        temporary.replace(config)


def prepare_portable_runtime(root: Path) -> list[str]:
    relocate_environment(root, '.app-venv')
    warnings = []
    try:
        relocate_environment(root, '.qwen-venv', required=False)
    except (OSError, RuntimeError) as error:
        # Optional local TTS must never stop the chat application from opening.
        warnings.append(str(error))
    return warnings


if __name__ == '__main__':
    try:
        for warning in prepare_portable_runtime(Path(__file__).resolve().parent):
            print('Local voice: ' + warning)
    except (OSError, RuntimeError) as error:
        print('Unable to prepare portable runtime: ' + str(error), file=sys.stderr)
        sys.exit(1)
