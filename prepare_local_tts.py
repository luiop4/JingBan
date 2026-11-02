"""Rebuild the optional, project-local Qwen TTS environment and model."""

from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
UV_EXE = PROJECT_DIR / "tools" / "uv.exe"
QWEN_ENV = PROJECT_DIR / ".qwen-venv"
RUNTIME_DIR = PROJECT_DIR / "runtime"
SOURCE_REVISION = "13ef823ffe76aec4ac7e35d3fec28ecfc8d7427a"
SOURCE_ZIP = (
    "https://github.com/dffdeeq/Qwen3-TTS-streaming/archive/"
    f"{SOURCE_REVISION}.zip"
)


def run_step(command: list[str], env: dict[str, str], label: str) -> None:
    print(label, flush=True)
    process = subprocess.Popen(
        command,
        cwd=PROJECT_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if process.stdout is not None:
        for line in process.stdout:
            print(line.rstrip(), flush=True)
    result = process.wait()
    if result:
        raise RuntimeError(f"步骤失败，退出代码 {result}：{label}")


def install_streaming_source() -> None:
    target = PROJECT_DIR / "tools" / "qwen3_tts_streaming"
    if (target / "qwen_tts" / "__init__.py").is_file():
        print("本地 Qwen 流式推理代码已存在。", flush=True)
        return

    print("正在下载 Qwen 流式推理代码…", flush=True)
    with tempfile.TemporaryDirectory(prefix="qwen-tts-source-") as temp_name:
        archive_path = Path(temp_name) / "qwen-tts.zip"
        request = urllib.request.Request(
            SOURCE_ZIP,
            headers={"User-Agent": "AIChatMemory-local-tts-installer"},
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            with archive_path.open("wb") as archive_file:
                shutil.copyfileobj(response, archive_file)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(temp_name)
        source_root = next(Path(temp_name).glob("Qwen3-TTS-streaming-*"), None)
        package_source = source_root / "qwen_tts" if source_root else None
        if package_source is None or not (package_source / "__init__.py").is_file():
            raise RuntimeError("下载的 Qwen 源码包中没有找到 qwen_tts 模块。")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(package_source, target / "qwen_tts", dirs_exist_ok=True)
        license_file = source_root / "LICENSE"
        if license_file.is_file():
            shutil.copy2(license_file, target / "LICENSE")
        (target / "UPSTREAM.txt").write_text(
            f"Upstream: https://github.com/dffdeeq/Qwen3-TTS-streaming\n"
            f"Revision: {SOURCE_REVISION}\n"
            "Downloaded after the user confirms local Qwen TTS installation.\n",
            encoding="utf-8",
        )


def main() -> int:
    if not UV_EXE.is_file():
        print("找不到项目内的 tools\\uv.exe；请先运行 setup_app.bat。", flush=True)
        return 1
    if not (PROJECT_DIR / "requirements-tts.lock.txt").is_file():
        print("找不到 requirements-tts.lock.txt。", flush=True)
        return 1

    env = os.environ.copy()
    env["UV_PYTHON_INSTALL_DIR"] = str(RUNTIME_DIR / "python")
    env["UV_PYTHON_NO_REGISTRY"] = "1"
    env["UV_CACHE_DIR"] = str(RUNTIME_DIR / "uv-cache")
    env["MODELSCOPE_CACHE"] = str(PROJECT_DIR / "models" / "modelscope-cache")
    env["HF_HOME"] = str(PROJECT_DIR / "models" / "huggingface-cache")

    try:
        install_streaming_source()
        if not (QWEN_ENV / "Scripts" / "python.exe").is_file():
            run_step(
                [str(UV_EXE), "python", "install", "3.12.15", "--no-registry", "--no-bin"],
                env,
                "正在准备项目内的 Python 3.12…",
            )
            run_step(
                [
                    str(UV_EXE), "venv", "--allow-existing", "--python", "3.12.15", "--managed-python",
                    str(QWEN_ENV),
                ],
                env,
                "正在创建本地 Qwen 虚拟环境…",
            )

        qwen_python = QWEN_ENV / "Scripts" / "python.exe"
        if not qwen_python.is_file():
            raise RuntimeError("本地 Python 环境没有创建成功。")
        run_step(
            [
                str(UV_EXE), "pip", "install", "--python", str(qwen_python),
                "--extra-index-url", "https://download.pytorch.org/whl/cu128",
                "-r", str(PROJECT_DIR / "requirements-tts.lock.txt"),
            ],
            env,
            "正在安装本地语音依赖和 CUDA 版 PyTorch…",
        )
        run_step(
            [str(qwen_python), str(PROJECT_DIR / "download_qwen_model.py")],
            env,
            "正在下载 Qwen3-TTS 模型…",
        )
        if not (PROJECT_DIR / "models" / "Qwen3-TTS-12Hz-0.6B-Base" / "config.json").is_file():
            raise RuntimeError("模型下载未完成。请再次点击“安装本地语音”继续配置。")
        model_dir = PROJECT_DIR / "models" / "Qwen3-TTS-12Hz-0.6B-Base"
        if not any(model_dir.glob("*.safetensors")):
            raise RuntimeError("模型权重未下载完成。请重试安装。")
        # 只有所有安装步骤成功才写入标记，取消或失败的安装不能被误判为可用。
        (model_dir / ".installation-complete.json").write_text(
            json.dumps({"source_revision": SOURCE_REVISION, "complete": True}), encoding="utf-8"
        )
    except Exception as error:
        print(f"本地语音配置失败：{error}", flush=True)
        return 1

    print("本地 Qwen 语音环境和模型已准备好。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
