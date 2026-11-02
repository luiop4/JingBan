"""Bounded, data-only import of DSH packages. Never executes package scripts."""
from __future__ import annotations

from contextlib import contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
import zipfile

MAX_TOTAL = 512 * 1024**2
MAX_FILE = 64 * 1024**2
MAX_FILES = 15000
CORE_PACKAGES = {
    '@deepseek-ai/cordis': ('4.0.4', 'obgyxqWAmFn3Re8kvsuUnyW+ihrz6eJCnJO4fh1cQzDtmPYz/zzVeUkH9R94I0OwSVOocK67Kgakm04j/oQXzg=='),
    '@deepseek-ai/cosmokit': ('1.8.5', 'LXsrlem9z8dq4sLflj2yuCuYX7KqhdzF5hZly3eZyuTo8d6oDSOXuEgC5DbQWKW+lksm6zmOutQLsP/ma6wR6A=='),
    '@standard-schema/spec': ('1.1.0', 'l2aFy5jALhniG5HgqrD6jXLi/rUWrKvqN/qJx6yoJsgKhblVd+iqqU4RCXavm/jPityDo5TCvKMnpjKnOriy0w=='),
}
PET_WEB_DEPENDENCIES = {
    'esbuild-wasm': '0.28.2',
    'react': '18.3.1',
    'react-dom': '18.3.1',
}
# These imports are supplied by DSH's browser host, not by dsh-pet's own
# dependencies. Our browser bridge must supply and validate them explicitly.
PET_WEB_FILES = (
    'react/index.js', 'react/jsx-runtime.js',
    'react/cjs/react.production.min.js', 'react/cjs/react-jsx-runtime.production.min.js',
    'react-dom/index.js', 'react-dom/client.js', 'react-dom/cjs/react-dom.production.min.js',
    'scheduler/index.js', 'scheduler/cjs/scheduler.production.min.js',
    'esbuild-wasm/lib/main.js', 'esbuild-wasm/bin/esbuild', 'esbuild-wasm/esbuild.wasm',
    'esbuild-wasm/wasm_exec.js', 'esbuild-wasm/wasm_exec_node.js',
)
SKIP = {'.git', '.svn', '__pycache__', 'node_modules', '.updates'}


class ImportCancelled(RuntimeError):
    pass


def cancelled(check):
    if check():
        raise ImportCancelled('操作已取消，原有插件保持不变。')


def safe_name(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or value.startswith('/'):
        raise ValueError('插件包包含无效路径。')
    parts = value.rstrip('/').split('/')
    if any(not p or p in ('.', '..') or p.endswith((' ', '.')) or
           re.search(r'[\x00-\x1f<>"|?*]', p) or
           re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p, re.I) for p in parts):
        raise ValueError('插件包包含不安全路径：' + value[:150])
    return '/'.join(parts)


def checked_dir(root, relative):
    root = Path(root).resolve()
    result = root / relative
    if result.resolve() != result or not result.is_relative_to(root):
        raise ValueError('DSH 存储目录不能是链接或指向项目之外。')
    result.mkdir(parents=True, exist_ok=True)
    return result


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 1024**2:
        raise ValueError('插件说明或配置超过 1 MB。')
    text = path.read_text(encoding='utf-8-sig')
    # Preserve quoted strings (including URLs) while removing JSONC comments.
    text = re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/',
                  lambda m: m[0] if m[0].startswith('"') else '', text)
    text = re.sub(r'"(?:\\.|[^"\\])*"|,(\s*[}\]])',
                  lambda m: m[0] if m[0].startswith('"') else m[1], text)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('插件说明和配置必须是 JSON 对象。')
    return value


def write_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def download(url, destination, progress=lambda _: None, check=lambda: False, limit=MAX_FILE):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('registry.npmjs.org', 'nodejs.org'):
        raise ValueError('下载地址不在已支持的官方源内。')
    request = urllib.request.Request(url, headers={'User-Agent': 'Jingban-DSH/1'})
    count = 0
    last = 0.0
    with urllib.request.urlopen(request, timeout=5) as response, Path(destination).open('wb') as output:
        if urllib.parse.urlsplit(response.url).hostname != parsed.hostname:
            raise ValueError('下载源发生了非预期跳转。')
        total = response.headers.get('Content-Length', '?')
        while True:
            cancelled(check)
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            count += len(chunk)
            if count > limit:
                raise ValueError('下载文件超过体积上限。')
            output.write(chunk)
            if time.monotonic() - last > .4:
                progress(f'正在下载：{count / 1024**2:.1f} MB / {total} 字节')
                last = time.monotonic()


