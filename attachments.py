from __future__ import annotations

import mimetypes
import base64
import hashlib
import json
import re
import shutil
import subprocess
import time
import threading
import urllib.parse
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader
from PySide6.QtGui import QImageReader


BASE_DIR = Path(__file__).resolve().parent
ATTACHMENT_DIR = BASE_DIR / "data" / "attachments"
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_DOCUMENT_CHARS = 30_000

IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
TEXT_TYPES = {".txt", ".md", ".csv", ".json", ".log", ".html", ".htm"}
DOCUMENT_TYPES = TEXT_TYPES | {".pdf", ".docx"}
VIDEO_TYPES = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".mpeg", ".mpg"}
MAX_VIDEO_BYTES = 1024 * 1024 * 1024
MAX_VIDEO_SECONDS = 60 * 60
VIDEO_FRAME_COUNT = 12
VIDEO_FRAME_SIZE = 768


def video_frame_parts(manifest: dict, byte_budget: int) -> tuple[list[dict], int]:
    """Build timestamp/image pairs from cached frames; never send missing files."""
    parts, used = [], 0
    for frame in manifest.get("frames", [])[:VIDEO_FRAME_COUNT]:
        path = (BASE_DIR / str(frame.get("path", ""))).resolve()
        if not path.is_relative_to(ATTACHMENT_DIR.resolve()) or not path.is_file():
            continue
        raw = path.read_bytes()
        if used + len(raw) > byte_budget:
            break
        seconds = float(frame.get("time_seconds", 0))
        parts.extend([
            {"type": "text", "text": f"[视频画面 @ {seconds:.1f} 秒]"},
            {"type": "image_url", "image_url": {
                "url": "data:" + ("image/png" if path.suffix.lower() == ".png" else "image/jpeg") + ";base64," + base64.b64encode(raw).decode("ascii"),
                "detail": "auto"}},
        ])
        used += len(raw)
    return parts, used


