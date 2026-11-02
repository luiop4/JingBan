"""引用卡、表情显示和本地表情库窗口。"""
from pathlib import Path
import shutil
import uuid
import json

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QMovie, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QListWidget, QFileDialog, QInputDialog)
from dialogs import FishDialog


def image_widget(path, parent, size=180):
    label = QLabel(parent)
    label.setAlignment(Qt.AlignmentFlag.AlignLeft)
    if path.suffix.lower() == '.gif':
        movie = QMovie(str(path), parent=label)
        movie.jumpToFrame(0)
        dimensions = movie.currentPixmap().size()
        if not dimensions.isEmpty():
            movie.setScaledSize(dimensions.scaled(QSize(size, size), Qt.AspectRatioMode.KeepAspectRatio))
        label.setMovie(movie)
        label.animation = movie
        movie.start()
    else:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            label.setText('图片暂不可用')
        else:
            label.setPixmap(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    return label


def render_extras(window, body, message_id, root, extras=None):
    for widget in getattr(body, 'extra_widgets', []):
        body.bubble_layout.removeWidget(widget)
        widget.deleteLater()
    body.extra_widgets = []
    body.set_original_reasoning_visible(window.settings.get('interaction', {}).get('mode', 'normal') == 'work')
    frame_count = 0
    records = window.database.get_extras(message_id) if extras is None else extras
    for extra in records:
        if extra['kind'] == 'character_aside':
            body.set_character_aside(extra['target'])
        elif extra['kind'] == 'character_aside_status':
            body.set_character_aside(extra['target'], state='unavailable')
    flow_message = any(extra['kind'] == 'chat_flow' for extra in records)
    for extra in records:
        if extra['kind'] in {'chat_flow', 'request_origin', 'internal_activity', 'qq_qzone', 'dsh_import', 'archive_only',
                            'character_aside', 'character_aside_status'}:
            continue
        if extra['kind'] == 'proactive' and flow_message:
            continue
        if extra['kind'] == 'reasoning':
            body.set_reasoning(extra['target'])
            continue
        card = QLabel('', body.parentWidget())
        if extra['kind'] == 'quote':
            original = window.database.get_message(int(extra['target']))
            card = QPushButton()
            card.setObjectName('messageActionButton')
            card.setStyleSheet('text-align: left; padding: 10px; border-left: 3px solid #8b9dcc; background: #f0f3f8; border-radius: 6px;')
            if original:
                name = window.app_settings.get('user' if original['role'] == 'user' else 'assistant', {}).get('name', original['role'])
                preview = original['content'].replace('\n', ' ')[:32]
                if len(original['content']) > 32:
                    preview += '…'
                attachments = window.database.attachments_for_message(original['id'])
                card.setText(f"引用 · {name} · {original['created_at'][:10]}\n{preview or '附件消息'}")
                card.setToolTip('点击定位并查看完整原消息\n' + original['content'][:1000])
                for attachment in attachments:
                    path = root / attachment['local_path']
                    if attachment['kind'] == 'image' and path.is_file():
                        from PySide6.QtGui import QIcon
                        card.setIcon(QIcon(str(path)))
                        card.setIconSize(QSize(64, 64))
                        break
                card.clicked.connect(lambda checked=False, target=original['id']: show_original(window, target, root))
            else:
                card.setText('引用的消息已删除')
                card.setEnabled(False)
        elif extra['kind'] == 'voice':
            card = QLabel('语音回复 · 合成后可回放')
            card.setObjectName('messageAttachmentChip')
        elif extra['kind'] == 'proactive':
            card.setText('鲸鱼心跳')
            card.setObjectName('messageAttachmentChip')
        elif extra['kind'] == 'qq_delivery':
            if extra['target'] == 'sent':
                card.deleteLater()
                continue
            card.setText({'pending': 'QQ发送中', 'unknown': 'QQ发送结果未确认', 'failed': 'QQ发送失败'}.get(extra['target'], 'QQ发送结果未确认'))
            card.setObjectName('messageAttachmentChip')
        elif extra['kind'] == 'tool_receipts':
            try:
                receipts = json.loads(extra['target'])
                if not isinstance(receipts, list):
                    continue
                rows = [r for r in receipts if isinstance(r, dict)]
                if not rows or flow_message and all(r.get('tool') in {'chat_message', 'read_self_state', 'update_self_state'} for r in rows):
                    card.deleteLater()
                    continue
            except (ValueError, TypeError):
                continue
            card.deleteLater()
            card = QPushButton('查看本轮工具依据', body.parentWidget())
            card.setObjectName('messageActionButton')
            def show_receipts(checked=False, records=rows):
                from PySide6.QtWidgets import QPlainTextEdit
                dialog = QDialog(window)
                dialog.setWindowTitle('本轮工具依据')
                dialog.resize(580, 420)
                box = QVBoxLayout(dialog)
                label = QLabel('成功表示工具返回成功；命令退出码不保证任务结果。历史回执不能证明当前状态。', dialog)
                label.setWordWrap(True)
                box.addWidget(label)
                text = QPlainTextEdit(dialog)
                text.setReadOnly(True)
                text.setPlainText('\n\n'.join(
                    f"{r.get('observed_at', '')}  {r.get('tool', '')}  {r.get('status', '')}\n"
                    f"范围：{r.get('scope', '')}  目标：{r.get('target', '')}" +
                    ('\n事实：' + json.dumps(r['facts'], ensure_ascii=False, indent=2) if r.get('facts') else '')
                    for r in records))
                box.addWidget(text)
                close = QPushButton('关闭', dialog)
                close.clicked.connect(dialog.accept)
                box.addWidget(close)
                dialog.exec()
                dialog.deleteLater()
            card.clicked.connect(show_receipts)
        elif extra['kind'] == 'sticker':
            path = root / 'assets' / 'stickers' / Path(extra['target']).name
            card = image_widget(path, body.parentWidget()) if path.is_file() else QLabel('表情已移除')
            card.setToolTip(Path(extra['target']).stem)
        elif extra['kind'] == 'image':
            from PySide6.QtWidgets import QWidget
            card.deleteLater()
            try:
                info = json.loads(extra['target'])
                path = (root / info['path']).resolve()
                if not path.is_relative_to((root / 'data' / 'attachments').resolve()) or not path.is_file():
                    card = QLabel('图片文件已移除', body.parentWidget())
                else:
                    card = QWidget(body.parentWidget())
                    box = QVBoxLayout(card)
                    box.setContentsMargins(0, 4, 0, 4)
                    box.addWidget(image_widget(path, card, 420))
                    open_image = QPushButton(str(info.get('title') or '图片') + ' · 查看原图', card)
                    open_image.clicked.connect(lambda checked=False, p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(p))))
                    box.addWidget(open_image)
                    caption = QLabel(info.get('label', '图片'), card)
                    caption.setTextFormat(Qt.TextFormat.PlainText)
                    box.addWidget(caption)
                    source = str(info.get('source_url', ''))
                    if source.startswith(('https://', 'http://')):
                        button = QPushButton('打开图片来源', card)
                        button.clicked.connect(lambda checked=False, u=source: QDesktopServices.openUrl(QUrl(u)))
                        box.addWidget(button)
            except (ValueError, TypeError, KeyError):
                continue
        elif extra['kind'] == 'video_frame':
            from PySide6.QtWidgets import QWidget
            card.deleteLater()
            try:
                info = json.loads(extra['target'])
                path = (root / info['path']).resolve()
                if not path.is_relative_to((root / 'data' / 'attachments').resolve()) or not path.is_file():
                    continue
                seconds = float(info['time_seconds'])
            except (ValueError, TypeError, KeyError):
                continue
            card = QWidget(body.parentWidget())
            layout = QVBoxLayout(card)
            layout.setContentsMargins(0, 4, 0, 4)
            layout.addWidget(image_widget(path, card, 420))
            caption = QPushButton(f"{info.get('title', '视频')} · {int(seconds)//60:02d}:{int(seconds)%60:02d}  查看画面", card)
            caption.clicked.connect(lambda checked=False, p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(p))))
            layout.addWidget(caption)
            if info.get('observation_kind') == 'current_browser_tab':
                note = QLabel('本轮浏览器标签读取 · 全片抽样画面，非当前播放位置', card)
                note.setWordWrap(True)
                layout.addWidget(note)
        if extra['kind'] in {'video_frame', 'image'}:
            body.bubble_layout.insertWidget(1 + frame_count, card)
            frame_count += 1
        else:
            body.bubble_layout.insertWidget(2 + len(body.extra_widgets), card)
        body.extra_widgets.append(card)