def download_npm(name, version, integrity, destination, progress, check):
    leaf = name.rsplit('/', 1)[-1]
    url = f'https://registry.npmjs.org/{name}/-/{leaf}-{version}.tgz'
    download(url, destination, progress, check)
    actual = base64.b64encode(hashlib.sha512(Path(destination).read_bytes()).digest()).decode()
    if actual != integrity:
        raise ValueError('下载包校验失败，未安装：' + name)


def _package_score(path, data):
    depth = len(PurePosixPath(path).parts)
    dsh = isinstance(data.get('dsh'), dict)
    deps = {**data.get('dependencies', {}), **data.get('peerDependencies', {})}
    cordis = '@deepseek-ai/cordis' in deps
    return (0 if dsh else 1 if cordis else 2, depth)


@contextmanager
def package_source(source, temporary, check=lambda: False):
    """Find the actual package inside npm archives or a GitHub source wrapper."""
    source, temporary = Path(source), Path(temporary)
    if source.is_dir():
        candidates = []
        for base, dirs, files in os.walk(source, followlinks=False):
            cancelled(check)
            relative = Path(base).relative_to(source)
            dirs[:] = [d for d in dirs if d not in SKIP and len(relative.parts) < 3
                       and not (Path(base) / d).is_symlink() and not (Path(base) / d).is_junction()]
            if 'package.json' in files:
                p = Path(base) / 'package.json'
                if p.resolve().is_relative_to(source.resolve()):
                    try:
                        candidates.append((_package_score(p.relative_to(source).as_posix(), read_json(p)), p.parent))
                    except (OSError, ValueError, TypeError):
                        pass
            if len(candidates) > 100:
                raise ValueError('发现过多 package.json，请直接选择插件自身的文件夹。')
        if not candidates:
            raise ValueError('没有找到 package.json，请选择 DSH 插件文件夹或发布包。')
        candidates.sort(key=lambda x: x[0])
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            raise ValueError('包含多个插件，请单独选择要导入的插件文件夹。')
        yield candidates[0][1]
        return
    if source.stat().st_size > MAX_TOTAL:
        raise ValueError('压缩包超过 512 MB，请选择插件发布包。')
    archive = zipfile.ZipFile(source) if zipfile.is_zipfile(source) else tarfile.open(source, 'r:*')
    with archive:
        zipped = isinstance(archive, zipfile.ZipFile)
        members = archive.infolist() if zipped else archive.getmembers()
        if len(members) > 50000:
            raise ValueError('压缩包文件数量过多，请导入单个插件包。')
        def regular(m):
            return not m.is_dir() and ((m.external_attr >> 16) & 0o170000) != 0o120000 if zipped else m.isfile()
        def contents(m):
            return archive.open(m) if zipped else archive.extractfile(m)
        def size(m):
            return m.file_size if zipped else m.size
        candidates = []
        for member in members:
            name = member.filename if zipped else member.name
            if PurePosixPath(name).name != 'package.json' or not regular(member) or size(member) > 1024**2:
                continue
            if any(p in SKIP for p in PurePosixPath(name).parts):
                continue
            try:
                with contents(member) as stream:
                    data = json.load(stream)
                candidates.append((_package_score(name, data), name))
            except (ValueError, TypeError, AttributeError):
                pass
        if not candidates:
            raise ValueError('压缩包内没有可识别的 DSH package.json。')
        candidates.sort(key=lambda x: x[0])
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            raise ValueError('压缩包内包含多个插件，请分别导入。')
        prefix = candidates[0][1][:-len('package.json')]
        seen, total = set(), 0
        temporary.mkdir(parents=True, exist_ok=True)
        for member in members:
            cancelled(check)
            name = member.filename if zipped else member.name
            if not name.startswith(prefix) or name == prefix:
                continue
            relative = name[len(prefix):].rstrip('/')
            if any(p in SKIP for p in PurePosixPath(relative).parts):
                continue
            relative = safe_name(relative)
            is_dir = member.is_dir() if zipped else member.isdir()
            if not is_dir and not regular(member):
                raise ValueError('插件包不能包含符号链接或特殊文件。')
            if is_dir:
                continue
            if relative.casefold() in seen:
                raise ValueError('插件包存在重复路径。')
            seen.add(relative.casefold())
            total += size(member)
            if len(seen) > MAX_FILES or total > MAX_TOTAL or size(member) > MAX_FILE:
                raise ValueError('插件最多 15000 个文件、512 MB，单文件最多 64 MB。')
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with contents(member) as incoming, target.open('wb') as outgoing:
                shutil.copyfileobj(incoming, outgoing)
        yield temporary


