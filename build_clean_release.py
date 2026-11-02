"""Assemble a fresh runnable directory from public program files and bundled dependencies."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import uuid

from portable_runtime import relocate_environment


PROGRAM_MODULES = '''about_page agency agent_runtime app_info app_controls app_startup attachments chat_tools chat_flow command_agent desktop_actions
command_trace companionship companion_life computer_play heartbeat_panel interaction_modes settings_layout conversation_time cross_channel data_reset data_transfer dsh_history database quick_phrases_plugin browser_link browser_tools bilibili_actions bilibili_api browsing reply_style qzone_data whale_widget_host
dialogs download_qwen_model dsh_packages dsh_runtime dsh_panel dsh_web evidence_guard history_intent history_manager history_search image_history
launcher live_video main memory_scheme message_body message_cards message_format onebot_panel
onebot_process onebot_service plugin_manager plugin_sdk portable_runtime prepare_local_tts prompts
video_browser qq_delivery qq_turns qq_images autonomous_video qq_bridge qq_account qq_account_panel qq_layout qq_active qq_qzone qq_social social_life qq_stickers qwen_tts_server standard_memory startup_support stream_audio tool_context update_core update_trust
video_tools video_discovery voice_worker web_media workers ui_chat_window ui_code_block ui_command_approval
ui_command_trace ui_event_history ui_history_manager ui_launcher ui_memory_scheme'''.split()
PROGRAM_FILES = [name + '.py' for name in PROGRAM_MODULES] + '''chat_window.ui code_block.ui
command_approval.ui command_trace.ui event_history.ui history_manager.ui launcher.ui memory_scheme.ui
start.bat setup_app.bat prepare_portable.bat start_qwen_tts.bat setup_qwen_tts.bat download_qwen_model.bat
version.json CHANGELOG.txt README.md STANDARD_MEMORY.md requirements.txt requirements-app.lock.txt
requirements-tts.txt requirements-tts.lock.txt author_avatar.png 鲸伴.exe'''.split()
PUBLIC_ASSETS = '''assets/app_icon.svg assets/assistant_avatar.svg assets/jingban-icon.ico
assets/jingban-icon.png assets/mascot_v2.png assets/memory-engine.svg assets/white-whale.svg
assets/character/dafeiyu_card.txt assets/character/mingyue_full.txt'''.split()
SKIP_DIRECTORIES = {'__pycache__', '.git', '.svn', '.pytest_cache', '.mypy_cache', '.ruff_cache',
                    'uv-cache', 'pip-cache', '.cache'}
SKIP_FILES = {'.lock', 'CACHEDIR.TAG', '.DS_Store', 'Thumbs.db', 'desktop.ini', 'direct_url.json'}


def _constant_value(node, bindings):
    if isinstance(node, ast.Name) and node.id in bindings:
        return bindings[node.id]
    if isinstance(node, ast.Dict):
        return {_constant_value(key, bindings): _constant_value(value, bindings)
                for key, value in zip(node.keys, node.values)}
    if isinstance(node, ast.List):
        return [_constant_value(value, bindings) for value in node.elts]
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict'
            and len(node.args) == 1 and not node.keywords):
        return dict(_constant_value(node.args[0], bindings))
    return ast.literal_eval(node)


def source_default(root, filename, name, bindings=None):
    tree = ast.parse((root / filename).read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return _constant_value(node.value, bindings or {})
    raise ValueError(f'找不到程序默认值 {name}，请先更新发行脚本。')


def is_link(path):
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def add_file(plan, root, relative, required=True):
    source = root / relative
    if is_link(source) or not source.resolve().is_relative_to(root):
        raise ValueError('发行文件不允许引用项目之外：' + relative)
    if not source.is_file():
        if required:
            raise ValueError('完整发行缺少文件：' + relative)
        return
    plan[relative] = source


def add_tree(plan, root, relative, required=True, exclude_top=()):
    source = root / relative
    if not source.is_dir():
        if required:
            raise ValueError('完整发行缺少目录：' + relative)
        return
    if is_link(source) or not source.resolve().is_relative_to(root):
        raise ValueError('发行目录不允许引用项目之外：' + relative)
    for directory, folders, filenames in os.walk(source, followlinks=False):
        directory = Path(directory)
        folders[:] = sorted(name for name in folders if name not in SKIP_DIRECTORIES
                             and not is_link(directory / name)
                             and not (directory == source and name.lower() in exclude_top))
        for name in sorted(filenames):
            if name in SKIP_FILES or Path(name).suffix.lower() in ('.pyc', '.pyo'):
                continue
            path = directory / name
            if is_link(path):
                continue
            add_file(plan, root, path.relative_to(root).as_posix())


def python_version(root, environment):
    path = root / environment / 'pyvenv.cfg'
    if not path.is_file() or not (root / environment / 'Scripts/python.exe').is_file():
        raise ValueError(environment + ' 不完整，请先恢复对应运行环境。')
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        key, separator, value = line.partition('=')
        if separator:
            values[key.strip().lower()] = value.strip()
    version = values.get('version_info', values.get('version', ''))
    if not re.fullmatch(r'3\.\d+\.\d+', version):
        raise ValueError('无法读取 ' + environment + ' 的 Python 版本。')
    return version


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def build_clean(root, output_base, include_local_tts=False):
    root, output_base = Path(root).resolve(), Path(output_base).resolve()
    if output_base.is_relative_to(root):
        raise ValueError('发行目录请放到项目目录之外，避免与个人文件混在一起。')
    info = json.loads((root / 'version.json').read_text(encoding='utf-8-sig'))
    version = str(info['version'])
    if not re.fullmatch(r'\d+(?:\.\d+){1,3}', version):
        raise ValueError('软件版本格式不正确。')
    print(f'正在收集 v{version} 的公开程序文件与运行环境…', flush=True)
    plan = {}
    for relative in PROGRAM_FILES + PUBLIC_ASSETS:
        add_file(plan, root, relative)
    add_tree(plan, root, 'assets/icons')
    add_tree(plan, root, 'onebot/runtime', exclude_top={'config', 'cache', 'logs', 'plugins'})
    add_file(plan, root, 'onebot/README.md', required=False)
    print('正在整理聊天环境，缓存和编译文件会跳过…', flush=True)
    add_tree(plan, root, '.app-venv')
    versions = {python_version(root, '.app-venv')}
    add_file(plan, root, 'tools/uv.exe')
    add_tree(plan, root, 'tools/ffmpeg')
    if include_local_tts:
        versions.add(python_version(root, '.qwen-venv'))
        model = 'models/Qwen3-TTS-12Hz-0.6B-Base'
        if not (root / model / '.installation-complete.json').is_file():
            raise ValueError('本地 Qwen 模型尚未安装完成；请先安装，或不使用 --include-local-tts。')
        add_tree(plan, root, '.qwen-venv')
        add_tree(plan, root, model, exclude_top={'.cache', '.git'})
        add_tree(plan, root, 'tools/qwen3_tts_streaming')
    for value in versions:
        add_tree(plan, root, f'runtime/python/cpython-{value}-windows-x86_64-none')
    print('正在整理默认配置与程序依赖清单…', flush=True)
    # Check locally imported application modules before assembling an incomplete directory.
    for module in PROGRAM_MODULES:
        tree = ast.parse((root / (module + '.py')).read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            for name in names:
                local = (name or '').split('.')[0] + '.py'
                if (root / local).is_file() and local not in plan:
                    raise ValueError(f'程序新增了 {local}，请先把它加入发行脚本 PROGRAM_MODULES。')
    defaults = source_default(root, 'main.py', 'DEFAULT_CONFIG', {
        'DEFAULT_SYSTEM_PROMPT': source_default(root, 'prompts.py', 'DEFAULT_SYSTEM_PROMPT'),
        'DEFAULT_PROACTIVE': source_default(root, 'companionship.py', 'DEFAULT_PROACTIVE'),
        'DEFAULT_QQ_ACCOUNT': source_default(root, 'qq_account.py', 'DEFAULT_QQ_ACCOUNT'),
    })
    appearance = source_default(root, 'main.py', 'DEFAULT_APP_SETTINGS')
    appearance['assistant'].update({'name': '大肥鱼', 'initials': '大肥'})
    total = sum(source.stat().st_size for source in plan.values())
    output_base.mkdir(parents=True, exist_ok=True)
    name = f'鲸伴-v{version}-纯净版-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:4]
    destination = output_base / name
    staging = output_base / ('.' + name + '.building')
    staging.mkdir()
    print(f'开始生成 v{version}，共 {len(plan)} 个文件，约 {total / 1024**3:.2f} GiB。', flush=True)
    print('不读取现有 config.json、app_settings.json、数据库或 QQ 登录文件。', flush=True)
    copied = 0
    next_report = time.monotonic()
    try:
        for index, (relative, source) in enumerate(sorted(plan.items()), 1):
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            before = source.stat()
            shutil.copyfile(source, target)
            after = source.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError('生成期间程序文件发生变化，请停止修改程序后重试：' + relative)
            copied += target.stat().st_size
            if time.monotonic() >= next_report:
                print(f'复制 {index}/{len(plan)}，{copied / max(1, total):.0%}：{relative}', flush=True)
                next_report = time.monotonic() + 3
        for folder in ('data', 'downloads', 'plugins', 'plugin_data', 'assets/stickers', 'assets/voices', 'models'):
            (staging / folder).mkdir(parents=True, exist_ok=True)
        write_json(staging / 'config.example.json', defaults)
        write_json(staging / 'app_settings.json', appearance)
        (staging / '首次使用.txt').write_text(
            f'鲸伴 v{version} 纯净发行版\n\n'
            '1. 将整个目录解压或复制到可写位置，双击 start.bat 或鲸伴.exe。\n'
            '2. 到“设置”填写自己的 API 密钥；聊天数据库和个人配置会在首次启动时新建。\n'
            '3. QQ 接入已包含 OneBot 组件，仍需本机安装兼容 QQ，在软件页面启动并扫码登录。\n'
            '4. 语音播放使用用户自己的语音服务设置。本地 Qwen 语音可在设置中安装；需要自己提供参考音频。\n'
            '5. 此目录包含项目 Python 和聊天环境，常规启动不依赖系统 Python。\n\n'
            '此目录未携带开发者的数据库、API 配置、QQ 登录状态、用户插件、附件、下载及缓存。\n'
            'app_settings.json 与 config.example.json 是根据程序公开默认值重新生成的文件。\n'
            + ('已额外包含完整的本地 Qwen 环境和模型。\n' if include_local_tts else '本地 Qwen 环境和模型未预装，可按需安装。\n'),
            encoding='utf-8')
        # First relocation checks that every required base interpreter was included.
        relocate_environment(staging, '.app-venv')
        if include_local_tts:
            relocate_environment(staging, '.qwen-venv')
        if any((staging / relative).exists() for relative in ('config.json', 'plugins.json', '.updates')):
            raise ValueError('发现不应出现在纯净目录中的个人状态，已停止生成。')
        # Write the final home now, keeping the directory marked unfinished until complete.
        for environment in (['.app-venv', '.qwen-venv'] if include_local_tts else ['.app-venv']):
            config = staging / environment / 'pyvenv.cfg'
            text = config.read_text(encoding='utf-8-sig')
            config.write_text(text.replace(str(staging), str(destination)), encoding='utf-8')
        records = []
        print('正在生成发行文件的 SHA-256 清单…', flush=True)
        for path in sorted(staging.rglob('*')):
            if path.is_file():
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    while chunk := stream.read(1024 * 1024):
                        digest.update(chunk)
                records.append({'path': path.relative_to(staging).as_posix(),
                                'size': path.stat().st_size, 'sha256': digest.hexdigest()})
        write_json(staging / '发行文件清单.json', {'version': version, 'clean': True,
                   'local_tts_included': include_local_tts, 'files': records})
        os.replace(staging, destination)
    except Exception:
        print('生成未完成；请勿分发本次输出。已保留 .building 临时目录或未完成目录供检查。', file=sys.stderr)
        raise
    print('\n生成完成：' + str(destination), flush=True)
    print('把这个新目录整体压缩发给别人即可。首次启动会创建新的个人配置和数据库。', flush=True)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='生成带运行环境和 OneBot 的纯净鲸伴目录，不修改个人数据。')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent.parent / '鲸伴发行')
    parser.add_argument('--include-local-tts', action='store_true', help='额外携带已完整安装的本地 Qwen 环境及模型')
    args = parser.parse_args()
    try:
        build_clean(args.root, args.output_dir, args.include_local_tts)
    except Exception as error:
        print('生成失败：' + str(error), file=sys.stderr)
        raise SystemExit(1)
