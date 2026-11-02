"""Resolve incoming OneBot images to real, persisted visual attachments."""
from __future__ import annotations

import base64
import hashlib
import html
import re
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImageReader


def incoming_content(event):
    segments = event.get('message')
    if not isinstance(segments, list):
        raw = str(segments or event.get('raw_message') or '')
        segments = []
        cursor = 0
        for match in re.finditer(r'\[CQ:image,([^\]]+)\]', raw):
            segments.append({'type': 'text', 'data': {'text': raw[cursor:match.start()]}})
            data = {}
            for part in match.group(1).split(','):
                key, sep, value = part.partition('=')
                if sep:
                    data[key] = html.unescape(value.replace('&#44;', ','))
            segments.append({'type': 'image', 'data': data})
            cursor = match.end()
        segments.append({'type': 'text', 'data': {'text': raw[cursor:]}})
    text, refs, stickers = [], [], []
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get('data'), dict):
            continue
        data = segment['data']
        if segment.get('type') == 'text':
            text.append(str(data.get('text', '')))
        elif segment.get('type') == 'image':
            url = str(data.get('url') or '')
            file = str(data.get('file_id') or data.get('file') or '')[:8192]
            if not url and file.startswith(('https://', 'http://')):
                url = file
            ref = {'url': url[:8192] if url.startswith(('https://', 'http://')) else '', 'file': file}
            fallback_file = str(data.get('file') or '')[:8192]
            if fallback_file and fallback_file != file:
                ref['fallback_file'] = fallback_file
            if ref['url'] or ref['file']:
                refs.append(ref)
                text.append('[图片]')
                if ref['url'] and (str(data.get('sub_type') or '0') != '0' or data.get('type') == 'sticker'):
                    stickers.append({'url': ref['url'], 'description': str(data.get('summary') or 'QQ 收藏表情')[:120]})
    return ''.join(text).strip(), refs[:9], stickers[:9]


def _image_sources(ref, bridge, cancelled, report):
    """Try each source independently; expired CDN URLs must not hide a cache hit."""
    from web_media import fetch
    urls = [ref.get('url', '')]
    files = list(dict.fromkeys(str(ref.get(key) or '') for key in ('file', 'fallback_file')))
    for file in files:
        if not file or bridge is None or cancelled():
            continue
        try:
            response = bridge.call_action('get_image', {'file': file}, timeout=15, cancelled=cancelled)
            data = response.get('data') or {}
            if not isinstance(data, dict):
                continue
        except Exception as error:
            report('get_image', error)
            continue
        encoded = data.get('base64')
        if isinstance(encoded, str) and len(encoded) <= 16*1024*1024:
            try:
                if encoded.startswith('base64://'):
                    encoded = encoded[9:]
                elif encoded.startswith('data:image/') and ';base64,' in encoded:
                    encoded = encoded.split(';base64,', 1)[1]
                yield base64.b64decode(encoded, validate=True), 'bridge_base64'
            except Exception as error:
                report('bridge_base64', error)
        # Trust only a cache location returned by the authenticated local bridge,
        # never a path supplied directly by the incoming chat message.
        if urlparse(str(getattr(bridge, 'url', ''))).hostname in {'127.0.0.1', 'localhost', '::1'}:
            try:
                cached = Path(str(data.get('file') or ''))
                if (cached.is_absolute() and cached.is_file() and not cached.is_symlink()
                        and cached.stat().st_size <= 12*1024*1024):
                    with cached.open('rb') as stream:
                        yield stream.read(12*1024*1024+1), 'bridge_cache'
            except Exception as error:
                report('bridge_cache', error)
        urls.append(str(data.get('url') or ''))
    for url in dict.fromkeys(urls):
        if cancelled():
            return
        if not url or not url.startswith(('https://', 'http://')):
            continue
        try:
            raw, _, _ = fetch(url, limit=12*1024*1024, cancelled=cancelled, timeout=(4, 8))
            yield raw, 'public_url'
        except Exception as error:
            report('public_url', error)


