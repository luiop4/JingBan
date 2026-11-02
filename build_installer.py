"""Build a Windows installer exclusively from the public clean-release manifest."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

from build_clean_release import build_clean, python_version


def compiler_path(root, requested=None):
    candidates = [requested] if requested else [
        shutil.which('ISCC.exe'), root / '.updates/build-tools/InnoSetup7/ISCC.exe',
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Inno Setup 7/ISCC.exe',
        Path(os.environ.get('ProgramFiles', '')) / 'Inno Setup 7/ISCC.exe',
        Path(os.environ.get('ProgramFiles(x86)', '')) / 'Inno Setup 6/ISCC.exe']
    for item in candidates:
        if item and Path(item).is_file():
            return Path(item).resolve()
    raise ValueError('未找到 Inno Setup 编译器。请从 https://jrsoftware.org/isdl.php 安装 Inno Setup 7，或传入 --compiler。')


def verify_payload(folder, expected_version):
    folder = Path(folder).resolve()
    manifest = json.loads((folder / '发行文件清单.json').read_text(encoding='utf-8'))
    if manifest.get('clean') is not True or manifest.get('version') != expected_version:
        raise ValueError('只能使用当前版本的纯净发行目录生成安装包。')
    recorded = set()
    for entry in manifest['files']:
        relative = entry['path']
        path = folder / relative
        if path.is_symlink() or not path.resolve().is_relative_to(folder) or relative in recorded:
            raise ValueError('发行清单含非法路径。')
        if path.stat().st_size != entry['size']:
            raise ValueError('发行文件大小不符：'+relative)
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != entry['sha256']:
            raise ValueError('发行文件摘要不符：'+relative)
        recorded.add(relative)
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    if actual != recorded | {'发行文件清单.json'}:
        raise ValueError('目录含清单之外的文件，请重新生成纯净目录，不能用已运行过的目录打包。')
    for name in ('data', 'plugins', 'plugin_data', 'downloads'):
        if any(p.is_file() for p in (folder / name).rglob('*')):
            raise ValueError('纯净目录含个人数据：'+name)
    if any((folder / name).exists() for name in ('config.json', 'chat_history.sqlite3', 'plugins.json')):
        raise ValueError('纯净目录含个人配置或聊天数据库。')
    return manifest


def verify_environment(folder):
    # Exercise the copied interpreter without UI, network activity or user config.
    code = ("import sys;from pathlib import Path;sys.path.insert(0,str(Path.cwd()));"
            "from PySide6.QtWidgets import QApplication;import main,openai,requests;"
            "from voice_worker import _load_http_client;client=_load_http_client();"
            "assert Path(client.__file__).resolve().is_relative_to(Path.cwd());"
            "print('运行环境核对通过：Python、Qt、模型SDK和语音网络组件。')")
    result = subprocess.run([str(folder / '.app-venv/Scripts/python.exe'), '-I', '-B', '-X', 'utf8', '-c', code],
        cwd=folder, capture_output=True, text=True, encoding='utf-8', timeout=90,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise ValueError('纯净环境无法正常加载，已停止打包：'+result.stderr[-1800:])
    print(result.stdout.strip(), flush=True)


def build(root, output, clean_dir=None, compiler=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    iscc = compiler_path(root, compiler)
    version = str(json.loads((root / 'version.json').read_text(encoding='utf-8-sig'))['version'])
    if not re.fullmatch(r'\d+(?:\.\d+){1,3}', version) or any(int(part) > 65535 for part in version.split('.')):
        raise ValueError('version.json 中的版本号应为1.70或1.70.1这类数字版本，最多四段，每段不超过65535。')
    file_version = '.'.join(version.split('.') + ['0'] * (4-len(version.split('.'))))
    print(f'当前软件版本：v{version}（自动读取 version.json）', flush=True)
    destination = output / f'鲸伴-v{version}-安装包.exe'
    if destination.exists() or destination.with_suffix('.json').exists():
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
        destination = destination.with_name(f'鲸伴-v{version}-安装包-{stamp}.exe')
        print('同版本安装包已存在，本次另存新文件，保留原安装包。', flush=True)
    folder = Path(clean_dir).resolve() if clean_dir else build_clean(root, output)
    print('正在核对纯净目录和文件摘要…', flush=True)
    manifest = verify_payload(folder, version)
    verify_environment(folder)
    output.mkdir(parents=True, exist_ok=True)
    staging = output / f'.installer-v{version}-{uuid.uuid4().hex}.building'
    staging.mkdir()
    bundled = f'runtime\\python\\cpython-{python_version(folder, ".app-venv")}-windows-x86_64-none\\python.exe'
    command = [str(iscc), '/Qp', f'/DAppVersion={version}', f'/DAppFileVersion={file_version}',
               f'/DPayloadDir={folder}', f'/DSourceRoot={root}', f'/DBundledPython={bundled}',
               f'/O{staging}', str(root / 'installer.iss')]
    print('正在压缩完整运行环境并生成 Windows 安装包…', flush=True)
    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('编译未完成，未发布新的安装包。临时文件保留在：'+str(staging)) from None
    compiled = staging / f'鲸伴-v{version}-安装包.exe'
    if not compiled.is_file():
        raise ValueError('编译器未生成预期的安装包，临时目录：'+str(staging))
    with compiled.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    metadata = {'name': '鲸伴', 'version': version, 'installer': destination.name,
                'size': compiled.stat().st_size, 'sha256': digest,
                'clean': True, 'payload_files': len(manifest['files']),
                'includes': ['Python', '应用依赖', 'OneBot 运行组件'],
                'excludes': ['个人数据库', 'API密钥', 'QQ及浏览器登录资料', '用户插件及附件', '可选本地语音大模型']}
    metadata_file = staging / (destination.stem+'.json')
    metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    # Publish only a fully compiled and hashed file. Windows rename refuses to overwrite.
    compiled.rename(destination)
    metadata_file.rename(destination.with_suffix('.json'))
    if not any(staging.iterdir()):
        staging.rmdir()
    print('安装包已生成：'+str(destination), flush=True)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='生成可安装、可卸载且不含个人数据的完整鲸伴安装包。')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent.parent / '鲸伴发行')
    parser.add_argument('--clean-dir', type=Path, help='复用尚未启动过、且摘要匹配的同版本纯净目录')
    parser.add_argument('--compiler', type=Path, help='Inno Setup ISCC.exe 路径')
    args = parser.parse_args()
    try:
        build(args.root, args.output_dir, args.clean_dir, args.compiler)
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, '生成失败：'+str(error)+'\n')
