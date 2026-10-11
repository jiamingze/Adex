# 配置说明

[English](../en/configuration.md)

首次执行 `uv run python scripts/init_env.py` 生成私有 `.env`。`.env.example` 只用于参考，不是可直接部署的凭证。文件权限保持 0600，不向客户端、截图或 Git 提交密钥。

| 配置 | 用途 |
| --- | --- |
| `ADEX_MODEL_PROVIDER` | `mock`、`minimax` 或 `qwen` |
| `MINIMAX_API_KEY` / `MINIMAX_MODEL` / `MINIMAX_BASE_URL` | MiniMax 聊天凭证、模型和地址 |
| `DASHSCOPE_API_KEY` / `DASHSCOPE_CHAT_MODEL` / `DASHSCOPE_CHAT_BASE_URL` | Qwen 聊天凭证、模型和兼容接口 |
| `TAVILY_API_KEY` | 自动联网搜索 |
| `ADEX_MUSIC_PROVIDER` / `ADEX_VIDEO_PROVIDER` | 媒体供应商或 Mock |
| `DASHSCOPE_MUSIC_MODEL` / `DASHSCOPE_VIDEO_MODEL` / `DASHSCOPE_MEDIA_BASE_URL` | 阿里云媒体模型与地域接口 |
| `ADEX_BACKGROUND_WORKER` | 持久后台 Worker |
| `ADEX_FILE_STORAGE_ROOT` | App 私有本地文件目录 |
| `ADEX_ES_URL` | 可选 Elasticsearch |
| `ADEX_ALLOWED_ORIGINS` | 明确允许的客户端 origin |
| `ADEX_IOS_API_URL` | iOS 打包脚本使用的公共 HTTPS 网关 |

聊天界面暂时提供 Qwen 与 MiniMax，实际模型名称必须在账户和地域中可用。文字 Key 不意味着具有音乐或视频权限。当前媒体适配包含 DashScope、MiniMax 音乐和本地 ACE-Step，启用付费调用前阅读 `creative.py` 和对应供应商模块。Mock 用于确定性学习与测试，不代表真实生成。

SMTP 和需审批的 CalDAV 为可选能力，见 `.env.example` 和供应商接入清单。各服务签名 Key 和数据库密码必须独立，部署时配置预算与配额。初始化账户随机生成，不使用开发者的本机账户。

修改环境后重启相关后端；修改外网 API 地址后重新打包 iOS。切换供应商前检查尚未完成的 Job 和 UNKNOWN 效果，避免失去对账能力。
