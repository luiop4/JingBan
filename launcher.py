from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from pathlib import Path

from startup_support import (child_environment, diagnostic_path, install_startup_diagnostics,
                             spawn_child, startup_log)

# The copied rescue executable also performs the commit without opening a UI.
# Handle this before importing Qt or any replaceable interface module.
if '--apply-update' in sys.argv:
    from update_core import helper_main
    sys.argv.remove('--apply-update')
    helper_main()
    raise SystemExit(0)

if '--update-worker' in sys.argv:
    from update_core import worker_main
    worker_main(sys.argv[sys.argv.index('--update-worker')+1:])
    raise SystemExit(0)

_APP_ROOT = (Path(sys.executable).absolute().parent if getattr(sys, 'frozen', False)
             else Path(__file__).absolute().parent)
install_startup_diagnostics(_APP_ROOT)

# Register bundled Qt/runtime directories before loading Qt. Windows supplies
# its own ICU and API DLLs; keep these directory handles alive while running.
_DLL_SEARCH_HANDLES = []
if getattr(sys, "frozen", False):
    _bundle_dir = Path(sys._MEIPASS)
    for _dll_dir in (_bundle_dir, _bundle_dir / "PySide6", _bundle_dir / "shiboken6"):
        if _dll_dir.is_dir():
            _DLL_SEARCH_HANDLES.append(os.add_dll_directory(str(_dll_dir)))

from PySide6.QtCore import QTimer, Qt, QThread, Signal, Slot, QUrl, qInstallMessageHandler
from PySide6.QtGui import QPixmap, QIcon, QDesktopServices
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QDialog, QVBoxLayout,
                              QHBoxLayout, QLabel, QPlainTextEdit)