def _binary(name: str) -> str:
    candidates = [
        shutil.which(name),
        str(BASE_DIR / "tools" / "ffmpeg" / "bin" / f"{name}.exe"),
        str(BASE_DIR / "tools" / name / f"{name}.exe"),
        str(BASE_DIR / "tools" / f"{name}.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise ValueError("视频理解需要 FFmpeg 和 ffprobe。请安装 FFmpeg 并将其加入 PATH 后重启软件。")


def _video_process(command, timeout, cancelled):
    # Pipes are drained by communicate while polling for cancellation.
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancelled():
                raise ValueError('视频读取已停止。')
            if time.monotonic() >= deadline:
                raise ValueError('视频处理超时。')
            try:
                stdout, stderr = process.communicate(timeout=0.2)
                return subprocess.CompletedProcess(command, process.returncode,
                    stdout.decode('utf-8', errors='replace'), stderr.decode('utf-8', errors='replace'))
            except subprocess.TimeoutExpired:
                pass
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


def _extract_video_frames(video_path: Path, frame_dir: Path, cancelled=lambda: False,
                          max_seconds=MAX_VIDEO_SECONDS, frame_count=VIDEO_FRAME_COUNT) -> tuple[float, list[dict]]:
    ffmpeg, ffprobe = _binary("ffmpeg"), _binary("ffprobe")
    probe = _video_process(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video_path)],
        30, cancelled)
    if probe.returncode:
        raise ValueError('无法读取视频时长。')
    duration = float(json.loads(probe.stdout).get("format", {}).get("duration", 0))
    if duration <= 0 or duration > max_seconds:
        raise ValueError("视频时长无效或超过本次读取限制。")
    frame_dir.mkdir(parents=True, exist_ok=True)
    count = min(frame_count, max(1, int(duration // 5) + 1))
    frames = []
    for index in range(count):
        timestamp = duration * (index + 0.5) / count
        output = frame_dir / f"frame_{index + 1:02d}.jpg"
        result = _video_process(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{timestamp:.3f}",
             "-i", str(video_path), "-frames:v", "1", "-vf",
             f"scale={VIDEO_FRAME_SIZE}:{VIDEO_FRAME_SIZE}:force_original_aspect_ratio=decrease",
             "-q:v", "5", "-y", str(output)],
            45, cancelled,
        )
        if result.returncode == 0 and output.is_file() and output.stat().st_size:
            frames.append({"time_seconds": round(timestamp, 2),
                           "path": output.relative_to(BASE_DIR).as_posix()})
    if not frames:
        raise ValueError("没有从视频中提取到可读取的画面。")
    return duration, frames


_VIDEO_LOCK = threading.Lock()


def prepare_bilibili_video(url: str, cancelled=lambda: False, max_bytes=MAX_VIDEO_BYTES,
                           max_seconds=MAX_VIDEO_SECONDS, frame_count=VIDEO_FRAME_COUNT) -> dict:
    # Manual and autonomous readers share the cache; serialize writes, cancellably.
    while not _VIDEO_LOCK.acquire(timeout=0.2):
        if cancelled():
            raise ValueError('视频读取已停止。')
    try:
        if cancelled():
            raise ValueError('视频读取已停止。')
        return _prepare_bilibili_video(url, cancelled, max_bytes, max_seconds, frame_count)
    finally:
        _VIDEO_LOCK.release()


def _prepare_bilibili_video(url, cancelled, max_bytes, max_seconds, frame_count):
    """Download a public Bilibili video into a bounded local cache and sample frames."""
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if host != "bilibili.com" and not host.endswith(".bilibili.com") and host != "b23.tv":
        raise ValueError("目前只接受 Bilibili 链接。")
    # 分享文案可能紧贴链接，保留视频编号与分 P，去掉追踪参数。
    video_id = re.match(r"/video/(BV[a-zA-Z0-9]+|av[0-9]+)", parsed.path)
    if video_id:
        part = urllib.parse.parse_qs(parsed.query).get("p", ["1"])[0]
        part = part if part.isdigit() and int(part) > 0 else "1"
        url = f"https://www.bilibili.com/video/{video_id.group(1)}/?p={part}"
    _binary("ffmpeg")
    _binary("ffprobe")
    try:
        import yt_dlp
    except ImportError as error:
        raise ValueError("B 站链接解析组件尚未安装。运行项目的环境更新脚本后即可使用。") from error

    cache_root = ATTACHMENT_DIR / "video_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    cache_dir = cache_root / digest
    manifest_path = cache_dir / "frames.json"
    if manifest_path.is_file():
        try:
            cached = json.loads(manifest_path.read_text(encoding="utf-8"))
            if cached["frames"] and all((BASE_DIR / frame["path"]).is_file() for frame in cached["frames"]):
                if float(cached.get('duration_seconds', 0)) > max_seconds:
                    raise ValueError('视频超过本轮时长限制。')
                if frame_count < len(cached['frames']):
                    frames = cached['frames']
                    cached = {**cached, 'frames': [frames[min(len(frames)-1, int((i+0.5)*len(frames)/frame_count))] for i in range(frame_count)]}
                return cached
        except (OSError, ValueError, KeyError, TypeError):
            pass
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(cache_dir / "video.%(ext)s")
    def progress(info):
        if cancelled():
            raise ValueError('视频读取已停止。')
        if int(info.get('downloaded_bytes') or 0) > max_bytes:
            raise ValueError('视频超过本次下载大小限制。')
    options = {
        'progress_hooks': [progress],
        "format": "bestvideo[height<=720][vcodec^=avc1]/bestvideo[height<=720]/best[height<=720]/bestvideo/best",
        "outtmpl": output_template,
        "max_filesize": max_bytes,
        "match_filter": yt_dlp.utils.match_filter_func(f"duration <= {max_seconds}"),
        "noplaylist": True,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "socket_timeout": 10,
        "retries": 1,
        "fragment_retries": 1,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
        if not info:
            raise ValueError("视频不符合本轮时长或大小限制。")
        candidates = sorted(
            (item for item in cache_dir.glob("video.*") if item.suffix.lower() in VIDEO_TYPES),
            key=lambda item: item.stat().st_size, reverse=True,
        )
        if not candidates:
            raise ValueError("B 站没有返回可下载的视频文件。")
        video_path = candidates[0]
        duration, frames = _extract_video_frames(video_path, cache_dir / "frames", cancelled, max_seconds, frame_count)
        video_path.unlink(missing_ok=True)
        manifest = {"duration_seconds": duration, "frames": frames,
                    "title": str(info.get("title", "Bilibili 视频"))[:200]}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return manifest
    except Exception as error:
        if isinstance(error, ValueError):
            raise
        raise ValueError(f"B 站视频解析失败：{str(error)[:300]}") from error
    finally:
        for residue in cache_dir.glob('video.*'):
            if residue.is_file():
                residue.unlink(missing_ok=True)


def _read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    paragraphs = []
    for paragraph in (node for node in root.iter() if node.tag.endswith("}p")):
        value = "".join(
            node.text or "" for node in paragraph.iter()
            if node.tag.endswith("}t")
        ).strip()
        if value:
            paragraphs.append(value)
    return "\n".join(paragraphs)


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path), strict=False)
    if reader.is_encrypted:
        raise ValueError("这个 PDF 已加密，暂时无法读取。")
    if len(reader.pages) > 120:
        raise ValueError("PDF 超过 120 页，请先拆分后再发送。")
    chunks = []
    remaining = MAX_DOCUMENT_CHARS
    for page_number, page in enumerate(reader.pages, start=1):
        if remaining <= 0:
            break
        text = (page.extract_text() or "").strip()
        if text:
            block = f"[第 {page_number} 页]\n{text}"
            chunks.append(block[:remaining])
            remaining -= len(block)
    return "\n\n".join(chunks)


def prepare_attachment(source: str | Path) -> dict:
    """Copy one supported local file into the project and extract its usable content."""
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"找不到文件：{path.name}")
    extension = path.suffix.lower()
    if extension not in IMAGE_TYPES and extension not in DOCUMENT_TYPES and extension not in VIDEO_TYPES:
        raise ValueError(f"暂不支持 {extension or '无扩展名'} 文件。可发送常见图片、文档和视频文件。")
    size_bytes = path.stat().st_size
    if size_bytes <= 0:
        raise ValueError(f"{path.name} 是空文件。")
    limit = MAX_VIDEO_BYTES if extension in VIDEO_TYPES else MAX_FILE_BYTES
    if size_bytes > limit:
        raise ValueError(f"{path.name} 超过 {limit // (1024 * 1024)} MB，请压缩或拆分后再发送。")

    ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = ATTACHMENT_DIR / f"{uuid.uuid4().hex}{extension}"
    shutil.copy2(path, stored_path)

    try:
        if extension in IMAGE_TYPES:
            kind = "image"
            mime_type = IMAGE_TYPES[extension]
            extracted_text = ""
            image_reader = QImageReader(str(stored_path))
            image_size = image_reader.size()
            if not image_reader.canRead():
                raise ValueError(f"{path.name} 不是可读取的图片文件。")
            if image_size.width() > 8192 or image_size.height() > 8192:
                raise ValueError(f"{path.name} 的边长超过 8192 像素，请先缩小图片。")
        elif extension in VIDEO_TYPES:
            kind = "video"
            mime_type = mimetypes.guess_type(path.name)[0] or "video/mp4"
            duration, frames = _extract_video_frames(stored_path, ATTACHMENT_DIR / f"{stored_path.stem}_frames")
            extracted_text = json.dumps({"duration_seconds": duration, "frames": frames}, ensure_ascii=False)
        else:
            kind = "document"
            mime_type = mimetypes.guess_type(path.name)[0] or "text/plain"
            if extension == ".pdf":
                extracted_text = _read_pdf(stored_path)
            elif extension == ".docx":
                extracted_text = _read_docx(stored_path)
            else:
                extracted_text = _read_text_file(stored_path)
            if not extracted_text.strip():
                raise ValueError(f"没有从 {path.name} 中提取到可读文字。扫描版 PDF 暂不支持 OCR。")
            if len(extracted_text) > MAX_DOCUMENT_CHARS:
                extracted_text = extracted_text[:MAX_DOCUMENT_CHARS] + "\n[文档内容已截取]"
    except Exception:
        stored_path.unlink(missing_ok=True)
        shutil.rmtree(ATTACHMENT_DIR / f"{stored_path.stem}_frames", ignore_errors=True)
        raise

    return {
        "file_name": path.name,
        "kind": kind,
        "mime_type": mime_type,
        "local_path": stored_path.relative_to(BASE_DIR).as_posix(),
        "extracted_text": extracted_text,
        "size_bytes": size_bytes,
    }
