"""Build an immutable, signed static release. Never uploads or copies user data."""
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path
import shutil
import time
import zipfile
from urllib.parse import quote
from xml.etree import ElementTree

from update_core import canonical, permitted_path, verify_envelope, atomic_json, UPDATER_FORMAT
from update_trust import UPDATE_BASE_URL, PUBLIC_MODULUS, PUBLIC_EXPONENT


def build_release(root, archive, key_path):
    root, archive, key_path = Path(root).resolve(), Path(archive).resolve(), Path(key_path).resolve()
    upload = archive / '网站上传' / 'jingban'
    if key_path.is_relative_to(upload):
        raise ValueError('签名私钥必须保存在网站上传目录之外。')
    key = ElementTree.parse(key_path).getroot()
    if key.findtext('Modulus') != PUBLIC_MODULUS or key.findtext('Exponent') != PUBLIC_EXPONENT:
        raise ValueError('签名私钥与客户端内置公钥不匹配。')
    modulus = int.from_bytes(base64.b64decode(key.findtext('Modulus')), 'big')
    private = int.from_bytes(base64.b64decode(key.findtext('D')), 'big')
    version = json.loads((root / 'version.json').read_text(encoding='utf-8'))['version']
    files = [path for path in root.iterdir() if path.is_file() and permitted_path(path.name)
             and path.name not in {'publish_update.py', 'build_clean_release.py', 'build_installer.py', '生成安装包.bat', 'build_launcher.bat',
                                   'AIChatMemoryLauncher.spec', '生成纯净发行版.bat', '生成联网更新.bat'}]
    for path in (root / 'assets').iterdir():
        if path.is_file() and permitted_path(path.relative_to(root).as_posix()):
            files.append(path)
    if not (root / '鲸伴.exe').is_file():
        raise ValueError('请先打包带更新功能的鲸伴.exe，确保缺失启动源码时仍可修复。')
    entries = [{'path': path.relative_to(root).as_posix(), 'size': path.stat().st_size,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(files)]
    components = []
    runtime = root / 'onebot' / 'runtime'
    if runtime.is_dir():
        component_files = []
        for path in sorted(runtime.rglob('*')):
            if path.is_symlink():
                raise ValueError('OneBot 分发目录不允许符号链接。')
            relative_path = path.relative_to(root).as_posix()
            if path.is_file() and permitted_path(relative_path):
                component_files.append({'path': relative_path, 'size': path.stat().st_size,
                                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        info = json.loads((runtime / 'jingban-release.json').read_text(encoding='utf-8'))
        component_id = hashlib.sha256(canonical(component_files)).hexdigest()[:20]
        bundle_relative = f'components/onebot-{component_id}.zip'
        bundle = upload / bundle_relative
        bundle.parent.mkdir(parents=True, exist_ok=True)
        if not bundle.exists():
            temporary = bundle.with_suffix('.tmp')
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
                for entry in component_files:
                    zipped.write(root / entry['path'], entry['path'])
            temporary.replace(bundle)
        with zipfile.ZipFile(bundle) as zipped:
            if len(zipped.infolist()) != len(component_files):
                raise ValueError('OneBot 发布包文件数量不匹配。')
            for entry in component_files:
                if hashlib.sha256(zipped.read(entry['path'])).hexdigest() != entry['sha256']:
                    raise ValueError('OneBot 发布包与源文件不一致：' + entry['path'])
        components.append({'id': 'onebot', 'version': info['version'],
                           'archive': {'size': bundle.stat().st_size,
                                       'sha256': hashlib.sha256(bundle.read_bytes()).hexdigest(),
                                       'url': bundle_relative}, 'files': component_files})
    release_id = hashlib.sha256(canonical({'files': entries, 'components': components})).hexdigest()[:20]
    relative = f'releases/v{version}/{release_id}'
    release_dir = upload / relative
    for entry in entries:
        source = root / entry['path']
        destination = release_dir / 'files' / entry['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != entry['sha256']:
            shutil.copy2(source, destination)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('生成期间源文件发生变化，请重新生成：' + entry['path'])
        entry['url'] = relative + '/files/' + quote(entry['path'], safe='/')
    changelog = (root / 'CHANGELOG.txt').read_text(encoding='utf-8-sig')
    headings = list(re.finditer(r'^\s*v(\d+(?:\.\d+){1,3})\s*$', changelog, re.M))
    current = next((index for index, item in enumerate(headings) if item.group(1) == version), None)
    if current is None:
        raise ValueError('更新日志缺少当前版本。')
    end = headings[current+1].start() if current+1 < len(headings) else len(changelog)
    release_notes = changelog[headings[current].start():end].strip()[:60000]
    payload = {'format': UPDATER_FORMAT, 'min_updater': 1, 'version': version,
               'release_notes': release_notes,
               'build': time.time_ns(), 'release_id': release_id, 'files': entries, 'components': components}
    length = (modulus.bit_length() + 7) // 8
    digest = bytes.fromhex('3031300d060960864801650304020105000420') + hashlib.sha256(canonical(payload)).digest()
    encoded = b'\x00\x01' + b'\xff' * (length - len(digest) - 3) + b'\x00' + digest
    signature = pow(int.from_bytes(encoded, 'big'), private, modulus).to_bytes(length, 'big')
    envelope = {'payload': payload, 'signature': base64.b64encode(signature).decode('ascii')}
    verify_envelope(envelope)  # Refuse to publish an unusable or incorrectly signed manifest.
    atomic_json(release_dir / 'manifest.json', envelope)
    notes = root / 'CHANGELOG.txt'
    shutil.copy2(notes, release_dir / 'CHANGELOG.txt')
    snapshot = archive / ('v' + version)
    for entry in entries:
        destination = snapshot / 'files' / entry['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(release_dir / 'files' / entry['path'], destination)
    component_entries = []
    for component in components:
        with zipfile.ZipFile(upload / component['archive']['url']) as zipped:
            for entry in component['files']:
                destination = snapshot / 'files' / entry['path']
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(zipped.read(entry['path']))
                component_entries.append(entry)
    atomic_json(snapshot / '联网发布清单.json', envelope)
    atomic_json(snapshot / '文件清单.json', {'version': version,
                'kind': 'program_snapshot_with_rescue_launcher_and_onebot',
                'description': '程序、救援启动器与 OneBot 运行组件；不含个人配置、聊天和登录缓存。',
                'files': [{key: entry[key] for key in ('path', 'size', 'sha256')}
                          for entry in entries + component_entries]})
    lines = notes.read_text(encoding='utf-8').splitlines()
    try:
        heading = lines.index('v' + version)
    except ValueError as error:
        raise ValueError('更新日志中缺少当前版本，请先填写 CHANGELOG.txt。') from error
    (snapshot / '更新说明.txt').write_text('\n'.join(lines[heading:]) + '\n', encoding='utf-8')
    versions = []
    for directory in archive.glob('v*'):
        if not directory.is_dir():
            continue
        try:
            tuple(int(part) for part in directory.name[1:].split('.'))
        except ValueError:
            continue
        versions.append({'version': directory.name[1:], 'directory': directory.name,
                         'has_source_snapshot': (directory / 'files' / 'main.py').is_file()})
    versions.sort(key=lambda entry: tuple(int(part) for part in entry['version'].split('.')))
    atomic_json(archive / '版本索引.json', {'current_version': version, 'versions': versions})
    (archive / '网站上传' / '上传顺序.txt').write_text(
        '将 jingban 文件夹放到网站根目录，对应 ' + UPDATE_BASE_URL + '\n\n'
        '1. 先上传 jingban/components 下的新增压缩包，再上传 jingban/releases 下的新增目录及全部文件，保留以前的版本。\n'
        '2. 全部上传完成后，最后替换 jingban/latest.json（建议服务器上临时文件上传后再改名）。\n'
        '3. latest.json 应返回 JSON 文件，禁止被 SPA/错误页替代；此文件设置 Cache-Control: no-cache。\n'
        '4. release 文件可使用长期缓存；文件目录包含内容摘要，发布后不要改动该目录。\n\n'
        '只上传此处的 jingban 文件夹。签名密钥文件夹、原始项目、用户配置和数据库均不上传。\n'
        '更新清单缺失、不可访问或下载校验失败时，客户端保留原程序，不会替换半套文件。\n', encoding='utf-8')
    # Finish all files and snapshots before replacing either live pointer.
    atomic_json(root / '.updates' / 'installed.json', envelope)
    atomic_json(upload / 'latest.json', envelope)
    return {'version': version, 'release_id': release_id, 'files': len(entries),
            'bytes': sum(entry['size'] for entry in entries), 'upload_directory': str(upload),
            'snapshot_directory': str(snapshot),
            'component_files': sum(len(component['files']) for component in components),
            'component_bytes': sum(component['archive']['size'] for component in components),
            'manifest_url': UPDATE_BASE_URL + 'latest.json'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='生成鲸伴静态更新目录，不进行联网上传')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--archive', type=Path, default=Path('I:/鲸伴更新'))
    parser.add_argument('--key', type=Path, default=Path('I:/鲸伴更新/签名密钥/release-signing-key.xml'))
    args = parser.parse_args()
    print(json.dumps(build_release(args.root, args.archive, args.key), ensure_ascii=False, indent=2))