def show_original(window, message_id, root):
    message = window.database.get_message(message_id)
    if not message:
        FishDialog.information(window, '消息已删除', '原消息已不在数据库中。')
        return
    row = window.message_rows.get(message_id)
    if row:
        window.chatScroll.ensureWidgetVisible(row)
    dialog = QDialog(window)
    dialog.setWindowTitle('原消息')
    dialog.resize(520, 420)
    from PySide6.QtWidgets import QScrollArea, QWidget
    outer = QVBoxLayout(dialog)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    container = QWidget()
    layout = QVBoxLayout(container)
    from message_body import MessageBody
    label = MessageBody(message['created_at'] + '\n\n' + message['content'])
    layout.addWidget(label)
    from command_trace import CommandTraceCard
    for progress in window.database.command_traces_for_message(message_id):
        card = CommandTraceCard(container)
        card.update_progress(progress)
        layout.addWidget(card)
    for attachment in window.database.attachments_for_message(message_id):
        path = root / attachment['local_path']
        if attachment['kind'] == 'image' and path.is_file():
            layout.addWidget(image_widget(path, container, 380))
            button = QPushButton('打开原图')
            button.clicked.connect(lambda checked=False, p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(p))))
            layout.addWidget(button)
        elif path.is_file():
            button = QPushButton('附件：' + attachment['file_name'])
            button.clicked.connect(lambda checked=False, p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(p))))
            layout.addWidget(button)
    layout.addStretch()
    scroll.setWidget(container)
    outer.addWidget(scroll)
    close = QPushButton('关闭')
    close.clicked.connect(dialog.accept)
    outer.addWidget(close)
    dialog.exec()