def bounded_copy(source, destination, check):
    source = Path(source).resolve()
    count = total = 0
    for base, dirs, files in os.walk(source, followlinks=False):
        cancelled(check)
        dirs[:] = [d for d in dirs if d not in SKIP]
        for name in dirs + files:
            item = Path(base) / name
            if item.is_symlink() or item.is_junction() or not item.resolve().is_relative_to(source):
                raise ValueError('插件不能包含链接或引用外部文件。')
        for name in files:
            cancelled(check)
            item = Path(base) / name
            relative = safe_name(item.relative_to(source).as_posix())
            total += item.stat().st_size
            count += 1
            if count > MAX_FILES or total > MAX_TOTAL or item.stat().st_size > MAX_FILE:
                raise ValueError('插件超过导入体积或文件数量上限。')
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, target)


def entry_file(package, metadata, selected=None):
    entry = selected or metadata.get('main')
    exports = metadata.get('exports', {})
    if not entry:
        entry = exports if isinstance(exports, str) else exports.get('.', exports) if isinstance(exports, dict) else None
        while isinstance(entry, dict):
            entry = entry.get('import') or entry.get('default') or entry.get('node')
    entry = str(entry or 'index.js').removeprefix('./')
    safe_name(entry)
    target = package / entry
    if (target.suffix.lower() not in ('.js', '.mjs', '.cjs') or not target.is_file()
            or target.resolve() != target or not target.resolve().is_relative_to(package.resolve())):
        raise ValueError('缺少已构建的 JavaScript 入口，请导入发布包；只有 TypeScript 源码的包需要先构建。')
    return entry


def standalone_entry(metadata):
    entries = metadata.get('bin', {})
    if isinstance(entries, str) and str(metadata.get('name', '')).rsplit('/', 1)[-1].endswith('-standalone'):
        return metadata['name'], entries
    if not isinstance(entries, dict):
        return None
    candidates = [(name, path) for name, path in entries.items()
                  if name == 'standalone' or name.endswith('-standalone')]
    if len(candidates) == 1 and isinstance(candidates[0][1], str):
        return candidates[0]
    return None


def runtime_dependencies(metadata):
    deps = metadata.get('dependencies', {})
    if not isinstance(deps, dict):
        raise ValueError('dependencies 必须是对象。')
    for name, version in deps.items():
        if (not re.fullmatch(r'(?:@[a-zA-Z0-9._-]+/)?[a-zA-Z0-9._-]+', str(name))
                or not isinstance(version, str) or not re.fullmatch(r'[a-zA-Z0-9.*^~<>=|+ -]+', version)):
            raise ValueError('暂不支持本地、Git、URL 或别名依赖：' + str(name))
    result = {name: value for name, value in deps.items() if name not in CORE_PACKAGES}
    if metadata.get('name') == 'dsh-pet':
        result.update(PET_WEB_DEPENDENCIES)
    return result


