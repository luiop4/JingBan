from __future__ import annotations

from collections import deque

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices


class PcmStreamPlayer(QObject):
    """Play incoming 16-bit mono PCM through one continuous Qt audio stream."""

    playback_finished = Signal()
    playback_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sink: QAudioSink | None = None
        self._output = None
        self._sample_rate = 0
        self._pending: deque[bytes] = deque()
        self._finish_requested = False
        self._paused = False
        self._timer = QTimer(self)
        self._timer.setInterval(10)
        self._timer.timeout.connect(self._write_pending_audio)

    @property
    def is_active(self) -> bool:
        return self._sink is not None or bool(self._pending)

    def append(self, pcm_data: bytes, sample_rate: int) -> None:
        if not pcm_data:
            return
        if len(pcm_data) % 2:
            raise ValueError("PCM 音频数据长度不是完整的 16 位采样帧。")
        if self._sink is None:
            self._start_sink(sample_rate)
        elif sample_rate != self._sample_rate:
            raise ValueError("语音流的采样率发生变化，无法接续当前播放。")

        self._finish_requested = False
        self._pending.append(bytes(pcm_data))
        if self._paused:
            return
        if not self._timer.isActive():
            self._timer.start()
        self._write_pending_audio()

    def finish(self) -> None:
        self._finish_requested = True
        if self._paused:
            return
        if self._sink is None:
            self.playback_finished.emit()
            return
        if not self._timer.isActive():
            self._timer.start()
        self._write_pending_audio()

    def stop(self) -> None:
        self._paused = False
        self._finish_requested = False
        self._pending.clear()
        self._timer.stop()
        if self._sink is not None:
            self._sink.stop()
            self._sink.deleteLater()
        self._sink = None
        self._output = None
        self._sample_rate = 0

    def pause(self) -> None:
        self._paused = True
        self._timer.stop()
        if self._sink is not None:
            self._sink.suspend()

    def resume(self) -> None:
        self._paused = False
        if self._sink is not None:
            self._sink.resume()
            self._timer.start()
            self._write_pending_audio()

    def _start_sink(self, sample_rate: int) -> None:
        device = QMediaDevices.defaultAudioOutput()
        if device.isNull():
            raise RuntimeError("没有可用的音频输出设备。")

        audio_format = QAudioFormat()
        audio_format.setSampleRate(int(sample_rate))
        audio_format.setChannelCount(1)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        sink = QAudioSink(device, audio_format, self)
        sink.setBufferSize(max(8192, int(sample_rate) // 2))
        sink.stateChanged.connect(self._on_sink_state_changed)
        output = sink.start()
        if output is None or sink.error().value != QAudio.Error.NoError.value:
            error = sink.error()
            sink.stop()
            sink.deleteLater()
            raise RuntimeError(f"无法启动实时语音播放（Qt 音频错误：{error}）。")

        self._sink = sink
        self._output = output
        self._sample_rate = int(sample_rate)
        if self._paused:
            sink.suspend()

    def _write_pending_audio(self) -> None:
        if self._paused:
            return
        sink = self._sink
        output = self._output
        if sink is None or output is None:
            self._timer.stop()
            return

        if sink.error().value != QAudio.Error.NoError.value:
            error = sink.error()
            self.stop()
            self.playback_failed.emit(f"实时语音播放失败（Qt 音频错误：{error}）。")
            return

        while self._pending:
            available = max(0, sink.bytesFree())
            available -= available % 2
            if available <= 0:
                break

            current = self._pending[0]
            write_size = min(available, len(current))
            write_size -= write_size % 2
            if write_size <= 0:
                break

            written = output.write(current[:write_size])
            if written <= 0:
                break
            if written >= len(current):
                self._pending.popleft()
            else:
                self._pending[0] = current[written:]

        buffer_size = max(0, sink.bufferSize())
        buffer_is_empty = buffer_size > 0 and sink.bytesFree() >= buffer_size
        if self._finish_requested and not self._pending and buffer_is_empty:
            self.stop()
            self.playback_finished.emit()
        elif not self._pending and not self._finish_requested:
            self._timer.stop()

    def _on_sink_state_changed(self, _state) -> None:
        if self._sink is None or self._sink.error().value == QAudio.Error.NoError.value:
            return
        error = self._sink.error()
        self.stop()
        self.playback_failed.emit(f"实时语音播放失败（Qt 音频错误：{error}）。")