def manage_stickers(window, root):
    folder = root / 'assets' / 'stickers'
    folder.mkdir(parents=True, exist_ok=True)
    dialog = QDialog(window)
    dialog.setWindowTitle('表情库')
    dialog.resize(480, 420)
    layout = QVBoxLayout(dialog)
    hint = QLabel('导入图片后，给它起一个描述情绪的名字，例如“开心”“无语”“晚安”。\nAI 会按名字选择表情；空表情库不会影响聊天。')
    hint.setWordWrap(True)
    layout.addWidget(hint)
    listing = QListWidget()
    layout.addWidget(listing)
    def refresh():
        listing.clear()
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtGui import QIcon
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}:
                listing.addItem(QListWidgetItem(QIcon(str(path)), path.name))
        listing.setIconSize(QSize(48, 48))
    def add():
        paths, _ = QFileDialog.getOpenFileNames(dialog, '导入表情', '', '图片 (*.png *.jpg *.jpeg *.webp *.gif)')
        try:
            for value in paths:
                source = Path(value)
                if source.stat().st_size > 20 * 1024 * 1024 or QPixmap(str(source)).isNull():
                    FishDialog.information(dialog, '无法导入', f'{source.name} 不是有效图片，或超过 20 MB。')
                    continue
                destination = folder / source.name
                if destination.exists():
                    destination = folder / (source.stem + '_' + uuid.uuid4().hex[:6] + source.suffix)
                shutil.copy2(source, destination)
            refresh()
        except OSError as error:
            FishDialog.information(dialog, '导入失败', str(error))
    def rename():
        item = listing.currentItem()
        if not item:
            return
        source = folder / item.text()
        name, ok = QInputDialog.getText(dialog, '表情名称', '用简短文字描述表情：', text=source.stem)
        if not ok or not name.strip():
            return
        name = name.strip()
        if any(c in name for c in '<>:"/\\|?*') or name.endswith('.'):
            FishDialog.information(dialog, '名称无效', '名称不能包含文件路径或特殊符号。')
            return
        try:
            destination = folder / (name + source.suffix)
            if destination == source:
                return
            if destination.exists():
                raise OSError('已有同名表情。')
            source.rename(destination)
            # 已发送的表情继续指向改名后的文件。
            with window.database._connect() as connection:
                connection.execute("UPDATE message_extras SET target=? WHERE kind='sticker' AND target=?", (destination.name, source.name))
            refresh()
        except OSError as error:
            FishDialog.information(dialog, '改名失败', str(error))
    def remove():
        item = listing.currentItem()
        if item and FishDialog.question(dialog, '删除表情', '删除后，历史消息中的这张表情也将不可用。确定删除？', confirm_text='删除', danger=True):
            try:
                (folder / item.text()).unlink(missing_ok=True)
                refresh()
            except OSError as error:
                FishDialog.information(dialog, '删除失败', str(error))
    buttons = QHBoxLayout()
    for title, callback in [('导入', add), ('改名', rename), ('删除', remove), ('关闭', dialog.accept)]:
        button = QPushButton(title)
        button.clicked.connect(callback)
        buttons.addWidget(button)
    layout.addLayout(buttons)
    refresh()
    dialog.exec()
