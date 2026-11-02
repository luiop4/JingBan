# 可选运行组件

[← 源码启动指南](../docs/GETTING_STARTED.md)

仓库保存应用源码与公开界面资源，便携 Python、可执行文件、语音模型和第三方运行时按需准备。

| 组件 | 用途 | 获取来源 / 放置位置 |
| --- | --- | --- |
| uv | `setup_app.bat` 和本地语音环境管理 | [astral-sh/uv](https://github.com/astral-sh/uv/releases)，Windows x86_64 的 `uv.exe` 放在 `tools/uv.exe` |
| FFmpeg / ffprobe | 视频画面抽取与媒体处理 | [FFmpeg 官方下载入口](https://ffmpeg.org/download.html)，放在 `tools/ffmpeg/bin/` 或加入系统 PATH |
| NapCat | 内置 OneBot 11 桥接 | [NapCat 官方发布](https://github.com/NapNeko/NapCatQQ/releases/tag/v4.18.41)，组件目录为 `onebot/runtime/` |
| Qwen 本地语音 | 可选语音合成与参考音频克隆 | 通过应用内「安装本地语音」准备，依赖单独存放 |

基础源码启动可直接使用系统 Python 和 `.venv`，无需先准备 uv。若选择现有 `setup_app.bat`，需先放好 `tools/uv.exe`；该脚本使用托管 Python 3.12.15 建立 `.app-venv`，与 `runtime/python` 配合用于便携启动。

第三方组件的许可证与再分发要求分别适用；制作发行包时保留各上游的许可证和来源信息。
