"""Reset only managed conversation data, without deleting the live SQLite file."""
from pathlib import Path
import shutil
import uuid
import os

from PySide6.QtCore import QThread
from update_core import WorkspaceLock, running_clients


class DataResetWorker(QThread):
    def __init__(self, root, database, parent=None):
        super().__init__(parent)
        self.root = Path(root).resolve()
        self.database = database
        self.result = None
        self.error = ''

    def run(self):
        try:
            # RuntimeLease uses the same lock when opening another chat window.
            with WorkspaceLock(self.root):
                if any(pid != os.getpid() for pid in running_clients(self.root)):
                    raise ValueError('同一目录还有其他聊天窗口运行，请先关闭其他窗口再清空。')
                self._clear()
        except Exception as error:
            self.error = str(error)

    def _clear(self):
        try:
            data = self.root / 'data'
            if data.is_symlink() or data.resolve() != data or not data.is_dir():
                raise ValueError('数据目录不是项目内的普通目录，已停止清空。')
            if self.database.database_path.resolve() != data / 'chat_history.sqlite3':
                raise ValueError('数据库位置与清空目录不一致，已停止清空。')
            sources = []
            for name in ('attachments', 'tts_audio', 'web_images'):
                source = data / name
                if not source.exists() and not source.is_symlink():
                    continue
                if source.is_symlink() or source.resolve() != source or not source.is_dir():
                    raise ValueError(f'缓存目录 {name} 指向其他位置，已停止清空。')
                sources.append(source)
            visit_files = [data / name for name in ('bilibili-visits.json', 'bilibili-session.json', 'bilibili-actions.json')]
            for visits in visit_files:
                if visits.is_symlink() or visits.exists() and (visits.resolve().parent != data or not visits.is_file()):
                    raise ValueError('B站漫游记录位置异常，已停止清空。')
            # Commit first: failure leaves all files in place. A crash can then
            # leave unused caches, but never old records pointing at moved files.
            counts = self.database.clear_all_conversation_data()
            self.result = {**counts, 'warnings': []}
            for visits in visit_files:
                try:
                    visits.unlink(missing_ok=True)
                except OSError:
                    self.result['warnings'].append('B站漫游记录未能删除，退出程序后可手动清理 ' + str(visits.name))
            for source in sources:
                target = source
                try:
                    if source.resolve().parent != data or source.is_symlink():
                        raise ValueError('缓存目录位置异常。')
                    target = data / ('.reset-' + uuid.uuid4().hex)
                    source.rename(target)
                    # Resolve and check the actual target before recursive deletion.
                    if target.resolve().parent != data or target.is_symlink():
                        raise ValueError('临时清理目录位置异常。')
                    shutil.rmtree(target)
                except (OSError, ValueError) as error:
                    residual = target if target.exists() else source
                    self.result['warnings'].append(f'部分缓存仍在 {residual}，退出程序后可清理：{error}')
        except Exception as error:
            if self.result is None:
                self.error = str(error)
            else:
                self.result['warnings'].append('聊天与记忆已清空，缓存清理未完成：' + str(error))