def _normalize_image(raw):
    if not raw or len(raw) > 12*1024*1024:
        raise ValueError('图片为空或超过12MiB')
    buffer = QBuffer()
    buffer.setData(raw)
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    reader.setDecideFormatFromContent(True)
    reader.setAutoTransform(True)
    # QQ pictures are raster media; never evaluate SVG or trust a cache suffix.
    if bytes(reader.format()).lower() not in {b'jpeg', b'jpg', b'png', b'gif', b'webp', b'bmp', b'tiff', b'tif', b'avif', b'heif', b'heic'}:
        raise ValueError('图片内容不是支持的位图格式')
    dimensions = reader.size()
    if (dimensions.width() <= 0 or dimensions.height() <= 0
            or dimensions.width()*dimensions.height() > 32_000_000):
        raise ValueError('图片格式不支持或尺寸过大')
    animated = reader.supportsAnimation()
    image = reader.read()
    if image.isNull():
        raise ValueError('图片解码失败')
    if max(image.width(), image.height()) > 1600:
        image = image.scaled(1600, 1600, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
    output = QBuffer()
    output.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(output, 'JPEG', 88):
        raise ValueError('图片转换失败')
    return bytes(output.data()), animated


def prepare_images(root, database, conversation_key, message_id, refs, bridge, cancelled):
    """Runs off the GUI thread. Never accepts a remote party's local file path."""
    root = Path(root)
    message = database.get_message(message_id) if message_id else None
    if not message or message['conversation_key'] != conversation_key or message['role'] != 'user':
        return [], ['图片原消息已删除或不属于当前会话。']
    existing = database.attachments_for_message(message_id)
    attachments = [row for row in existing if row['kind'] == 'image']
    errors = []
    # Persisted images are reusable even after the temporary QQ URL expires.
    for index, ref in enumerate(refs[:9]):
        if cancelled():
            return [], ['图片读取已停止。']
        if any(item.get('file_name') == f'QQ图片{index+1}.jpg' and (root / item['local_path']).is_file() for item in attachments):
            continue
        try:
            raw = None
            from startup_support import startup_log
            def report(phase, error):
                status = getattr(getattr(error, 'response', None), 'status_code', '')
                startup_log(root, f'message={message_id}; image={index+1}; source={phase}; '
                    f'error={type(error).__name__}; http={status}', 'qq-images.log')
            sources = _image_sources(ref, bridge, cancelled, report)
            try:
                for candidate, source in sources:
                    if cancelled():
                        return [], ['图片读取已停止。']
                    try:
                        raw, animated = _normalize_image(candidate)
                        break
                    except Exception as error:
                        report(source+'_decode', error)
            finally:
                sources.close()
            if raw is None:
                if cancelled():
                    return [], ['图片读取已停止。']
                raise ValueError('图片链接与QQ缓存均未取得可读取的原图')
            folder = root / 'data/attachments/qq_images'
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / (hashlib.sha256(raw).hexdigest() + '.jpg')
            if cancelled():
                return [], ['图片读取已停止。']
            if not path.is_file():
                path.write_bytes(raw)
            attachment = {'file_name': f'QQ图片{index+1}.jpg', 'kind': 'image', 'mime_type': 'image/jpeg',
                'local_path': path.relative_to(root).as_posix(), 'size_bytes': len(raw),
                'extracted_text': f'QQ 用户发送的第{index+1}张实际图片' + ('（动态图仅读取首帧）' if animated else '')}
            database.save_attachment(message_id, attachment)
            attachments.append(attachment)
        except Exception as error:
            # Signed URLs and transport credentials must not enter model/error history.
            from startup_support import startup_log
            startup_log(root, f'message={message_id}; image={index+1}; error={type(error).__name__}', 'qq-images.log')
            reason = str(error) if isinstance(error, ValueError) else '下载或解码失败，请重发图片'
            errors.append(f'第{index+1}张图片：{reason[:120]}')
    attachments.sort(key=lambda row: int((re.search(r'QQ图片(\d+)', row.get('file_name', '')) or ['0', '0'])[1]))
    parts, used = [], 0
    for item in attachments[:9]:
        path = (root / item['local_path']).resolve()
        if not path.is_relative_to((root / 'data/attachments').resolve()) or not path.is_file():
            continue
        raw = path.read_bytes()
        used += len(raw)
        if used > 12*1024*1024:
            break
        parts.extend([{'type': 'text', 'text': item.get('extracted_text') or 'QQ 用户发送的实际图片'},
                      {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(raw).decode('ascii'), 'detail': 'auto'}}])
    return parts, errors
