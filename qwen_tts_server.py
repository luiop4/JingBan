"""A small local HTTP server that keeps one Qwen3-TTS model loaded in memory."""

from __future__ import annotations

import base64
import io
import json
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
import sys


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
STREAMING_SOURCE_DIR = BASE_DIR / "tools" / "qwen3_tts_streaming"
if STREAMING_SOURCE_DIR.is_dir():
    sys.path.insert(0, str(STREAMING_SOURCE_DIR))

from qwen_tts import Qwen3TTSModel

MODEL: Qwen3TTSModel | None = None
MODEL_ID = ""
MODEL_ERROR = ""
MODEL_DEVICE = ""
MODEL_DTYPE = ""
MODEL_ATTENTION = ""
PROMPT_CACHE: dict[tuple[str, int, str], list] = {}
INFERENCE_LOCK = threading.Lock()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_model_once()
    yield


app = FastAPI(title="Local Qwen3-TTS", docs_url=None, redoc_url=None, lifespan=lifespan)


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)


def read_voice_config() -> dict:
    try:
        settings = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        voice = settings.get("voice", {})
        if voice.get("provider") != "qwen3":
            raise ValueError("config.json 的语音 provider 不是 qwen3，请先在聊天程序中保存语音设置。")
        return voice
    except FileNotFoundError as error:
        raise ValueError("没有找到 config.json，请先运行一次聊天程序并保存语音设置。") from error


