"""迁移包：数据库用 SQLite backup 一致性快照，文件操作在后台完成。"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox, QApplication
from dialogs import FishDialog


def export_backup(root: Path, destination: Path) -> None:
    # 避免把正在生成的 ZIP 或历史备份再次打进自身。
    destination = destination.resolve()
    if destination.is_relative_to(root / 'data') or destination.is_relative_to(root / 'assets'):
        raise ValueError('请将备份保存到 data、assets 文件夹以外的位置。')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tempfile.TemporaryDirectory(prefix='chat-backup-') as temp, zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            snapshot = Path(temp) / 'snapshot.sqlite3'
            for folder in ('data', 'assets'):
                for source in sorted((root / folder).rglob('*')):
                    if folder == 'data' and source.relative_to(root / folder).parts[0].casefold() in ('onebot', 'dsh', 'bilibili-browser', 'web-browser'):
                        continue
                    if source.is_symlink() or not source.is_file():
                        continue
                    if not source.resolve().is_relative_to(root):
                        continue
                    if source.name.endswith(('-wal', '-shm', '-journal')):
                        continue
                    arcname = source.relative_to(root).as_posix()
                    if source.suffix.lower() in ('.db', '.sqlite', '.sqlite3'):
                        snapshot.unlink(missing_ok=True)
                        src = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
                        dst = sqlite3.connect(snapshot)
                        try:
                            src.backup(dst)
                        finally:
                            src.close()
                            dst.close()
                        archive.write(snapshot, arcname)
                        if source.name == 'chat_history.sqlite3':
                            connection = sqlite3.connect(snapshot)
                            connection.row_factory = sqlite3.Row
                            try:
                                memories = [dict(row) for row in connection.execute('SELECT * FROM memories')]
                            finally:
                                connection.close()
                            archive.writestr('memories.json', json.dumps(memories, ensure_ascii=False, indent=2))
                    else:
                        archive.write(source, arcname)
            if (root / 'app_settings.json').is_file():
                archive.write(root / 'app_settings.json', 'app_settings.json')
            archive.writestr('manifest.json', json.dumps({
                'format': 'AIChatMemory', 'version': 1, 'source_root': str(root),
                'created_at': datetime.now().astimezone().isoformat(),
                'credentials_included': False,
            }, ensure_ascii=False, indent=2))
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def import_backup(root: Path, source: Path) -> Path:
    with tempfile.TemporaryDirectory(prefix='.restore-', dir=root) as temp:
        staging = Path(temp)
        with zipfile.ZipFile(source) as archive:
            if archive.getinfo('manifest.json').file_size > 65536:
                raise ValueError('备份说明文件异常。')
            manifest = json.loads(archive.read('manifest.json'))
            if manifest.get('format') != 'AIChatMemory' or manifest.get('version') != 1:
                raise ValueError('这不是支持的聊天备份文件。')
            entries = archive.infolist()
            if len(entries) > 100000 or sum(x.file_size for x in entries) > 20 * 1024**3:
                raise ValueError('备份包过大（最多 20 GB / 100000 个文件）。')
            seen = set()
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename
                        or ':' in entry.filename or not path.parts):
                    raise ValueError('备份包含不安全的路径。')
                key = str(path).casefold()
                if key in seen:
                    raise ValueError('备份包含重复路径。')
                seen.add(key)
                if path.parts[0] not in ('data', 'assets') and str(path) not in ('manifest.json', 'memories.json', 'app_settings.json'):
                    raise ValueError('备份包含无法识别的内容。')
                if str(path).endswith(('-wal', '-shm', '-journal')):
                    raise ValueError('备份不应包含数据库临时文件。')
                # QQ session state belongs to this device and never comes from a chat backup.
                if len(path.parts) > 1 and path.parts[0] == 'data' and path.parts[1].casefold() in ('onebot', 'dsh', 'bilibili-browser', 'web-browser'):
                    continue
                target = staging.joinpath(*path.parts)
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as reader, target.open('wb') as writer:
                        shutil.copyfileobj(reader, writer)
        database = staging / 'data' / 'chat_history.sqlite3'
        if not database.is_file():
            raise ValueError('备份中缺少聊天数据库。')
        connection = sqlite3.connect(database)
        try:
            if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('备份数据库损坏，未导入。')
            tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'messages', 'memories', 'memory_sources', 'audio_files', 'message_attachments'} <= tables:
                raise ValueError('数据库结构不完整，未导入。')
            if 'owner_notifications' in tables:
                connection.execute("UPDATE owner_notifications SET status='cancelled' WHERE status='queued'")
                connection.execute("UPDATE owner_notifications SET status='unknown' WHERE status='sending'")
            if 'qq_proactive' in tables:
                connection.execute("UPDATE qq_proactive SET status='unknown' WHERE status='pending'")
            if 'agency_journal' in tables:
                connection.execute("UPDATE agency_journal SET status='interrupted' WHERE status='running'")
            old_root = Path(manifest['source_root'])
            for table, column in [('audio_files', 'file_path'), ('message_attachments', 'local_path')]:
                for rowid, value in connection.execute(f'SELECT rowid, {column} FROM {table}').fetchall():
                    if not value:
                        continue
                    path = Path(value)
                    if path.is_absolute():
                        try:
                            relative = path.relative_to(old_root)
                        except ValueError:
                            continue
                        if relative.parts and relative.parts[0] == 'data' and '..' not in relative.parts:
                            connection.execute(f'UPDATE {table} SET {column}=? WHERE rowid=?', (str(root / relative), rowid))
            connection.commit()
        finally:
            connection.close()
        settings = staging / 'app_settings.json'
        if settings.exists():
            value = json.loads(settings.read_text(encoding='utf-8'))
            if not isinstance(value, dict):
                raise ValueError('外观配置格式不正确。')
        for service in ('onebot', 'dsh', 'bilibili-browser', 'web-browser'):
            local_state = root / 'data' / service
            if local_state.exists():
                if local_state.is_symlink() or not local_state.resolve().is_relative_to(root.resolve()):
                    raise ValueError(f'本机 {service} 数据目录位置异常，未导入。')
                shutil.copytree(local_state, staging / 'data' / service, symlinks=True)
        rollback = root / 'backups' / ('before-import-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6] + '.zip')
        export_backup(root, rollback)
        moved, installed = [], []
        try:
            for name in ('data', 'assets', 'app_settings.json'):
                incoming, target = staging / name, root / name
                if not incoming.exists():
                    continue
                previous = staging / ('previous-' + name)
                if target.exists():
                    os.replace(target, previous)
                    moved.append((previous, target))
                os.replace(incoming, target)
                installed.append(target)
        except Exception:
            for target in reversed(installed):
                os.replace(target, staging / ('failed-' + target.name))
            for previous, target in reversed(moved):
                os.replace(previous, target)
            raise
        return rollback


class TransferWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, root, path, restore, parent=None):
        super().__init__(parent)
        self.root, self.path, self.restore = Path(root).resolve(), Path(path), restore

    def run(self):
        try:
            if self.restore:
                result = str(import_backup(self.root, self.path))
            else:
                export_backup(self.root, self.path)
                result = str(self.path)
            self.completed.emit(result)
        except Exception as error:
            self.failed.emit(str(error))


class DataTransferDialog(QDialog):
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root, self.worker = Path(root), None
        self.restored = False
        self.dsh_imported = False
        self.result_path = ''
        self.setWindowTitle('会话与记忆迁移')
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        description = QLabel('导出包含所有聊天数据库、长期记忆、附件、历史语音及头像外观。\n'
                             '另外附带 memories.json，方便单独查看记忆。\n'
                             '不包含 API 密钥、QQ 登录配置与令牌、DSH 插件、Python 环境和 TTS 模型。\n\n'
                             '“导入备份”会替换当前数据，自动保存恢复备份，成功后需重启。\n'
                             '“从 DSH 迁移”只追加旧聊天，支持预览和去重，不替换当前数据。')
        description.setWordWrap(True)
        layout.addWidget(description)
        self.export_button = QPushButton('导出完整备份…')
        self.import_button = QPushButton('导入备份…')
        self.dsh_button = QPushButton('从 DSH 迁移聊天记录…')
        self.status = QLabel('迁移到另一台电脑：安装应用后，在这里导入 ZIP 备份。')
        self.status.setWordWrap(True)
        self.close_button = QPushButton('关闭')
        for widget in (self.export_button, self.import_button, self.dsh_button, self.status, self.close_button):
            layout.addWidget(widget)
        self.export_button.clicked.connect(self.export)
        self.import_button.clicked.connect(self.restore)
        self.dsh_button.clicked.connect(self.import_dsh)
        self.close_button.clicked.connect(self.accept)

    def import_dsh(self):
        from dsh_history import DshHistoryDialog
        dialog = DshHistoryDialog(self.root, self)
        dialog.exec()
        self.dsh_imported = self.dsh_imported or dialog.imported
        if dialog.imported:
            self.status.setText('DSH 记录已追加，可在“历史记录”查看，也可请 AI 检索旧对话；当前聊天继续保留。')

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, '导出会话与记忆', str(Path.home() / ('AIChatMemory-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.zip')), 'ZIP 备份 (*.zip)')
        if path:
            self.start(path if path.lower().endswith('.zip') else path + '.zip', False)

    def restore(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择聊天备份', str(Path.home()), 'ZIP 备份 (*.zip)')
        if not path:
            return
        if FishDialog.question(self, '替换当前会话与记忆', '导入会替换当前聊天记录、记忆、附件与历史语音。\n'
                                '当前内容会先自动备份到项目的 backups 文件夹。\nAPI 密钥保留本机设置。\n\n确认导入？',
                                confirm_text='备份并导入', danger=True):
            self.start(path, True)

    def start(self, path, restore):
        for button in (self.export_button, self.import_button, self.dsh_button, self.close_button):
            button.setEnabled(False)
        self.status.setText('正在导入，请勿关闭程序…' if restore else '正在打包数据，请稍候…')
        self.worker = TransferWorker(self.root, path, restore, self)
        self.worker.completed.connect(self.done_transfer)
        self.worker.failed.connect(self.failed_transfer)
        self.worker.finished.connect(self.finished_transfer)
        self.worker.start()

    @Slot(str)
    def done_transfer(self, path):
        self.restored = self.worker.restore
        self.result_path = path
        self.status.setText(('导入完成，原数据备份：' if self.restored else '备份已保存：') + path)

    @Slot(str)
    def failed_transfer(self, message):
        self.status.setText('操作未完成：' + message)

    @Slot()
    def finished_transfer(self):
        self.worker.deleteLater()
        self.worker = None
        if self.restored:
            FishDialog.information(self, '导入完成', '数据已导入。软件即将退出，请重新打开。\n原数据备份：\n' + self.result_path, 'success')
            self.accept()
            QApplication.instance().quit()
            return
        for button in (self.export_button, self.import_button, self.dsh_button, self.close_button):
            button.setEnabled(True)

    def reject(self):
        if self.worker is None:
            super().reject()

    def closeEvent(self, event):
        if self.worker is not None:
            event.ignore()
        else:
            event.accept()
