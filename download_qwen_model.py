"""Download Qwen3-TTS into this project and point the app at the local copy."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
MODEL_DIR = PROJECT_DIR / "models" / "Qwen3-TTS-12Hz-0.6B-Base"
CONFIG_PATH = PROJECT_DIR / "config.json"


def main() -> int:
    MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(Path(sys.executable).parent / "modelscope.exe"),
        "download",
        "--model",
        "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        "--local_dir",
        str(MODEL_DIR),
    ]
    try:
        subprocess.run(command, cwd=PROJECT_DIR, check=True)
    except FileNotFoundError:
        print("找不到 ModelScope 下载程序，请重新运行 setup_qwen_tts.bat。")
        return 1
    except subprocess.CalledProcessError as error:
        print(f"模型下载失败，错误代码：{error.returncode}。重新运行本脚本可继续下载。")
        return error.returncode or 1

    if not (MODEL_DIR / "config.json").is_file():
        print("下载完成后没有找到模型配置文件，请检查下载器输出。")
        return 1
    if not CONFIG_PATH.exists():
        print("请先运行一次 main.py 生成 config.json，再运行本脚本。")
        return 1

    try:
        settings = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("config.json 无法读取。模型已下载，但没有改动 API 设置。")
        return 1
    voice = settings.setdefault("voice", {})
    voice["model_id"] = MODEL_DIR.relative_to(PROJECT_DIR).as_posix()
    voice.setdefault("device", "auto")
    voice.setdefault("dtype", "auto")
    CONFIG_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    print("模型路径已写入 config.json；API 密钥和其他设置已保留。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