def load_model_once() -> None:
    global MODEL, MODEL_ID, MODEL_ERROR, MODEL_DEVICE, MODEL_DTYPE, MODEL_ATTENTION
    try:
        voice = read_voice_config()
        MODEL_ID = voice.get("model_id", "Qwen/Qwen3-TTS-12Hz-0.6B-Base").strip()
        if not MODEL_ID:
            raise ValueError("Qwen3 模型名称不能为空。")
        model_path = Path(MODEL_ID).expanduser()
        if not model_path.is_absolute():
            model_path = BASE_DIR / model_path
        model_source = str(model_path.resolve()) if (model_path / "config.json").is_file() else MODEL_ID

        requested_device = str(voice.get("device", "auto")).strip().lower()
        if requested_device == "auto":
            device_map = "cuda:0" if torch.cuda.is_available() else "cpu"
        elif requested_device.startswith("cuda") and not torch.cuda.is_available():
            raise ValueError("语音设置选择了 CUDA，但当前 PyTorch 没有检测到可用显卡。请把设备改成 auto 或 cpu。")
        else:
            device_map = requested_device

        requested_dtype = str(voice.get("dtype", "auto")).strip().lower()
        dtype_map = {
            "auto": torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
            else (torch.float16 if torch.cuda.is_available() else torch.float32),
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        if requested_dtype not in dtype_map:
            raise ValueError("语音精度设置无效，请选择 auto、float16、bfloat16 或 float32。")
        dtype = dtype_map[requested_dtype]
        if device_map == "cpu" and dtype in (torch.float16, torch.bfloat16):
            raise ValueError("CPU 推理请选择 auto 或 float32 精度。")
        MODEL_DEVICE = device_map
        MODEL_DTYPE = requested_dtype
        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32 = True

        # Restore the earlier PyTorch SDPA path. The later FlashAttention build
        # did not improve this machine's measured decode time consistently.
        MODEL_ATTENTION = "sdpa"
        MODEL = Qwen3TTSModel.from_pretrained(
            model_source,
            device_map=device_map,
            dtype=dtype,
            attn_implementation=MODEL_ATTENTION,
        )
        print(
            f"Qwen3-TTS 已加载：{MODEL_ID}（{device_map}，{dtype}，{MODEL_ATTENTION}）",
            flush=True,
        )
    except Exception as error:
        MODEL_ERROR = str(error)
        print(f"Qwen3-TTS 加载失败：{MODEL_ERROR}", flush=True)


@app.get("/health")
def health() -> dict:
    return {
        "ready": MODEL is not None,
        "model": MODEL_ID,
        "device": MODEL_DEVICE,
        "dtype": MODEL_DTYPE,
        "attention": MODEL_ATTENTION,
        "error": MODEL_ERROR,
    }


@app.post("/synthesize")
def synthesize(request: SynthesisRequest) -> Response:
    if MODEL is None:
        raise HTTPException(status_code=503, detail=MODEL_ERROR or "语音模型仍在加载。")

    request_started = time.perf_counter()
    prompt_seconds = 0.0
    lock_wait_seconds = 0.0
    generation_seconds = 0.0
    write_seconds = 0.0
    prompt_cache_hit = False
    try:
        voice = read_voice_config()
        if voice.get("model_id", MODEL_ID).strip() != MODEL_ID:
            raise ValueError("模型设置已更改，请关闭并重新启动 Qwen3-TTS 服务。")
        requested_device = str(voice.get("device", "auto")).strip().lower()
        if requested_device == "auto":
            requested_device = "cuda:0" if torch.cuda.is_available() else "cpu"
        if requested_device != MODEL_DEVICE or str(voice.get("dtype", "auto")).strip().lower() != MODEL_DTYPE:
            raise ValueError("设备或精度设置已更改，请关闭并重新启动 Qwen3-TTS 服务。")
        reference_audio = Path(voice.get("reference_audio", "")).expanduser()
        if not reference_audio.is_absolute():
            reference_audio = BASE_DIR / reference_audio
        reference_audio = reference_audio.resolve()
        reference_text = voice.get("reference_text", "").strip()
        if not reference_audio.is_file():
            raise ValueError("参考音频不存在；请在聊天程序的语音页重新选择文件。")
        if not reference_text:
            raise ValueError("参考音频对应的文字不能为空。")

        cache_key = (str(reference_audio), reference_audio.stat().st_mtime_ns, reference_text)
        lock_wait_started = time.perf_counter()
        with INFERENCE_LOCK:
            lock_wait_seconds = time.perf_counter() - lock_wait_started
            if cache_key not in PROMPT_CACHE:
                PROMPT_CACHE.clear()
                prompt_started = time.perf_counter()
                PROMPT_CACHE[cache_key] = MODEL.create_voice_clone_prompt(
                    ref_audio=str(reference_audio),
                    ref_text=reference_text,
                    x_vector_only_mode=False,
                )
                prompt_seconds = time.perf_counter() - prompt_started
            else:
                prompt_cache_hit = True

            generation_started = time.perf_counter()
            wavs, sample_rate = MODEL.generate_voice_clone(
                text=request.text.strip(),
                language=voice.get("language", "Auto"),
                voice_clone_prompt=PROMPT_CACHE[cache_key],
                max_new_tokens=int(voice.get("max_new_tokens", 512)),
                temperature=float(voice.get("temperature", 0.7)),
                top_p=float(voice.get("top_p", 0.8)),
                top_k=int(voice.get("top_k", 20)),
                repetition_penalty=float(voice.get("repetition_penalty", 1.05)),
            )
            generation_seconds = time.perf_counter() - generation_started

        write_started = time.perf_counter()
        audio_buffer = io.BytesIO()
        sf.write(audio_buffer, wavs[0], sample_rate, format="WAV", subtype="PCM_16")
        write_seconds = time.perf_counter() - write_started
        audio_seconds = len(wavs[0]) / sample_rate if sample_rate else 0.0
        total_seconds = time.perf_counter() - request_started
        real_time_factor = total_seconds / audio_seconds if audio_seconds > 0 else 0.0
        print(
            "[TTS] "
            f"chars={len(request.text.strip())} "
            f"prompt_cached={prompt_cache_hit} "
            f"queue_wait={lock_wait_seconds:.2f}s "
            f"prompt={prompt_seconds:.2f}s "
            f"generate_decode={generation_seconds:.2f}s "
            f"wav={write_seconds:.2f}s "
            f"audio={audio_seconds:.2f}s "
            f"total={total_seconds:.2f}s "
            f"rtf={real_time_factor:.2f}",
            flush=True,
        )
        return Response(
            content=audio_buffer.getvalue(),
            media_type="audio/wav",
            headers={
                "X-TTS-Prompt-Seconds": f"{prompt_seconds:.3f}",
                "X-TTS-Generate-Decode-Seconds": f"{generation_seconds:.3f}",
                "X-TTS-Audio-Seconds": f"{audio_seconds:.3f}",
            },
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"语音合成失败：{error}") from error


@app.post("/synthesize/stream")
def synthesize_stream(request: SynthesisRequest) -> StreamingResponse:
    """Generate cloned speech locally and return small PCM chunks as NDJSON."""
    if MODEL is None:
        raise HTTPException(status_code=503, detail=MODEL_ERROR or "语音模型仍在加载。")

    request_started = time.perf_counter()
    try:
        voice = read_voice_config()
        if voice.get("model_id", MODEL_ID).strip() != MODEL_ID:
            raise ValueError("模型设置已更改，请关闭并重新启动 Qwen3-TTS 服务。")
        requested_device = str(voice.get("device", "auto")).strip().lower()
        if requested_device == "auto":
            requested_device = "cuda:0" if torch.cuda.is_available() else "cpu"
        if requested_device != MODEL_DEVICE or str(voice.get("dtype", "auto")).strip().lower() != MODEL_DTYPE:
            raise ValueError("设备或精度设置已更改，请关闭并重新启动 Qwen3-TTS 服务。")
        if not callable(getattr(MODEL, "stream_generate_voice_clone", None)):
            raise ValueError("当前本地 Qwen3-TTS 源码没有流式语音克隆接口。")

        reference_audio = Path(voice.get("reference_audio", "")).expanduser()
        if not reference_audio.is_absolute():
            reference_audio = BASE_DIR / reference_audio
        reference_audio = reference_audio.resolve()
        reference_text = voice.get("reference_text", "").strip()
        if not reference_audio.is_file():
            raise ValueError("参考音频不存在；请在聊天程序的语音页重新选择文件。")
        if not reference_text:
            raise ValueError("参考音频对应的文字不能为空。")

        cache_key = (str(reference_audio), reference_audio.stat().st_mtime_ns, reference_text)
        prompt_started = time.perf_counter()
        with INFERENCE_LOCK:
            if cache_key not in PROMPT_CACHE:
                PROMPT_CACHE.clear()
                PROMPT_CACHE[cache_key] = MODEL.create_voice_clone_prompt(
                    ref_audio=str(reference_audio),
                    ref_text=reference_text,
                    x_vector_only_mode=False,
                )
        prompt_seconds = time.perf_counter() - prompt_started
        sample_rate = int(MODEL.model.speech_tokenizer.get_output_sample_rate())
        generation_options = {
            "language": voice.get("language", "Auto"),
            "voice_clone_prompt": PROMPT_CACHE[cache_key],
            "max_frames": int(voice.get("max_new_tokens", 512)),
            "emit_every_frames": 4,
            "decode_window_frames": 80,
            "overlap_samples": 0,
            "temperature": float(voice.get("temperature", 0.7)),
            "top_p": float(voice.get("top_p", 0.8)),
            "top_k": int(voice.get("top_k", 20)),
            "repetition_penalty": float(voice.get("repetition_penalty", 1.05)),
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"语音合成失败：{error}") from error

    def generate_stream():
        audio_samples = 0
        chunk_count = 0
        first_chunk_seconds = 0.0
        completed = False

        def json_line(payload: dict) -> bytes:
            return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")

        yield json_line({"type": "start", "sample_rate": sample_rate, "format": "s16le", "channels": 1})
        try:
            with INFERENCE_LOCK:
                for audio_chunk, chunk_rate in MODEL.stream_generate_voice_clone(
                    text=request.text.strip(),
                    **generation_options,
                ):
                    if int(chunk_rate) != sample_rate:
                        raise RuntimeError("流式语音块的采样率在合成过程中发生变化。")
                    chunk = np.asarray(audio_chunk, dtype=np.float32).reshape(-1)
                    if not chunk.size:
                        continue
                    pcm = (np.clip(chunk, -1.0, 1.0) * 32767.0).astype("<i2", copy=False).tobytes()
                    if chunk_count == 0:
                        first_chunk_seconds = time.perf_counter() - request_started
                    chunk_count += 1
                    audio_samples += len(pcm) // 2
                    yield json_line({"type": "audio", "data": base64.b64encode(pcm).decode("ascii")})
            completed = True
            yield json_line({"type": "end"})
        except GeneratorExit:
            raise
        except Exception as error:
            print(f"[TTS stream] 合成失败：{error}", flush=True)
            yield json_line({"type": "error", "message": f"语音合成失败：{error}"})
        finally:
            total_seconds = time.perf_counter() - request_started
            audio_seconds = audio_samples / sample_rate if sample_rate else 0.0
            rtf = total_seconds / audio_seconds if audio_seconds > 0 else 0.0
            print(
                "[TTS stream] "
                f"chars={len(request.text.strip())} "
                f"prompt={prompt_seconds:.2f}s "
                f"first_audio={first_chunk_seconds:.2f}s "
                f"chunks={chunk_count} "
                f"audio={audio_seconds:.2f}s "
                f"total={total_seconds:.2f}s "
                f"rtf={rtf:.2f} "
                f"complete={completed}",
                flush=True,
            )

    return StreamingResponse(
        generate_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-TTS-Stream-Format": "pcm_s16le_base64_ndjson",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9881, log_level="info")