def inspect_package(package):
    package = Path(package)
    meta = read_json(package / 'package.json')
    name, version = str(meta.get('name', '未命名插件'))[:160], str(meta.get('version', '未知'))[:60]
    report = {'name': name, 'version': version, 'description': str(meta.get('description', ''))[:2000],
              'adapter': 'unsupported', 'status': '暂不支持', 'details': [], 'entry': '', 'dependencies': []}
    deps = {**meta.get('dependencies', {}), **meta.get('peerDependencies', {})}
    report['dependencies'] = sorted(str(key) for key in deps)
    reasons = []
    if not isinstance(meta.get('dsh'), dict) and '@deepseek-ai/cordis' not in deps:
        reasons.append('未声明 DSH 或 Cordis 插件信息。')
    standalone = standalone_entry(meta)
    dsh = meta.get('dsh', {})
    if not standalone and (isinstance(dsh, dict) and dsh.get('client') is not None
            or isinstance(meta.get('exports'), dict) and './client' in meta['exports']):
        reasons.append('包含 DSH 客户端页面入口，第一版没有通用页面兼容器。')
    host_deps = [str(n) for n in deps if str(n).startswith('@deepseek-ai/dsh-')]
    if host_deps and not standalone:
        reasons.append('尚未适配的 DSH 宿主依赖：' + '、'.join(host_deps))
    try:
        report['entry'] = entry_file(package, meta, standalone[1] if standalone else None)
        report['npm_dependencies'] = runtime_dependencies(meta)
    except ValueError as error:
        reasons.append(str(error))
    if reasons:
        report['details'] = reasons
    else:
        if standalone:
            report.update(adapter='standalone', status='原版插件 · 独立入口', command=standalone[0], details=[
                '直接运行插件发布包声明的 ' + standalone[0] + '，保留原插件代码、界面和功能。',
                '首次启用准备共享运行环境及 npm 依赖；插件自己的桌面运行库由原插件按需管理。',
                '独立模式不提供 DSH 专属页面、宿主会话及余额服务；模型和聊天数据使用插件自身设置。'])
            if standalone[0] == 'dsh-pet-standalone':
                report['interface_file'] = 'dsh-pet/standalone-runtime.json'
                report['web_compat'] = 'pet'
                report['details'].append('兼容原版网页桌宠及设置；切换仅网页时打开鲸伴插件窗口，也可一键恢复桌面显示。')
                report['details'].append('支持鲸伴新回复同步到原版桌面气泡；启动设置中可开关，无额外模型请求。')
        else:
            report.update(adapter='cordis', status='Cordis 后台入口 · 启用时检查', details=[
                '运行原版 JavaScript 入口，支持 Cordis 基础服务和可安装的 npm 运行依赖。',
                '启用时检查实际 inject 服务；缺少 DSH 模型、工具、会话等服务会明确报错。',
                '依赖安装禁用 npm 生命周期脚本；不自动构建源码。聊天事件默认关闭。'])
            if name == 'dsh-whale-widget':
                report.update(web_compat='whale-widget', interface_file='compat/whale-widget.json',
                              status='透明挂件 · 主窗口 / 桌面悬浮')
                report['details'].append('保留原插件的角色、菜单和余额面板，可附着鲸伴主窗口或悬浮桌面；空白处鼠标穿透，显示位置会记住。')
                report['details'].append('余额由鲸伴现有连接提供，插件不接收模型密钥。')
    return report


def import_package(root, source, progress=lambda _: None, check=lambda: False):
    root = Path(root).resolve()
    storage = checked_dir(root, 'data/dsh')
    catalog = checked_dir(root, 'data/dsh/packages')
    with tempfile.TemporaryDirectory(prefix='.import-', dir=storage) as scratch:
        scratch = Path(scratch)
        with package_source(source, scratch / 'unpacked', check) as original:
            report = inspect_package(original)
            identity = hashlib.sha256(report['name'].encode()).hexdigest()[:20]
            target = catalog / identity
            if target.exists():
                raise ValueError('该插件已导入。请先在 DSH 页面移除原插件，再导入新版本；设置会保留。')
            stage = scratch / 'ready'
            stage.mkdir()
            progress('正在复制插件文件并检查兼容性…')
            bounded_copy(original, stage / 'package', check)
            report['id'] = identity
            write_json(stage / 'report.json', report)
            cancelled(check)
            stage.rename(target)
            return report


