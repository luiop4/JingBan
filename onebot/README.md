# 鲸伴内置 OneBot 11

[← 返回项目首页](../README.md) · [接入指南](../docs/GETTING_STARTED.md#qq-接入)

完整发行版集成 **NapCat v4.18.41**，来源为 [NapCat 官方发布](https://github.com/NapNeko/NapCatQQ/releases/tag/v4.18.41)。源码仓库不包含第三方二进制运行时或账号状态；可自行准备组件，也可直接连接已有 OneBot 11 WebSocket 服务。

- `runtime/`：官方运行组件及许可证，随鲸伴签名更新一同分发。
- `../data/onebot/`：仅本机保存的配置、二维码和日志，不进入更新包。
- 打开鲸伴的“QQ 接入”，点击“启动并登录 QQ”，在页面内扫码并查看运行日志。
- 首次使用需要本机安装兼容 QQ，手机扫码和确认由用户完成。
- 若以前的外部 NapCat 仍在运行，请先退出它，或继续使用外部桥接的连接入口。
- 关闭服务请用页面内“停止服务”；鲸伴退出时也会清理它启动的桥接进程树。

完整发行目录中，原始发行包摘要见 `runtime/jingban-release.json`，上游许可证见 `runtime/LICENSE`。自行准备组件时应保留其来源与许可证。
