# 开发与扩展

[← 返回项目首页](../README.md) · [源码启动](GETTING_STARTED.md)

## 项目结构

| 文件 / 目录 | 职责 |
| --- | --- |
| `main.py`、`chat_flow.py`、`chat_tools.py` | 桌面入口、对话编排与模型工具 |
| `database.py`、`standard_memory.py`、`history_search.py` | SQLite 存储、事件整理与历史检索 |
| `memory_scheme.py`、`STANDARD_MEMORY.md` | 记忆方案界面和技术规则 |
| `companion_life.py`、`companionship.py`、`heartbeat_panel.py` | 持续打算、主动行为与心跳工作区 |
| `cross_channel.py`、`interaction_modes.py` | QQ / 桌面接续与普通 / 工作模式 |
| `qq_*.py`、`onebot_*.py` | QQ 消息、资料、空间和桥接生命周期 |
| `browsing.py`、`browser_link.py`、`autonomous_video.py` | 网页浏览、日常浏览器接入与视频活动 |
| `evidence_guard.py`、`tool_context.py` | 工具回执与后续对话的来源衔接 |
| `plugin_manager.py`、`plugin_sdk.py` | 原生 Python 插件和开发接口 |
| `dsh_*.py`、`whale_widget_host.py` | DSH 兼容、历史导入与透明挂件 |
| `*.ui`、`ui_*.py` | Qt Designer 界面与生成模块 |
| `assets/` | 品牌图形、角色资料和界面资源 |
| `website/` | 当前宣传网站静态文件 |
| `build_clean_release.py`、`build_installer.py` | 纯净发行目录与 Windows 安装包 |

## 修改界面

使用 Qt Designer 编辑 `.ui`，再生成对应 Python 模块，例如：

```powershell
.\.venv\Scripts\pyside6-uic.exe chat_window.ui -o ui_chat_window.py
```

界面行为写在逻辑模块里。直接编辑 `ui_*.py` 的改动会在重新生成时覆盖。

## 原生插件

在 `plugins/my_plugin/` 放置 `plugin.json` 与 `main.py`，或在应用插件页导入文件夹。首次导入默认停用，启用后才执行。

```json
{
  "id": "my_plugin",
  "name": "我的插件",
  "version": "1.0.0",
  "api_version": 1,
  "entry": "main.py",
  "permissions": []
}
```

```python
class Plugin:
    def __init__(self, context):
        self.context = context

    def start(self):
        self.context.notify("插件已启动")

    def stop(self):
        pass

def create_plugin(context):
    return Plugin(context)
```

`context` 提供独立设置与数据目录、窗口生命周期托管、消息草稿和事件订阅。完整接口在 [`plugin_sdk.py`](../plugin_sdk.py)，应用里的「开发说明 / 模板」也能查看并生成模板。订阅聊天事件需在清单声明 `chat_events`。

停用时应释放线程、网络请求和计时器，不阻塞界面。插件是受信任的本地 Python 代码，与应用具有相同系统权限。

## DSH 插件与历史

兼容层提供导入、依赖准备和独立界面；桌宠及网页挂件可能需要额外 Node / Electron / 网页构建依赖。兼容范围由插件使用的接口决定，不承诺所有插件即导即用。用户安装的插件及其运行数据不进入本仓库。

历史导入与插件运行是不同入口，导入前先预览记录范围。相关实现分别在 `dsh_history.py`、`dsh_packages.py` 和 `dsh_runtime.py`。

## 构建发行包

`生成安装包.bat` 会先组装纯净发行目录，再调用安装包构建脚本。制作电脑需要准备完整的便携 Python 环境、应用依赖、FFmpeg、uv、启动器 EXE 和可分发的 OneBot 组件；这些不是源码仓库附送的内容。Windows 安装器还需要 Inno Setup 7。

因此，“能从源码运行基础聊天”与“已满足完整发行包构建要求”是两件事。各脚本的 `--help` 可查看参数，详细发行过程保留在 [历史参考](REFERENCE.md)。

版本由 `version.json` 管理。`CHANGELOG.txt` 被应用的「关于」页面读取，请保留其 `v数字版本` 的标题格式；[CHANGELOG.md](../CHANGELOG.md) 是便于 GitHub 阅读的对应版本。

## 更新签名

客户端验证公钥位于 `update_trust.py`。`publish_update.py` 只生成静态签名更新文件，不负责上传；签名私钥必须由发布者在仓库之外保存。自行维护更新通道时，应使用自己的签名密钥和对应客户端公钥。

## 反馈与贡献

提交问题时提供版本、重现步骤、预期行为和脱敏错误信息。修改记忆逻辑时注意原消息来源、身份隔离与删除关联；修改跨端发送时注意真实回执、超时结果和重复发送；涉及界面时附上清楚的前后截图。

发布前可先用 `git status` 检查将要提交的文件。不要提交真实配置、数据库、浏览器会话、插件私有数据或发行签名私钥。
