from __future__ import annotations

import asyncio
import json
import threading
import uuid
import base64
import concurrent.futures
import time
from collections import deque
from pathlib import Path

import websockets
from PySide6.QtCore import QThread, Signal


class QQActionError(RuntimeError):
    def __init__(self, message, outcome_unknown=False):
        super().__init__(message)
        self.outcome_unknown = outcome_unknown


class QQBridgeThread(QThread):
    """Connects to a local OneBot 11 forward WebSocket server."""

    status_changed = Signal(str)
    message_received = Signal(object)

    def __init__(self, url: str, access_token: str = "", parent=None):
        super().__init__(parent)
        self.url = url
        self.access_token = access_token
        self._loop: asyncio.AbstractEventLoop | None = None
        self._listen_task: asyncio.Task | None = None
        self._socket = None
        self._stop_requested = threading.Event()
        self._pending = {}
        self._delivery_locks = {}
        self._seen_messages = set()
        self._seen_order = deque()
        self._retry_allowed = True

    def run(self) -> None:
        try:
            asyncio.run(self._listen())
        except Exception as error:
            if not self._stop_requested.is_set():
                self.status_changed.emit(f"连接失败：{error}")
        finally:
            self._listen_task = None
            self._loop = None

    async def _listen(self) -> None:
        failures = 0
        while not self._stop_requested.is_set():
            began = time.monotonic()
            await self._listen_once()
            if self._stop_requested.is_set() or not self._retry_allowed:
                return
            failures = 1 if time.monotonic()-began >= 30 else failures+1
            delay = min(30, 2**min(failures-1, 5))
            self.status_changed.emit(f'桥接连接中断，{delay}秒后重连；未确认的发送不会自动重发')
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                if not self._stop_requested.is_set():
                    raise
                return

    async def _listen_once(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._listen_task = asyncio.current_task()
        headers = {}
        if self.access_token.strip():
            headers["Authorization"] = f"Bearer {self.access_token.strip()}"

        failed = False
        try:
            if self._stop_requested.is_set():
                return
            async with websockets.connect(
                self.url,
                extra_headers=headers or None,
                open_timeout=10,
                close_timeout=1,
                ping_interval=20,
                max_size=20*1024*1024,  # 12 MiB pictures can be ~16 MiB of OneBot Base64.
            ) as socket:
                self._socket = socket
                if self._stop_requested.is_set():
                    return
                self.status_changed.emit("已连接到本地桥接")
                while not self._stop_requested.is_set():
                    try:
                        raw = await asyncio.wait_for(socket.recv(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue
                    except websockets.ConnectionClosed:
                        break
                    try:
                        self._handle_event(raw)
                    except (TypeError, ValueError, KeyError, AttributeError):
                        self.status_changed.emit('收到无法解析的QQ事件，本条未处理；桥接继续连接')
        except asyncio.CancelledError:
            if not self._stop_requested.is_set():
                raise
        except asyncio.TimeoutError:
            if not self._stop_requested.is_set():
                failed = True
                self.status_changed.emit("连接失败：10 秒内未完成连接，请检查桥接是否启动、地址是否正确")
        except Exception as error:
            if not self._stop_requested.is_set():
                failed = True
                if getattr(error, 'status_code', None) in (401, 403):
                    self._retry_allowed = False
                self.status_changed.emit(f"连接失败：{error}")
        finally:
            self._socket = None
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(QQActionError('桥接已断开，操作结果未知，请先在 QQ 核对，勿重复执行', True))
            self._pending.clear()
            if not failed:
                self.status_changed.emit("已断开")

    def _handle_event(self, raw: str) -> None:
        try:
            event = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(event, dict):
            return
        echo = event.get('echo')
        if isinstance(echo, str) and echo in self._pending:
            future = self._pending.pop(echo)
            if not future.done():
                if event.get('status') == 'ok' and event.get('retcode', 0) == 0:
                    future.set_result(event)
                else:
                    future.set_exception(QQActionError(str(event.get('wording') or event.get('message') or event.get('retcode'))))
            return
        if event.get("post_type") != "message":
            return
        if event.get("message_type") != "private":
            return

        peer_id = str(event.get("user_id", "")).strip()
        if peer_id == str(event.get('self_id', '')):
            return
        message_key = (str(event.get('self_id', '')), peer_id, str(event.get('message_id', '')))
        tracked = type(event.get('message_id')) in (str, int) and message_key[-1] not in ('', '0')
        if tracked and message_key in self._seen_messages:
            return
        sender = event.get("sender")
        sender = sender if isinstance(sender, dict) else {}
        peer_name = sender.get("card") or sender.get("nickname") or peer_id
        from qq_images import incoming_content
        message, image_refs, stickers = incoming_content(event)
        images = [ref['url'] for ref in image_refs if ref['url']]
        if peer_id and message:
            if tracked:
                self._seen_messages.add(message_key)
                self._seen_order.append(message_key)
                if len(self._seen_order) > 1024:
                    self._seen_messages.discard(self._seen_order.popleft())
            self.message_received.emit(
                {
                    "peer_id": peer_id,
                    "peer_name": str(peer_name),
                    "text": message,
                    "images": images[:9],
                    "image_refs": image_refs,
                    "stickers": stickers[:9],
                }
            )

    async def _call_action(self, action, params, timeout=30):
        if self._socket is None:
            raise QQActionError("QQ 桥接尚未连接。")
        echo = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._pending[echo] = future
        dispatched = False
        try:
            # A transport failure during send cannot prove the server did not act.
            dispatched = True
            await self._socket.send(json.dumps({'action': action, 'params': params, 'echo': echo}, ensure_ascii=False))
            return await asyncio.wait_for(future, timeout)
        except QQActionError:
            raise
        except (asyncio.TimeoutError, websockets.ConnectionClosed, OSError) as error:
            raise QQActionError('等待 QQ 操作回执失败，结果未知，请在 QQ 核对后再操作', dispatched) from error
        finally:
            self._pending.pop(echo, None)

    def call_action(self, action, params, timeout=90, cancelled=lambda: False):
        """Worker-thread API. The existing listener alone receives WebSocket frames."""
        return self._wait_coroutine(self._call_action(action, params, timeout), timeout, cancelled)

    def _wait_coroutine(self, coroutine, timeout, cancelled):
        if not self.isRunning() or self._loop is None or self._socket is None:
            coroutine.close()
            raise QQActionError('QQ 桥接尚未连接。')
        if cancelled():
            coroutine.close()
            raise QQActionError('操作已取消，尚未发送。')
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        except RuntimeError as error:
            coroutine.close()
            raise QQActionError('QQ 桥接已停止。') from error
        deadline = time.monotonic() + timeout + 5
        while True:
            try:
                return future.result(timeout=0.2)
            except concurrent.futures.TimeoutError:
                if time.monotonic() >= deadline:
                    future.cancel()
                    raise QQActionError('桥接操作等待超时，结果未知，请在 QQ 核对。', True)
                if cancelled():
                    future.cancel()
                    raise QQActionError('等待已取消；请求可能已执行，请在 QQ 核对，勿直接重试。', True)
            except concurrent.futures.CancelledError as error:
                raise QQActionError('桥接已停止，操作结果未知，请在 QQ 核对。', True) from error

    async def _send(self, peer_id: str, message) -> None:
        user_id: int | str = int(peer_id) if peer_id.isdigit() else peer_id
        await self._call_action('send_private_msg', {'user_id': user_id, 'message': message})
        self.status_changed.emit(f'已发送至 QQ {peer_id}')

    def send_private_message(self, peer_id: str, text: str) -> bool:
        if not self.isRunning() or self._loop is None or self._socket is None:
            return False
        self._schedule(self._send(peer_id, [{'type': 'text', 'data': {'text': text}}]))
        return True

    async def _send_bundle(self, peer_id, messages, permitted, cancelled):
        lock = self._delivery_locks.setdefault(peer_id, asyncio.Lock())
        sent = 0
        async with lock:
            for index, message in enumerate(messages):
                if cancelled() or not permitted() or self._stop_requested.is_set():
                    return {'confirmed': False, 'sent_parts': sent, 'total_parts': len(messages),
                            'error': '发送已停止或权限已撤销，剩余内容未发送。'}
                try:
                    await self._call_action('send_private_msg', {'user_id': int(peer_id), 'message': message}, 20)
                except QQActionError as error:
                    return {'confirmed': False, 'sent_parts': sent, 'total_parts': len(messages),
                            'error': str(error), 'outcome_unknown': error.outcome_unknown}
                sent += 1
                if index+1 < len(messages):
                    for _ in range(6):
                        await asyncio.sleep(0.1)
                        if cancelled() or not permitted():
                            break
        result = {'confirmed': True, 'sent_parts': sent, 'total_parts': len(messages)}
        self.status_changed.emit(f'QQ 回复已按顺序发送，共 {sent} 条')
        return result

    def send_chat_reply(self, peer_id, text, permitted=lambda: True, *, compact=False):
        """Nonblocking GUI API; command confirmations retain send_private_message."""
        from qq_delivery import split_reply
        if not peer_id.isdigit() or not self.isRunning() or self._loop is None or self._socket is None:
            return False
        messages = [[{'type': 'text', 'data': {'text': part}}] for part in split_reply(text, compact=compact)]
        if not messages:
            return True
        async def deliver():
            result = await self._send_bundle(peer_id, messages, permitted, self._stop_requested.is_set)
            if not result['confirmed']:
                self.status_changed.emit(f"QQ 已确认发送 {result['sent_parts']}/{result['total_parts']} 条；" + result['error'])
        self._schedule(deliver())
        return True

    def send_bundle_wait(self, peer_id, messages, permitted, cancelled):
        if not peer_id.isdigit():
            raise QQActionError('无效的接收方 QQ。')
        return self._wait_coroutine(self._send_bundle(peer_id, messages, permitted, cancelled),
                                    25*len(messages)+10, cancelled)

    def _schedule(self, coroutine):
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        def completed(result):
            try:
                result.result()
            except Exception as error:
                self.status_changed.emit(f'发送未确认：{error or "等待桥接回执超时，请检查 QQ，勿重复发送"}')
        future.add_done_callback(completed)

    async def _send_media(self, peer_id, path, kind):
        def encode():
            file = Path(path)
            if file.stat().st_size > 30 * 1024 * 1024:
                raise ValueError('文件超过 30 MB')
            return 'base64://' + base64.b64encode(file.read_bytes()).decode('ascii')
        encoded = await asyncio.to_thread(encode)
        await self._send(peer_id, [{'type': kind, 'data': {'file': encoded}}])

    def send_media(self, peer_id: str, path: str, kind: str) -> bool:
        if kind not in ('image', 'record') or not peer_id.isdigit():
            return False
        if not self.isRunning() or self._loop is None or self._socket is None:
            return False
        self._schedule(self._send_media(peer_id, path, kind))
        return True

    def stop_bridge(self) -> None:
        self._stop_requested.set()
        loop, task = self._loop, self._listen_task
        if loop is not None and task is not None:
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                # The event loop may have finished between the state check and cancellation.
                pass

