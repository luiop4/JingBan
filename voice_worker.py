"""Cancellable speech requests. Cancellation closes the active HTTP stream."""
from __future__ import annotations

import asyncio
import base64
import importlib
import json
from pathlib import Path
import tempfile
import threading
import uuid
import wave

from PySide6.QtCore import QThread, Signal


def _load_http_client():
    """Use the HTTP client supplied by either generation of the OpenAI SDK.

    Load it only when speech is requested, so optional speech dependencies
    cannot prevent the application from importing its UI and chat workers.
    """
    for name in ('httpx2', 'httpx'):
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError as error:
            if error.name == name:
                continue
            raise RuntimeError(f'语音请求组件 {name} 的依赖缺失：{error.name}。请修复软件运行环境。') from error
        if not all(hasattr(module, attribute) for attribute in ('AsyncClient', 'Timeout')):
            raise RuntimeError(f'语音请求组件 {name} 不兼容，缺少 AsyncClient 或 Timeout。')
        return module
    raise RuntimeError('语音请求组件缺失（httpx2 / httpx），请修复软件运行环境。')


class TtsWorker(QThread):
    audio_ready = Signal(str, object, bool)
    audio_chunk = Signal(bytes, int)
    synthesis_failed = Signal(str)

    def __init__(self, voice_settings, text, parent=None, batch_id=None, stream_audio=False):
        super().__init__(parent)
        self.voice_settings = dict(voice_settings)
        self.text, self.batch_id, self.stream_audio = text, batch_id, stream_audio
        self.cancelled = False
        self.synthesis_complete = False
        self._lock = threading.Lock()
        self._loop = self._task = None

    def cancel(self):
        self.requestInterruption()
        with self._lock:
            if self.cancelled:
                return
            self.cancelled = True
            loop, task = self._loop, self._task
            if loop is not None and task is not None:
                try:
                    loop.call_soon_threadsafe(task.cancel)
                except RuntimeError:
                    pass

    def run(self):
        try:
            asyncio.run(self._request())
        except asyncio.CancelledError:
            pass
        except Exception as error:
            if not self.cancelled:
                self.synthesis_failed.emit(str(error).strip() or type(error).__name__)

    async def _request(self):
        path = None
        writer = None
        success = False
        try:
            with self._lock:
                self._loop = asyncio.get_running_loop()
                self._task = asyncio.current_task()
                if self.cancelled:
                    raise asyncio.CancelledError()
            httpx = _load_http_client()
            settings = self.voice_settings
            doubao = settings.get('provider', 'doubao') == 'doubao'
            if doubao:
                key = str(settings.get('doubao_api_key', '')).strip()
                resource = str(settings.get('doubao_resource_id', 'seed-tts-2.0')).strip()
                speaker = str(settings.get('doubao_speaker_id', '')).strip()
                if not key or not resource or not speaker:
                    raise ValueError('请先填写豆包语音 API Key、模型资源 ID 和音色 ID。')
                url = str(settings.get('doubao_endpoint', 'https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse')).strip()
                payload = {'user': {'uid': settings.get('doubao_uid') or 'ai-chat-memory'},
                           'req_params': {'text': self.text, 'speaker': speaker, 'audio_params': {
                               'format': 'pcm', 'sample_rate': 24000,
                               'speech_rate': int(settings.get('doubao_speech_rate', 0))}}}
                headers = {'X-Api-Key': key, 'X-Api-Resource-Id': resource,
                           'X-Api-Request-Id': str(uuid.uuid4()), 'Accept': 'text/event-stream',
                           'X-Control-Require-Usage-Tokens-Return': '*'}
            else:
                url = str(settings.get('base_url', '')).rstrip('/') + ('/synthesize/stream' if self.stream_audio else '/synthesize')
                payload, headers = {'text': self.text}, {}
            folder = Path(__file__).resolve().parent / 'data' / 'tts_audio'
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(suffix='.wav', prefix='reply_', dir=folder, delete=False) as output:
                path = Path(output.name)
            sample_rate, received, odd_byte, completed = 24000 if doubao else 0, 0, b'', False

            def open_writer():
                nonlocal writer
                writer = wave.open(str(path), 'wb')
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(sample_rate)

            def pcm_chunk(encoded):
                nonlocal odd_byte, received
                pcm = odd_byte + base64.b64decode(str(encoded), validate=True)
                odd_byte, pcm = (pcm[-1:], pcm[:-1]) if len(pcm) % 2 else (b'', pcm)
                if pcm:
                    if writer is None:
                        raise ValueError('语音服务未先返回音频格式。')
                    writer.writeframesraw(pcm)
                    received += len(pcm)
                    self.audio_chunk.emit(pcm, sample_rate)

            def consume(raw):
                nonlocal sample_rate, completed
                if self.cancelled:
                    raise asyncio.CancelledError()
                if raw == '[DONE]':
                    completed = True
                    return
                event = json.loads(raw)
                if not isinstance(event, dict):
                    return
                if doubao:
                    code = int(event.get('code', 0) or 0)
                    if code == 20000000:
                        completed = True
                    elif code != 0:
                        raise RuntimeError(f"豆包语音服务错误（{code}）：{event.get('message') or event.get('msg') or '合成失败'}")
                    else:
                        encoded = event.get('data')
                        if isinstance(encoded, dict):
                            encoded = encoded.get('data')
                        if encoded:
                            pcm_chunk(encoded)
                elif event.get('type') == 'start':
                    sample_rate = int(event.get('sample_rate', 0))
                    if sample_rate <= 0 or event.get('format') != 's16le' or int(event.get('channels', 0)) != 1:
                        raise ValueError('语音服务返回了不支持的音频格式。')
                    open_writer()
                elif event.get('type') == 'audio':
                    pcm_chunk(event.get('data', ''))
                elif event.get('type') == 'end':
                    completed = True
                elif event.get('type') == 'error':
                    raise RuntimeError(str(event.get('message', '语音合成失败。')))

            timeout = httpx.Timeout(600.0 if not doubao else 120.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream('POST', url, json=payload, headers=headers) as response:
                    if response.is_error:
                        if response.status_code in (401, 403):
                            raise RuntimeError(f'语音接口拒绝访问（HTTP {response.status_code}），请检查密钥、服务开通状态及音色权限。')
                        raise RuntimeError(f'语音接口请求失败（HTTP {response.status_code}）。')
                    if not doubao and not self.stream_audio:
                        content = await response.aread()
                        if not content.startswith(b'RIFF') or content[8:12] != b'WAVE':
                            raise ValueError('语音服务返回的文件不是有效 WAV 音频。')
                        path.write_bytes(content)
                        completed = True
                    else:
                        if doubao:
                            open_writer()
                        lines = []
                        async for line in response.aiter_lines():
                            if self.cancelled:
                                raise asyncio.CancelledError()
                            if doubao:
                                if not line.strip():
                                    if lines:
                                        consume('\n'.join(lines))
                                        lines.clear()
                                elif line.startswith('data:'):
                                    lines.append(line[5:].lstrip())
                                elif not line.startswith((':', 'event:', 'id:', 'retry:')):
                                    lines.append(line)
                            elif line.strip():
                                consume(line)
                            if completed:
                                break
                        if lines and not completed:
                            consume('\n'.join(lines))
                        if not received or odd_byte:
                            raise ValueError('语音服务返回的音频为空或不完整。')
            if not completed:
                raise RuntimeError('语音流意外中断，未收到完成事件。')
            if writer is not None:
                writer.close()
                writer = None
            with self._lock:
                if self.cancelled:
                    raise asyncio.CancelledError()
                self.synthesis_complete = True
            success = True
            self.audio_ready.emit(str(path), self.batch_id, doubao or self.stream_audio)
        finally:
            if writer is not None:
                writer.close()
            if path is not None and not success:
                path.unlink(missing_ok=True)
            with self._lock:
                self._loop = self._task = None