# Source launches pick up Designer edits before importing the generated UI.
if not getattr(sys, 'frozen', False):
    import PySide6
    _source_root = Path(__file__).resolve().parent
    _ui_source = _source_root / 'launcher.ui'
    _ui_generated = _source_root / 'ui_launcher.py'
    if _ui_source.is_file() and (not _ui_generated.is_file() or
            _ui_source.stat().st_mtime_ns > _ui_generated.stat().st_mtime_ns):
        _temporary_ui = _source_root / 'ui_launcher.generated.tmp'
        try:
            subprocess.run([str(Path(PySide6.__file__).parent / 'uic.exe'), '-g', 'python',
                            str(_ui_source), '-o', str(_temporary_ui)], check=True,
                           capture_output=True, timeout=20,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            _temporary_ui.replace(_ui_generated)
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError('启动界面更新失败，请检查 launcher.ui 的格式。') from error

from ui_launcher import Ui_LauncherWindow
from portable_runtime import prepare_portable_runtime
from update_core import (prepare_update, handoff_update, WorkspaceLock, recover,
                         UpdateError, UpdateBusy, bundled_helper_python, atomic_json)


class UpdateCheckWorker(QThread):
    progress = Signal(int, str)

    def __init__(self, root, parent=None, approved=None):
        super().__init__(parent)
        self.root = root
        self.outcome = None
        self.approved = approved
        self._progress_time = 0.0
        self._progress_value = -1

    def report_progress(self, value, text):
        now = time.monotonic()
        # File verification can produce hundreds of notifications in a fraction
        # of a second. The GUI only needs the latest phase at a bounded rate.
        if value != self._progress_value or now - self._progress_time >= 0.10:
            self._progress_time, self._progress_value = now, value
            startup_log(self.root, f'update {value}: {text}')
            self.progress.emit(value, text)

    def run(self):
        process = None
        folder = self.root / '.updates'
        identity = 'request-'+uuid.uuid4().hex
        result_file, progress_file, proposal_file = [folder/(identity+suffix) for suffix in ('.result.json', '.progress.json', '.proposal.json')]
        try:
            folder.mkdir(parents=True, exist_ok=True)
            python = bundled_helper_python(self.root)
            if python:
                command = [str(python), str(resource_path('update_core.py'))]
                frozen_helper = False
            elif getattr(sys, 'frozen', False):
                command, frozen_helper = [sys.executable, '--update-worker'], True
            else:
                command, frozen_helper = [sys.executable, str(self.root/'update_core.py')], False
            command += ['--mode', 'download' if self.approved else 'check', '--root', str(self.root),
                        '--result', str(result_file), '--progress', str(progress_file)]
            if self.approved:
                atomic_json(proposal_file, self.approved)
                command += ['--proposal', str(proposal_file)]
            log = diagnostic_path(self.root, 'update-worker.log')
            if log is None:
                raise OSError('无法写入更新检查日志。')
            with log.open('ab') as output:
                process = spawn_child(command, cwd=self.root, env=child_environment(), stdout=output,
                    stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                started = last_progress = time.monotonic()
                signature = None
                while process.poll() is None:
                    if self.isInterruptionRequested():
                        self._stop_child(process, frozen_helper)
                        self.outcome = {'state': 'offline', 'message': '本次更新已取消，继续启动本地软件。'}
                        return
                    try:
                        current = progress_file.read_text(encoding='utf-8')
                        if current != signature:
                            value = json.loads(current)
                            self.report_progress(int(value['value']), str(value['text']))
                            signature, last_progress = current, time.monotonic()
                    except (OSError, ValueError, KeyError, TypeError):
                        pass
                    now = time.monotonic()
                    if (not self.approved and now-started >= 6) or self.approved and now-last_progress >= 20:
                        self._stop_child(process, frozen_helper)
                        self.outcome = {'state': 'offline', 'message': '更新连接超时，继续启动本地软件。'}
                        return
                    time.sleep(0.1)
            self.outcome = json.loads(result_file.read_text(encoding='utf-8'))
        except Exception as error:
            startup_log(self.root, traceback.format_exc())
            self.outcome = {'state': 'error', 'message': str(error)[:400]}
        finally:
            if process is not None and process.poll() is None:
                self._stop_child(process, locals().get('frozen_helper', False))
            for path in (result_file, progress_file, proposal_file):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _stop_child(process, frozen_helper=False):
        if process.poll() is not None:
            return
        if frozen_helper and os.name == 'nt':
            try:
                subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                    capture_output=True, timeout=4, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except (OSError, subprocess.SubprocessError):
                pass
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


def resource_path(relative_path: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", _APP_ROOT))
    return bundle_root / relative_path


class UpdateNotice(QDialog):
    def __init__(self, result, parent):
        super().__init__(parent)
        self.setWindowTitle('鲸伴 · 更新内容')
        self.setMinimumSize(420, 300)
        self.resize(560, 450)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setStyleSheet('''QDialog { background:#F7F9FD; } QLabel { color:#344763; }
            QPlainTextEdit { background:white; border:1px solid #DAE3F1; border-radius:10px; padding:10px; }
            QPushButton { padding:9px 18px; border:1px solid #D6E0F0; border-radius:8px; background:white; }
            QPushButton#installUpdate { background:#5276C9; color:white; border-color:#5276C9; }''')
        box = QVBoxLayout(self)
        box.setContentsMargins(22, 20, 22, 18)
        title = QLabel(f'可更新至 v{result["version"]}', self)
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setStyleSheet('font-size:20px; font-weight:600;')
        box.addWidget(title)
        detail = QLabel(f'当前版本：v{result.get("local_version", "未知")} · 待更新或修复 {result.get("count", 0)} 个文件', self)
        detail.setTextFormat(Qt.TextFormat.PlainText)
        detail.setWordWrap(True)
        box.addWidget(detail)
        notes = QPlainTextEdit(self)
        notes.setReadOnly(True)
        notes.setPlainText(str(result.get('release_notes') or '此版本没有提供更新说明。'))
        box.addWidget(notes, 1)
        hint = QLabel('可以本次跳过。下次打开软件时仍会检查并提示。', self)
        hint.setWordWrap(True)
        box.addWidget(hint)
        row = QHBoxLayout()
        row.addStretch(1)
        skip = QPushButton('本次跳过', self)
        skip.setDefault(True)
        skip.clicked.connect(self.reject)
        install = QPushButton('立即更新', self)
        install.setObjectName('installUpdate')
        install.setAutoDefault(False)
        install.clicked.connect(self.accept)
        row.addWidget(skip)
        row.addWidget(install)
        box.addLayout(row)
        screen = parent.screen() or QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            self.resize(min(560, geometry.width()-32), min(450, geometry.height()-32))


class LauncherWindow(QMainWindow, Ui_LauncherWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setupUi(self)
        self.resize(760, 450)
        self.setWindowIcon(QIcon(str(resource_path("assets/jingban-icon.ico"))))
        self.root = _APP_ROOT.resolve()
        self.python = self.root / ".app-venv" / "Scripts" / "python.exe"
        self.main_script = self.root / "main.py"
        self.ready_file = Path(tempfile.gettempdir()) / f"aichat-ready-{uuid.uuid4().hex}.txt"
        self.app_process: subprocess.Popen | None = None
        self.handed_off = False
        self.update_worker = None
        self._close_pending = False
        self._failed = False
        self._local_starting = False
        self.update_handoff = None
        self.app_log_path = None
        self._startup_time = 0.0


        # 无边框启动：隐藏系统标题栏，并支持按住窗口拖动。
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self._drag_offset = None
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setStyleSheet("""
            QWidget { font-family: 'Microsoft YaHei UI'; font-size: 12px; color: #40516b; }
            QMainWindow { background: #f6f8fc; }
            QFrame#panel { background: #ffffff; border: 1px solid #e1e7f0; border-radius: 16px; }
            QLabel { background: transparent; border: none; }
            QLabel#titleLabel { color: #2c3d58; font-size: 32px; font-weight: 700; }
            QLabel#brandLabel { color: #6f8baa; font-size: 10px; }
            QLabel#subtitleLabel { color: #526a8d; font-size: 15px; }
            QLabel#descriptionLabel { color: #8492a6; font-size: 11px; }
            QLabel#schemaLabel { font-size: 12px;
                background: #f5f8fc; border: 1px solid #e7edf5; border-radius: 8px; padding: 12px; }
            QLabel#featuresLabel { color: #5f7898; font-size: 11px; padding: 4px 0; }
            QLabel#engineLabel { color: #93a1b3; font-size: 10px; }
            QLabel#statusLabel { color: #7d8ba0; font-size: 11px; }
            QProgressBar { height: 5px; border: none; border-radius: 2px; background: #edf1f7; }
            QProgressBar::chunk { background: #8aa6c7; border-radius: 2px; }
            QPushButton#closeButton { color: #ffffff; background: #8aa6c7; border: none;
                border-radius: 6px; padding: 6px 16px; }
        """)
        self.authorLabel.setText("by 雪落时")
        self.authorLabel.setStyleSheet("color: #8a97b8; font-size: 12px;")
        self.authorAvatarLabel.setStyleSheet("background: transparent; border: 0;")
        self.authorAvatarLabel.setPixmap(
            QPixmap(str(resource_path("author_avatar.png"))).scaled(
                self.authorAvatarLabel.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        if self.authorAvatarLabel.pixmap().isNull():
            self.authorAvatarLabel.hide()
        self.closeButton.clicked.connect(self.close)
        self.logsButton = QPushButton('打开诊断日志', self.panel)
        self.logsButton.setVisible(False)
        self.infoLayout.addWidget(self.logsButton)
        self.logsButton.clicked.connect(self._open_diagnostics)
        self.cancelUpdateButton = QPushButton('取消更新并启动软件', self.panel)
        self.cancelUpdateButton.hide()
        self.infoLayout.addWidget(self.cancelUpdateButton)
        self.cancelUpdateButton.clicked.connect(self._cancel_download)
        self.statusLabel.setWordWrap(True)
        self.characterLabel.setStyleSheet("background: transparent; border: 0;")
        self.characterLabel.setPixmap(
            QPixmap(str(resource_path("assets/mascot_v2.png"))).scaled(
                self.characterLabel.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._center_window()

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(180)
        self.poll_timer.timeout.connect(self._check_startup)
        self.helper_timer = QTimer(self)
        self.helper_timer.setInterval(150)
        self.helper_timer.timeout.connect(self._check_update_helper)
        QTimer.singleShot(180, self._begin_update_check)

    @Slot()
    def _begin_update_check(self):
        if '--skip-update-once' in sys.argv:
            try:
                with WorkspaceLock(self.root):
                    recover(self.root)
                previous = json.loads((self.root / '.updates/last_result.json').read_text(encoding='utf-8'))
                if previous.get('ok') is False:
                    self._set_status(13, '上次更新未完成，保留本地程序：' + str(previous.get('message', ''))[:100])
                    QTimer.singleShot(850, self._check_project_files)
                    return
            except (OSError, ValueError):
                pass
            except UpdateError as error:
                self._show_error('更新恢复未完成：' + str(error))
                return
            self._set_status(13, '更新交接已结束，继续启动软件…')
            QTimer.singleShot(100, self._check_project_files)
            return
        self._set_status(1, '正在检查更新与 OneBot 组件完整性…')
        self._run_update_worker()

    def _run_update_worker(self, approved=None):
        self.update_worker = UpdateCheckWorker(self.root, self, approved=approved)
        self.update_worker.progress.connect(self._set_status, Qt.ConnectionType.QueuedConnection)
        self.update_worker.finished.connect(self._on_update_worker_finished, Qt.ConnectionType.QueuedConnection)
        self.update_worker.start()

    def _cancel_download(self):
        if self.update_worker is not None:
            self.cancelUpdateButton.setEnabled(False)
            self._set_status(13, '正在取消本次下载，随后启动本地软件…')
            self.update_worker.requestInterruption()

    @Slot()
    def _on_update_worker_finished(self):
        worker = self.update_worker
        if worker is None:
            return
        result = worker.outcome
        self.update_worker = None
        self.cancelUpdateButton.hide()
        self.cancelUpdateButton.setEnabled(True)
        worker.deleteLater()
        if self._close_pending:
            self.close()
            return
        # Only hand off or advance after run() has ended; no queued result may
        # close the window while its update thread is still being used.
        self._on_update_checked(result or {'state': 'error', 'message': '更新检查未返回结果。'})

    def _on_update_checked(self, result):
        if self._close_pending:
            return
        if result['state'] == 'ready':
            try:
                self._set_status(13, f'已准备 {result["count"]} 个文件，正在安装并重新启动…')
                self.update_handoff = handoff_update(self.root, result['job_id'])
                self._helper_start_time = time.monotonic()
                self.helper_timer.start()
            except (OSError, UpdateError) as error:
                startup_log(self.root, traceback.format_exc())
                self._show_error('更新暂未安装：' + str(error))
            return
        if (self.root / '.updates' / 'transaction.json').exists():
            self._show_error('更新恢复未完成：' + result.get('message', '请重新启动修复。'))
            return
        if result['state'] == 'available':
            self._set_status(6, '检测到更新，请查看更新内容…')
            dialog = UpdateNotice(result, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.cancelUpdateButton.show()
                self._set_status(6, '正在准备你选择的更新…')
                self._run_update_worker(approved=result['envelope'])
            else:
                self._set_status(13, '本次跳过更新，继续启动软件…')
                QTimer.singleShot(100, self._check_project_files)
            return
        if result['state'] == 'error':
            startup_log(self.root, '更新未替换本地文件：' + result.get('message', ''))
            self._set_status(13, '更新未完成，保留原文件并尝试本地启动…')
            QTimer.singleShot(100, self._check_project_files)
            return
        if result['state'] in {'offline', 'busy'}:
            startup_log(self.root, result.get('message', ''))
            self._set_status(13, result.get('message', '继续使用本地程序。'))
            QTimer.singleShot(100, self._check_project_files)
        else:
            QTimer.singleShot(100, self._check_project_files)

    @Slot()
    def _check_update_helper(self):
        handoff = self.update_handoff
        if handoff is None or self._close_pending:
            return
        process = handoff['process']
        try:
            if process.poll() is not None:
                raise UpdateError(f'更新助手提前退出（{process.returncode}），请打开诊断日志。')
            if handoff['ready'].is_file():
                acknowledgement = json.loads(handoff['ready'].read_text(encoding='utf-8'))
                if (acknowledgement.get('job_id') != handoff['job_id']
                        or acknowledgement.get('spawn_pid', acknowledgement.get('pid')) != process.pid):
                    raise UpdateError('更新助手启动确认无效。')
                self.helper_timer.stop()
                self.handed_off = True
                startup_log(self.root, '更新助手已确认启动，正在退出启动器。')
                self.close()
            elif time.monotonic() - self._helper_start_time > 25:
                raise UpdateError('更新助手未能完成启动，原程序尚未替换，请打开诊断日志。')
        except (OSError, ValueError, UpdateError) as error:
            self._cancel_update_handoff()
            self._show_error(str(error))

    def _cancel_update_handoff(self):
        self.helper_timer.stop()
        if self.update_handoff is not None and not self.handed_off:
            try:
                self.update_handoff['cancel'].write_text('cancelled', encoding='utf-8')
            except OSError as error:
                startup_log(self.root, '未能写入更新取消标记：' + str(error))

    @Slot()
    def _open_diagnostics(self):
        path = diagnostic_path(self.root, 'launcher.log')
        if path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def _center_window(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is not None:
            geometry = screen.availableGeometry()
            self.setMinimumSize(min(720, geometry.width()-24), min(440, geometry.height()-24))
            self.resize(min(self.width(), geometry.width()-24), min(self.height(), geometry.height()-24))
            self.move(
                geometry.center().x() - self.width() // 2,
                geometry.center().y() - self.height() // 2,
            )


    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)
    @Slot(int, str)
    def _set_status(self, value: int, text: str) -> None:
        if self._close_pending or self._failed:
            return
        self.progressBar.setValue(value)
        self.statusLabel.setText(text)
        # app.exec() already dispatches paint and queued progress events. Calling
        # processEvents here re-enters this slot and can overflow the native stack.

    def _check_project_files(self) -> None:
        if self._close_pending or self._failed or self._local_starting:
            return
        self._local_starting = True
        self._set_status(14, "正在适配当前目录的 Python 运行环境…")
        try:
            for warning in prepare_portable_runtime(self.root):
                print('Local voice: ' + warning)
        except (OSError, RuntimeError) as error:
            self._show_error("运行环境准备失败：" + str(error))
            return
        missing = [str(path.name) for path in (self.python, self.main_script) if not path.is_file()]
        if missing:
            self._show_error("缺少 " + "、".join(missing) + "。请先运行 setup_app.bat。")
            return
        QTimer.singleShot(260, self._load_appearance_settings)

    def _load_appearance_settings(self) -> None:
        self._set_status(34, "正在加载外观与角色设置…")
        self._read_optional_json("app_settings.json")
        QTimer.singleShot(260, self._load_service_settings)

    def _load_service_settings(self) -> None:
        self._set_status(54, "正在读取模型、语音和 QQ 配置…")
        self._read_optional_json("config.json")
        QTimer.singleShot(260, self._prepare_local_data)

    def _prepare_local_data(self) -> None:
        self._set_status(74, "正在准备本地聊天记录与记忆…")
        QTimer.singleShot(220, self._start_chat_application)

    def _read_optional_json(self, filename: str) -> None:
        path = self.root / filename
        if not path.exists():
            return
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # The main application applies its existing fallback behavior for invalid files.
            return

    def _start_chat_application(self) -> None:
        if self._close_pending or self._failed:
            return
        try:
            self.ready_file.unlink(missing_ok=True)
            environment = child_environment()
            environment["AICHAT_STARTUP_READY_FILE"] = str(self.ready_file)
            self._set_status(88, "正在启动聊天窗口…")
            self.app_log_path = diagnostic_path(self.root, 'chat-startup.log')
            if self.app_log_path is None:
                raise OSError('无法创建聊天启动日志，请检查程序目录写入权限。')
            with self.app_log_path.open('wb') as output:
                self.app_process = spawn_child(
                    [str(self.python), '-X', 'faulthandler', '-u', str(self.main_script)],
                    cwd=self.root, env=environment, stdout=output, stderr=subprocess.STDOUT,
                    creationflags=(getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                        if getattr(sys, 'frozen', False) or os.environ.get('AICHAT_UPDATE_RESTART') else 0),
                )
            self._startup_time = time.monotonic()
            startup_log(self.root, f'聊天进程已创建：pid={self.app_process.pid}; log={self.app_log_path}')
            self.poll_timer.start()
        except OSError as error:
            self._show_error(f"聊天程序启动失败：{error}")

    def _check_startup(self) -> None:
        if self.app_process is not None and self.app_process.poll() is not None:
            self._show_error(f'聊天程序提前退出（{self.app_process.returncode}）。请打开诊断日志查看 chat-startup.log。')
            return
        if self.ready_file.is_file():
            self.poll_timer.stop()
            self.handed_off = True
            self._set_status(100, "大肥鱼已经准备好了。")
            self.ready_file.unlink(missing_ok=True)
            QTimer.singleShot(450, self.close)
            return
        if self._startup_time and time.monotonic() - self._startup_time > 90:
            self._show_error('聊天窗口尚未就绪，请打开诊断日志查看 chat-startup.log。')

    def _show_error(self, message: str) -> None:
        self._failed = True
        self.poll_timer.stop()
        self.helper_timer.stop()
        startup_log(self.root, 'ERROR: ' + message)
        self.statusLabel.setStyleSheet("color: #a3452b; font-size: 12px;")
        self.statusLabel.setText(message)
        self.progressBar.setValue(0)
        self.closeButton.setVisible(True)
        self.logsButton.setVisible(True)

    def closeEvent(self, event) -> None:
        if self.update_worker is not None and self.update_worker.isRunning():
            self._close_pending = True
            self.update_worker.requestInterruption()
            self.statusLabel.setText('正在结束更新检查…')
            event.ignore()
            return
        self.poll_timer.stop()
        self._cancel_update_handoff()
        self.ready_file.unlink(missing_ok=True)
        if not self.handed_off and self.app_process is not None and self.app_process.poll() is None:
            self.app_process.terminate()
        super().closeEvent(event)


def main() -> None:
    qInstallMessageHandler(lambda kind, context, message: startup_log(_APP_ROOT, 'Qt: ' + message))
    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Jingban.Companion')
    app = QApplication(sys.argv)
    app.setApplicationName('鲸伴')
    app.setWindowIcon(QIcon(str(resource_path('assets/jingban-icon.ico'))))
    app.setStyle("Fusion")
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
