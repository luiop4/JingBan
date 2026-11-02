"""Read DSH session logs as inert historical messages, never as executable state.

Format references: deepseek-ai/deepseek-harness, packages/core/session/src/types.ts
and packages/session-query/session-log-export/src/archive.ts (session format v4).
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import uuid
import zipfile

MAX_LOG = 64 * 1024**2
MAX_TOTAL = 256 * 1024**2
MAX_MESSAGES = 100000
LOG_NAME = re.compile(r'(?:session(?:\.v\d+)?|[\w-]+)\.jsonl(?:\.zstd|\.zst)?$', re.I)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def timestamp(value):
    """Missing dates stay visibly unknown instead of being dated at import time."""
    try:
        if isinstance(value, bool):
            return ''
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000 if value >= 100000000000 else value).astimezone().isoformat(timespec='seconds')
        if isinstance(value, str) and value.strip():
            return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone().isoformat(timespec='seconds')
    except (ValueError, OverflowError, OSError):
        pass
    return ''


@dataclass
class ImportedAttachment:
    name: str
    kind: str
    mime: str
    data: bytes | None


@dataclass
class ImportedMessage:
    key: str
    role: str
    text: str
    at: str
    attachments: list = field(default_factory=list)


@dataclass
class ImportedSession:
    identity: str
    title: str
    origin: str
    messages: list
    missing: int = 0
    undated: int = 0
    subagent: bool = False


class Budget:
    def __init__(self):
        self.total = 0

    def add(self, size):
        self.total += size
        if self.total > MAX_TOTAL:
            raise ValueError('本次导入内容超过 256 MB，请分批选择会话文件。')


def checked_bytes(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('会话或附件文件不存在，或为链接。')
    with path.open('rb') as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise ValueError('单个会话日志或附件超过读取上限。')
    return value


def zstd_frames(source):
    """Locate standard frames (RFC 8878 §3.1); refuse truncated source copies."""
    offset, frames = 0, []

    def advance(size):
        nonlocal offset
        end = offset + size
        if end > len(source):
            raise ValueError('压缩日志尾部不完整，请先退出 DSH 再复制，或使用官方 ZIP 导出。')
        value = source[offset:end]
        offset = end
        return value

    while offset < len(source):
        start = offset
        if advance(4) != b'\x28\xb5\x2f\xfd':
            raise ValueError('压缩日志不是标准 Zstandard 帧。')
        descriptor = advance(1)[0]
        if descriptor & 0x18:
            raise ValueError('压缩日志帧头不合法。')
        single = bool(descriptor & 0x20)
        size_flag = descriptor >> 6
        dictionary_bytes = (0, 1, 2, 4)[descriptor & 3]
        content_bytes = (1 if single else 0, 2, 4, 8)[size_flag]
        advance((0 if single else 1) + dictionary_bytes + content_bytes)
        last = False
        while not last:
            block = int.from_bytes(advance(3), 'little')
            last = bool(block & 1)
            block_type = (block >> 1) & 3
            if block_type == 3:
                raise ValueError('压缩日志使用了无效块类型。')
            advance(1 if block_type == 1 else block >> 3)
        if descriptor & 4:
            advance(4)
        frames.append((start, offset))
        if len(frames) > 100000:
            raise ValueError('压缩帧过多，请分批导出会话。')
    if not frames:
        raise ValueError('压缩日志为空。')
    return frames


def decompress(root, source):
    """Use an existing optional Node runtime; do not install or start DSH plugins."""
    frames = zstd_frames(source)
    try:
        import zstandard
    except ImportError:
        zstandard = None
    if zstandard is not None:
        import io
        chunks, total = [], 0
        for begin, end in frames:
            with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(source[begin:end])) as reader:
                value = reader.read(MAX_LOG - total + 1)
            total += len(value)
            if total > MAX_LOG:
                raise ValueError('解压后的单个会话超过 64 MB。')
            chunks.append(value)
        return b''.join(chunks)
    node = Path(root) / 'data/dsh/runtime/node.exe'
    if not node.is_file() or node.is_symlink():
        raise ValueError('这是 Zstandard 压缩日志。请先在「插件 → DSH 插件兼容」安装共享运行环境，'
                         '或在 DSH 会话菜单选择「下载 Session 日志」后导入 ZIP；不需要启用插件。')
    # A plain one-shot Node decompression stops at the first independent frame.
    # Length-prefix each frame; no source text or path becomes JavaScript code.
    payload = b''.join((end - begin).to_bytes(4, 'little') + source[begin:end] for begin, end in frames)
    script = ("const z=require('node:zlib'),f=require('node:fs'),s=f.readFileSync(0),out=[];"
              "let p=0,n=0;while(p<s.length){const len=s.readUInt32LE(p);p+=4;"
              "const b=z.zstdDecompressSync(s.subarray(p,p+len),{maxOutputLength:Math.max(1,67108864-n)});"
              "p+=len;n+=b.length;if(n>67108864)throw Error('size');out.push(b);}"
              "process.stdout.write(Buffer.concat(out,n));")
    env = dict(os.environ)
    env.pop('NODE_OPTIONS', None)
    env.pop('NODE_PATH', None)
    try:
        result = subprocess.run([str(node), '-e', script], input=payload, capture_output=True,
                                timeout=45, env=env,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('压缩会话解压失败或超时，请改用 DSH 导出的 ZIP 日志。') from error
    if result.returncode or len(result.stdout) > MAX_LOG:
        raise ValueError('压缩会话解压失败：文件可能不完整，或共享 Node 版本不支持 Zstandard。')
    return result.stdout


def content_parts(content, read_media):
    if isinstance(content, str):
        return content, []
    if not isinstance(content, list):
        raise ValueError('消息正文不是支持的文本或内容块数组。')
    texts, attachments = [], []
    for block in content:
        if not isinstance(block, dict):
            raise ValueError('消息内容块格式错误。')
        kind = block.get('type', block.get('kind'))
        if kind in ('text', 'input_text', 'output_text') or kind is None and isinstance(block.get('text'), str):
            if isinstance(block.get('text'), str):
                texts.append(block['text'])
        elif kind in ('image', 'image_url', 'file'):
            ref = block.get('attachment')
            ref = ref if isinstance(ref, dict) else {}
            attachment_id = str(ref.get('attachmentId', ''))
            mime = str(ref.get('mediaType', ''))[:120]
            original_name = str(ref.get('name') or ('图片' if kind != 'file' else '文件'))
            name = original_name[:200]
            data = read_media(attachment_id, original_name, kind != 'file') if attachment_id else None
            attachments.append(ImportedAttachment(name, 'file' if kind == 'file' else 'image', mime, data))
            if data is None:
                texts.append(f'[{name}：导入源未包含原文件]')
        # Thinking, tool-call/result, and provider transport blocks are not chat text.
    return '\n\n'.join(texts), attachments


def parse_session(raw, origin, read_media):
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeError as error:
        raise ValueError('日志不是 UTF-8 编码。') from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        records = []
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f'第 {number} 行日志不完整或格式错误；请先关闭 DSH 再复制日志。') from error
            if not isinstance(record, dict):
                raise ValueError(f'第 {number} 行不是会话事件对象。')
            records.append(record)
    else:
        if isinstance(document, dict) and isinstance(document.get('events'), list):
            header = document.get('header', document.get('session', {}))
            header = header if isinstance(header, dict) else {}
            records = [{'type': 'session', **header}, *document['events']]
        elif isinstance(document, list):
            records = document
        elif isinstance(document, dict) and isinstance(document.get('messages'), list):
            records = [{'type': 'session', 'id': document.get('id', document.get('sessionId', '')),
                        'title': document.get('title', '')}]
            for message in document['messages']:
                if not isinstance(message, dict) or message.get('role') not in ('user', 'assistant'):
                    continue
                records.append({'type': message['role'] + '/message', 'time': message.get('created_at', message.get('time')),
                                'data': message if message['role'] == 'user' else {'message': message}})
        else:
            raise ValueError('不是支持的 DSH 日志，请选择 Session 日志 ZIP、JSONL 或含 events/messages 的 JSON。')
    if not records or any(not isinstance(record, dict) for record in records):
        raise ValueError('会话事件列表为空或格式错误。')
    header = next((event for event in records if event.get('type') == 'session'), {})
    version = header.get('version', 0)
    if type(version) is not int or version not in range(5):
        raise ValueError('暂不支持此会话日志版本，请用 DSH 导出当前格式的 Session 日志。')
    title = header.get('title') or ''
    messages, seen = [], set()
    undated = missing = 0
    for index, event in enumerate(records):
        kind = event.get('type')
        data = event.get('data', {})
        if not isinstance(data, dict) and kind in ('user/message', 'assistant/message'):
            raise ValueError('消息事件载荷格式错误。')
        if not isinstance(data, dict):
            continue
        if kind == 'session/title':
            title = data.get('title') or title
        if kind not in ('user/message', 'assistant/message'):
            continue
        # Replacements contain compressed/system surface state, not another utterance.
        if event.get('surfaceOp', 'append') != 'append':
            continue
        role = kind.split('/')[0]
        message = data.get('message', data)
        if not isinstance(message, dict):
            raise ValueError('消息载荷格式错误。')
        if role == 'user':
            source = message.get('source', data.get('source'))
            if isinstance(source, dict) and source.get('kind') != 'user':
                continue
            if version >= 4 and not isinstance(source, dict):
                continue
        identity = message.get('id')
        key = role + ':' + (str(identity) if identity is not None else 'seq:' + str(event.get('seq', index)))
        if key in seen:
            continue
        body, attachments = content_parts(message.get('content', message.get('text', '')), read_media)
        if not body.strip() and not attachments:
            continue
        seen.add(key)
        at = timestamp(event.get('time', message.get('created_at', message.get('createdAt'))))
        missing += sum(attachment.data is None for attachment in attachments)
        undated += not bool(at)
        messages.append(ImportedMessage(key, role, body, at, attachments))
        if len(messages) > MAX_MESSAGES:
            raise ValueError('单个会话超过十万条消息，请分批导出。')
    if not messages:
        raise ValueError('没有可迁移的用户消息或助手回复。')
    identity = header.get('id')
    if not isinstance(identity, (str, int)) or not str(identity):
        first = messages[0]
        identity = digest(json.dumps([first.role, first.text, first.at], ensure_ascii=False).encode())
    title = str(title).strip() or next((m.text[:60] for m in messages if m.role == 'user' and m.text.strip()), 'DSH 历史会话')
    subagent = header.get('origin') == 'subagent'
    return ImportedSession('dsh:' + digest(str(identity).encode()), title.replace('\n', ' ')[:160],
                           origin, messages, missing, undated, subagent)


def zip_sessions(path, root, budget):
    sessions, errors = [], []
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 20000:
            raise ValueError('ZIP 包文件过多，请只选择 DSH 导出的会话日志包。')
        names = {}
        for entry in entries:
            name = PurePosixPath(entry.filename)
            # Attachment IDs may contain a colon in their basename, not a drive prefix.
            if (not name.parts or name.is_absolute() or '..' in name.parts
                    or '\\' in entry.filename or ':' in name.parts[0]):
                raise ValueError('ZIP 中包含不安全的路径。')
            if entry.filename in names:
                raise ValueError('ZIP 中有重复文件名。')
            names[entry.filename] = entry

        def read(entry, limit):
            if entry.file_size > limit:
                raise ValueError('ZIP 中的单个日志或附件超过大小限制。')
            with archive.open(entry) as stream:
                value = stream.read(limit + 1)
            if len(value) > limit:
                raise ValueError('ZIP 解压内容超过大小限制。')
            budget.add(len(value))
            return value

        cache = {}

        def media(identifier, name, image):
            if not re.fullmatch(r'[A-Za-z0-9:_-]{1,180}', identifier):
                return None
            if image:
                candidates = [key for key in names if key.startswith('media/' + identifier + '.') and key.count('/') == 1]
            else:
                key = identifier.removeprefix('sha256:')
                safe_name = re.sub(r'[\\/\x00-\x1f\x7f]', '_', name)
                safe_name = 'file' if safe_name in ('', '.', '..') else safe_name
                candidates = [key_name for key_name in names if key_name == f'files/{key[:2]}/{key}/{safe_name}']
            if len(candidates) != 1:
                return None
            key = candidates[0]
            if key not in cache:
                cache[key] = read(names[key], 20 * 1024**2 if image else 50 * 1024**2)
            return cache[key]

        logs = [entry for entry in entries if not entry.is_dir() and LOG_NAME.fullmatch(PurePosixPath(entry.filename).name)]
        if not logs:
            raise ValueError('ZIP 中没有 DSH JSONL 会话日志；鲸伴备份请使用“导入备份”。')
        for entry in logs:
            try:
                raw = read(entry, MAX_LOG)
                if entry.filename.endswith(('.zstd', '.zst')):
                    raw = decompress(root, raw)
                    budget.add(len(raw))
                sessions.append(parse_session(raw, Path(path).name + ' / ' + entry.filename, media))
            except ValueError as error:
                errors.append(PurePosixPath(entry.filename).name + '：' + str(error))
    return sessions, errors


def discover(source):
    source = Path(source).resolve()
    if not source.is_dir():
        return [source]
    found = []
    scanned = 0
    for directory, folders, files in os.walk(source, followlinks=False):
        folders[:] = [name for name in folders if name not in ('node_modules', '.git', 'cache', 'npm-cache')
                      and not (Path(directory) / name).is_symlink()
                      and not (Path(directory) / name).is_junction()]
        for name in files:
            scanned += 1
            if scanned > 100000:
                raise ValueError('所选目录太大，请直接选择 DSH 的 sessions 子目录。')
            path = Path(directory) / name
            if LOG_NAME.fullmatch(name) and not path.is_symlink():
                found.append(path)
                if len(found) > 2000:
                    raise ValueError('会话文件超过 2000 个，请选择更小的子目录分批迁移。')
    # DSH may retain several physical format generations; select the latest one.
    chosen = {}
    for path in found:
        match = re.fullmatch(r'session(?:\.v(\d+))?\.jsonl(?:\.zstd|\.zst)?', path.name, re.I)
        key = str(path.parent) if match else str(path)
        rank = (int(match.group(1) or 0) if match else 0, not path.name.endswith(('.zstd', '.zst')))
        if key not in chosen or rank > chosen[key][0]:
            chosen[key] = (rank, path)
    return [item[1] for item in sorted(chosen.values(), key=lambda value: str(value[1]))]


def scan(source, root, progress=lambda text: None):
    paths, budget, sessions, errors = discover(source), Budget(), [], []
    for index, path in enumerate(paths):
        progress(f'正在读取会话 {index + 1}/{len(paths)}：{path.name}')
        try:
            if path.suffix.lower() == '.zip':
                parsed, failures = zip_sessions(path, root, budget)
                sessions.extend(parsed)
                errors.extend(failures)
            else:
                raw = checked_bytes(path, MAX_LOG)
                budget.add(len(raw))
                if path.name.endswith(('.zstd', '.zst')):
                    raw = decompress(root, raw)
                    budget.add(len(raw))
                # Loose logs normally lack the exported attachment objects.
                sessions.append(parse_session(raw, path.name, lambda *args: None))
        except (ValueError, OSError, zipfile.BadZipFile, RuntimeError) as error:
            errors.append(path.name + '：' + str(error))
        if sum(len(session.messages) for session in sessions) > MAX_MESSAGES:
            raise ValueError('本次超过十万条消息，请分批选择会话。')
    if not sessions:
        raise ValueError('\n'.join(errors[:5]) if errors else '未找到会话日志。请选择 DSH 的 sessions 目录，或导入 Session 日志 ZIP。')
    # Same session appearing in a copied/exported source only needs one preview row.
    merged = {}
    for session in sessions:
        if session.identity not in merged or len(session.messages) > len(merged[session.identity].messages):
            merged[session.identity] = session
    return list(merged.values()), errors


def import_sessions(root, sessions, **options):
    from update_core import WorkspaceLock, running_clients
    root = Path(root).resolve()
    with WorkspaceLock(root):
        if any(pid != os.getpid() for pid in running_clients(root)):
            raise ValueError('同一目录还有其他鲸伴窗口运行，请先退出其他窗口再迁移。')
        return _import_sessions(root, sessions, **options)


def _import_sessions(root, sessions, *, visible=False, organize=False, progress=lambda text: None):
    root = Path(root).resolve()
    db_path = root / 'data/chat_history.sqlite3'
    if (not db_path.is_file() or db_path.is_symlink()
            or db_path.resolve() != root / 'data/chat_history.sqlite3'):
        raise ValueError('当前鲸伴聊天数据库不存在。')
    backup_dir = root / 'backups'
    backup_dir.mkdir(exist_ok=True)
    if backup_dir.is_symlink() or backup_dir.resolve() != root / 'backups':
        raise ValueError('备份目录不能指向项目之外。')
    backup_path = backup_dir / ('before-dsh-import-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8] + '.sqlite3')
    with closing(sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(backup_path)) as dst:
        src.backup(dst)
    directory = root / 'data/attachments' / ('dsh-' + uuid.uuid4().hex)
    directory.parent.mkdir(exist_ok=True)
    if directory.parent.resolve() != root / 'data/attachments':
        raise ValueError('附件目录不能指向项目之外。')
    created = []
    inserted = duplicates = conflicts = 0
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    try:
        with closing(sqlite3.connect(db_path, timeout=20)) as con, con:
            con.execute('BEGIN IMMEDIATE')
            for session in sessions:
                progress('正在迁移：' + session.title)
                for message in session.messages:
                    payload = [message.role, message.text, message.at,
                               [[a.name, a.kind, a.mime, digest(a.data) if a.data is not None else None] for a in message.attachments]]
                    fingerprint = digest(json.dumps(payload, ensure_ascii=False).encode())
                    previous = con.execute('SELECT i.content_hash FROM dsh_import_items i JOIN messages m ON m.id=i.message_id '
                                           'WHERE i.session_key=? AND i.item_key=?', (session.identity, message.key)).fetchone()
                    if previous:
                        if previous[0] == fingerprint:
                            duplicates += 1
                        else:
                            conflicts += 1
                        continue
                    row = con.execute('INSERT INTO messages(conversation_key,source,role,content,peer_id,peer_name,created_at) '
                                      'VALUES (?,?,?,?,?,?,?)',
                                      (session.identity, 'dsh', message.role, message.text, '', session.title, message.at))
                    mid = row.lastrowid
                    con.execute('INSERT OR REPLACE INTO dsh_import_items VALUES (?,?,?,?,?)',
                                (session.identity, message.key, mid, fingerprint, now))
                    con.execute('INSERT INTO message_extras VALUES (?,?,?)',
                                (mid, 'dsh_import', json.dumps({'title': session.title, 'source': session.origin}, ensure_ascii=False)))
                    if not organize:
                        con.execute('INSERT INTO message_extras VALUES (?,?,?)', (mid, 'archive_only', 'dsh'))
                    if not visible:
                        con.execute('INSERT INTO hidden_messages VALUES (?)', (mid,))
                    for number, attachment in enumerate(message.attachments):
                        if attachment.data is None:
                            continue
                        if not directory.exists():
                            directory.mkdir()
                        extension = mimetypes.guess_extension(attachment.mime) or Path(attachment.name).suffix or '.bin'
                        if not re.fullmatch(r'\.[a-zA-Z0-9]{1,10}', extension):
                            extension = '.bin'
                        path = directory / f'{mid}-{number}{extension}'
                        created.append(path)
                        path.write_bytes(attachment.data)
                        con.execute('INSERT INTO message_attachments(message_id,file_name,kind,mime_type,local_path,extracted_text,size_bytes) '
                                    'VALUES (?,?,?,?,?,?,?)', (mid, attachment.name, attachment.kind, attachment.mime,
                                                             path.relative_to(root).as_posix(), '', len(attachment.data)))
                    inserted += 1
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
        raise
    return {'inserted': inserted, 'duplicates': duplicates, 'conflicts': conflicts, 'backup': str(backup_path)}


# The reader above has no Qt dependency; only the user-facing workflow uses Qt.
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
                              QAbstractItemView, QPlainTextEdit, QCheckBox)
from dialogs import FishDialog


class DshHistoryWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, root, operation, value, parent=None, **options):
        super().__init__(parent)
        self.root, self.operation, self.value, self.options = root, operation, value, options

    def run(self):
        try:
            if self.operation == 'scan':
                sessions, warnings = scan(self.value, self.root, self.progress.emit)
                result = {'sessions': sessions, 'warnings': warnings}
            else:
                result = import_sessions(self.root, self.value, progress=self.progress.emit, **self.options)
            self.completed.emit(result)
        except Exception as error:
            self.failed.emit(str(error))


class DshHistoryDialog(QDialog):
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root, self.worker, self.sessions = Path(root), None, []
        self.imported = False
        self.setWindowTitle('从 DSH 迁移聊天记录')
        self.resize(780, 660)
        self.setMinimumSize(580, 440)
        layout = QVBoxLayout(self)
        description = QLabel('选择 DSH 的 sessions 目录，或 Session 日志 ZIP / JSONL / JSON 文件。'
                             '\n只追加聊天记录，保留当前鲸伴数据；导入前自动备份数据库。')
        description.setWordWrap(True)
        layout.addWidget(description)
        actions = QHBoxLayout()
        self.file_button = QPushButton('选择日志文件…', self)
        self.folder_button = QPushButton('选择 DSH 会话目录…', self)
        self.help_button = QPushButton('不知道记录在哪？', self)
        for button in (self.file_button, self.folder_button, self.help_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(['导入', '会话标题', '消息', '起始时间'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        layout.addWidget(self.table, 2)
        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText('选择会话后，在这里预览部分原文。')
        layout.addWidget(self.preview, 1)
        self.visible = QCheckBox('将导入记录显示在聊天列表（默认只在历史记录中查看和检索）', self)
        self.organize = QCheckBox('允许记忆方案整理导入记录（后续整理会调用模型并消耗 Token）', self)
        self.visible.setChecked(False)
        self.organize.setChecked(False)
        layout.addWidget(self.visible)
        layout.addWidget(self.organize)
        self.status = QLabel('等待选择导入源。原始思考、系统提示和工具操作不会作为新任务执行。', self)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        bottom = QHBoxLayout()
        self.import_button = QPushButton('导入所选会话', self)
        self.import_button.setEnabled(False)
        self.close_button = QPushButton('关闭', self)
        bottom.addStretch()
        bottom.addWidget(self.import_button)
        bottom.addWidget(self.close_button)
        layout.addLayout(bottom)
        self.file_button.clicked.connect(self.choose_file)
        self.folder_button.clicked.connect(self.choose_folder)
        self.help_button.clicked.connect(self.help)
        self.close_button.clicked.connect(self.accept)
        self.import_button.clicked.connect(self.import_selected)
        self.table.currentCellChanged.connect(self.show_preview)

    def default_directory(self):
        home = Path(os.environ.get('DSH_HOME') or Path.home() / '.dsh')
        return str(home / 'sessions' if (home / 'sessions').is_dir() else home if home.is_dir() else Path.home())

    def help(self):
        FishDialog.information(self, '找到 DSH 聊天记录',
            '方式一：先退出 DSH，再选择会话目录。默认位置通常是：\n'
            + str(Path.home() / '.dsh' / 'sessions')
            + '\n如果你修改过 DSH_HOME，请选择对应目录下的 sessions。\n\n'
            '方式二：打开 DSH 的目标对话，在顶部“更多”菜单选择“下载 Session 日志”；'
            '也可以在 DSH 输入 /export，下载后在这里选择 ZIP。\n\n'
            '建议优先选择 ZIP：官方日志包还会包含图片与文件。'
            '单独复制的压缩日志需要已安装共享 Node 运行环境，且可能不包含原附件。')

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择 DSH Session 日志', self.default_directory(),
            'DSH 日志 (*.zip *.jsonl *.jsonl.zstd *.jsonl.zst *.json);;所有文件 (*)')
        if path:
            self.start('scan', path)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, '选择 DSH sessions 目录（请先退出 DSH）', self.default_directory())
        if path:
            self.start('scan', path)

    def start(self, operation, value, **options):
        if self.worker is not None:
            return
        if operation == 'scan':
            self.sessions.clear()
            self.table.setRowCount(0)
            self.preview.clear()
        self.set_busy(True)
        self.status.setText('正在读取日志…' if operation == 'scan' else '正在备份数据库并追加记录，请勿关闭程序…')
        worker = self.worker = DshHistoryWorker(self.root, operation, value, self, **options)
        worker.progress.connect(self.status.setText)
        worker.completed.connect(self.completed)
        worker.failed.connect(lambda text: self.status.setText('操作未完成：' + text))
        worker.finished.connect(self.finished)
        worker.start()

    def set_busy(self, busy):
        for widget in (self.file_button, self.folder_button, self.help_button, self.close_button,
                       self.table, self.visible, self.organize):
            widget.setEnabled(not busy)
        self.import_button.setEnabled(not busy and bool(self.sessions))

    def completed(self, result):
        if self.worker.operation == 'import':
            self.imported = self.imported or result['inserted'] > 0
            self.status.setText(f"导入完成：新增 {result['inserted']} 条，跳过重复 {result['duplicates']} 条，"
                f"保留已有冲突记录 {result['conflicts']} 条。\n数据库备份：{result['backup']}"
                '\n可到“历史记录”查看，或在聊天中请她查找 DSH 旧对话。')
            return
        self.sessions = result['sessions']
        self.table.setRowCount(len(self.sessions))
        for row, session in enumerate(self.sessions):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Unchecked if session.subagent else Qt.CheckState.Checked)
            self.table.setItem(row, 0, check)
            first_date = next((message.at[:16].replace('T', ' ') for message in session.messages if message.at), '未知')
            for col, text in enumerate((('子会话 · ' if session.subagent else '') + session.title, str(len(session.messages)), first_date), 1):
                item = QTableWidgetItem(text)
                item.setToolTip(session.origin)
                self.table.setItem(row, col, item)
        self.table.setCurrentCell(0, 1)
        warnings = result['warnings']
        missing = sum(session.missing for session in self.sessions)
        undated = sum(session.undated for session in self.sessions)
        self.status.setText(f'识别 {len(self.sessions)} 个会话，{sum(len(s.messages) for s in self.sessions)} 条消息。'
            + (f' {missing} 个附件缺少原文件，保留文字占位。' if missing else '')
            + (f' {undated} 条消息缺少原时间，标为未知。' if undated else '')
            + (f' {len(warnings)} 个日志未读取：\n' + '\n'.join(warnings[:3]) if warnings else ''))

    def show_preview(self, row, *_args):
        if 0 <= row < len(self.sessions):
            session = self.sessions[row]
            self.preview.setPlainText('\n\n'.join(
                f"{'你' if m.role == 'user' else '助手'} · {m.at or '时间未知'}\n{m.text[:1500]}"
                + (f'\n（附带 {sum(a.data is not None for a in m.attachments)} 个原文件）' if m.attachments else '')
                for m in session.messages[:8]))

    def import_selected(self):
        selected = [session for row, session in enumerate(self.sessions)
                    if self.table.item(row, 0).checkState() == Qt.CheckState.Checked]
        if not selected:
            self.status.setText('请至少勾选一个会话。')
            return
        count = sum(len(session.messages) for session in selected)
        if FishDialog.question(self, '追加 DSH 聊天记录',
                f'将迁移 {len(selected)} 个会话，共 {count} 条消息。\n'
                '鲸伴现有聊天与设置保留；重复的原消息不会再次加入。\n'
                '导入前自动备份当前数据库到 backups 文件夹。\n\n'
                + ('后续记忆整理可能产生 API 费用。' if self.organize.isChecked() else '本次不为旧记录自动调用模型整理记忆。'),
                confirm_text='备份并追加'):
            self.start('import', selected, visible=self.visible.isChecked(), organize=self.organize.isChecked())

    def finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.set_busy(False)

    def accept(self):
        if self.worker is None:
            super().accept()

    def reject(self):
        if self.worker is None:
            super().reject()

    def closeEvent(self, event):
        if self.worker is not None:
            event.ignore()
        else:
            event.accept()
