# 运维与恢复

## 配置边界

`.env` 必须保持 0600 且不纳入 Git。Agent 获取 MiniMax 密钥，Tools 获取 Tavily、视觉、CalDAV 配置，App 获取 SMTP；每个服务使用自己数据库角色，内部请求按 issuer / audience / scope / owner / resource 签名。生产凭证由部署环境注入。

不要将 `.env`、日志、备份或 `.local-data` 加入 Docker 镜像。模型调用和工具账务为 PG 数据。日志只记录请求元数据，媒体票据和预览票据路径已脱敏。

## 本地启动与诊断

执行 `make up-dev`，通过 `make status` 检查四服务 `/health/ready`。Web 是 5173，App 8080，Automation 8081，Agent 8105，Tools 8107。开发进程与日志在 `.local-data`；Java 运行文件复制到 `.local-data/runtime`，编译不会改写已运行进程的 JAR。

Colima 的本项目 profile 为 `adex`。当前机器有独立 Docker 配置以避免覆盖原有 Docker Desktop 凭证配置：

```sh
export DOCKER_CONFIG="$PWD/.local-data/docker-config"
export DOCKER_HOST="unix://$HOME/.colima/adex/docker.sock"
docker compose --env-file .env -f deploy/compose/compose.yaml config --quiet
```

本地 ES 开发容器是 `adex-local-es`，绑定 127.0.0.1:59200。生产应使用受保护内网或配置 `ADEX_ES_API_KEY`；不要公开未启用认证的 ES。

## 故障处理

- Redis 不可用：权威上下文继续从 App PG 获取，L1 变成缓存未命中；恢复后自然重建。
- ES 不可用：聊天、记忆与任务继续运行，索引 outbox 重试。检索退回 PG。删除后的 ES 文档保留空内容墓碑，不能用旧索引恢复记忆。
- PG 不可用：返回受控不可用错误，拒绝持久写入。不得用内存队列补充未经提交的状态。
- Worker 中断：等待租约过期，后续 attempt 使用更高 epoch。只恢复 Automation 已 CAS 提交引用的 immutable checkpoint；孤儿 checkpoint 只做诊断。
- 模型/外部动作 UNKNOWN：禁止自动重新下单或发送。日历可使用用户发起的对账查询，验证既有 UID、时间和标题；查询不到不代表之前未执行。
- 媒体已有 provider_job_id：查询旧 job 并以同一文件幂等键导入；无供应商回执的 UNKNOWN 不盲目提交。Mock 可重复查询确定性既有作品；真实供应商须按其对账能力实现适配器。
- 删除会话：取消交互 turn、递增记忆修订、删除对应摘要，关联长期记忆以墓碑删除；延迟抽取与后台结果会消费并丢弃，不再回填。
- 通知或结果重复：消费事件和用户消息同一 PG 事务去重，同一 Run 也做逻辑去重。

## 文件和备份

文件在私有目录按 UUID 分片，临时文件 fsync → PENDING 元数据 → atomic rename → READY。下载校验大小及 SHA-256，媒体支持鉴权票据和 Range。清理器只在 PG 可用时处理过期未完成上传、孤儿对象和已删除文件；已删除文件留 24 小时再清理。

一致性备份采用短暂停写，不声称零停机：

```sh
make down-dev
uv run python scripts/backup.py
uv run python scripts/restore_drill.py .local-data/backups/<备份目录>
make up-dev
```

恢复演练在新 `adex_restore_*` 数据库中验证数据计数、checkpoint 哈希、READY 文件大小和哈希。生产除 PG 和文件外还需要独立保存角色、部署配置及受保护密钥；本地备份不等于异地灾备。不要对生产数据库运行故障测试。

## 外部动作及上线条件

CalDAV 配置 HTTPS URL、用户名、密码和明确授权的 `ADEX_CALDAV_OWNER_ID`；用户在 Web 批准草稿，App 创建持久 CALENDAR Run，Tools 执行前校验租约与草稿对应关系。审批可撤销；已下发结果未知时使用查询对账。

SMTP 配置服务端账号、From 和必需 STARTTLS，用户显式开启邮件并填写收件地址；每天每用户最多 20 封。发送前写入 IN_FLIGHT，超时或中断变 UNKNOWN，不能因重试制造重复邮件。

ECS 上线尚需实际主机、域名、TLS、合法网络可达性和恢复演练。Compose 只公开 Web 网关；服务角色、数据库、Redis、ES 保持内网。上传反向代理限制为 26MiB，普通请求由 App 控制更小上限，SSE 禁止缓冲。

### TLS 网关配置

部署目录中提供可选 `deploy/compose/compose.tls.yaml` 与 Caddyfile。实际域名 DNS 指向 ECS、80/443 入站开放后，设置 `ADEX_PUBLIC_DOMAIN`，把公共 HTTPS origin 加入 `ADEX_ALLOWED_ORIGINS`，再合并两份 Compose 启动。Caddy 将 HTTPS scheme 转发到内网，App 识别 forwarded headers；Web 自身端口始终只绑 127.0.0.1。此配置尚未在 ECS/真实域名执行，不代表已上线。参考 [Docker daemon proxy 文档](https://docs.docker.com/engine/daemon/proxy/) 处理开发 VM 的镜像网络问题，代理不应作为产品外部接口绕行策略。

### 生产代码沙箱

提供可选 `deploy/compose/compose.runner.yaml`：Tools 只向内部固定策略 Gateway 发签名请求，Docker socket 仅挂到 Gateway，不共享给业务服务或生成代码。Gateway 不持有 PG/模型密钥；只允许运行固定 Runner 镜像，2 个并发、16 秒总期限、无网络、只读、0.5 CPU、512MiB、64 PID，结束后强制清理。Gateway 不能暴露公网；Docker socket 权限等同主机高权限，需单独保护这一受控组件。

先构建 `runners/code/Dockerfile` 对应 `adex-code-runner:local`，配置随机 `ADEX_RUNNER_KEY`、绝对 `ADEX_RUNNER_HOST_DIR`（ECS 可用 `/data/adex/runner-tmp`）和实际 socket group GID，再合并 Runner Compose。Gateway 的临时目录必须与 Docker 主机同路径挂载。不要向请求开放镜像名、命令、网络或卷参数。

## 本机独立容器验收

本次使用项目 `adex-acceptance`、独立数据库 `adex_container_acceptance`、Web 15173 和独立文件目录，模型为 Mock，不会混用 native 用户数据库。私密验收配置在 `.local-data/compose-validation.env`，镜像覆盖在 `.local-data/compose-images.yaml`。已执行 `uv run python scripts/verify_compose.py`，覆盖真实就绪检查、持久聊天、私有文件/Range、强制重建 App、文件 SHA 与容器 Runner；不要把此 Mock 验收当作外部供应商验收。Nginx 使用 Docker 内置 DNS 定时刷新服务地址。

验收完成后 Compose 停止，保留其测试卷；原生 Web 5173 与本地 PG/Redis/ES 继续运行。故障测试不针对这个或用户数据库，而是新建 `adex_test_*`。

## 本机外网 HTTPS 访问

本机安装的 cloudflared Quick Tunnel 将 `127.0.0.1:4173` 构建后的 Vite Preview 暴露为 HTTPS。仅开放网页与其 `/api` 代理；App/Automation/Agent/Tools、Redis、PostgreSQL 不直接公开。Vite 仅允许本次生成的精确域名，账户和私有会话继续由 App 鉴权。外网使用 Secure + HttpOnly 会话 Cookie，API Key 不下发客户端。

- 启动：`uv run python scripts/public_access.py start`（先运行本机服务及 `make build`）
- 查看当前链接：`uv run python scripts/public_access.py status`
- 关闭外网入口：`uv run python scripts/public_access.py stop`
- 日志：忽略目录 `.local-data/public-tunnel.log`、`.local-data/public-web.log`

电脑及服务进程需保持运行；Quick Tunnel 重启后域名变化，不是固定域名部署。要固定域名需用户自有 Cloudflare 域名和账户配置。

### Alibaba music/video configuration

Keep `DASHSCOPE_API_KEY` in private `.env`. Copy the Beijing workspace hostname from the logged-in console API example into `DASHSCOPE_MEDIA_BASE_URL` (`https://<workspace-id>.cn-beijing.maas.aliyuncs.com/api/v1`). Use `ADEX_MUSIC_PROVIDER=dashscope`, `DASHSCOPE_MUSIC_MODEL=qwen-audio-3.1-tts-next`, `ADEX_VIDEO_PROVIDER=dashscope`, `DASHSCOPE_VIDEO_MODEL=wan3.0-video`; restart App/Agent/Tools after changes. Chat retains its OpenAI-compatible Qwen endpoint.

Original audio requests up to 120 seconds use one provider call; longer requests up to 600 seconds use durable original sections and local ffmpeg crossfades. Requires ffmpeg/ffprobe. Each top-level composition counts once against `ADEX_MEDIA_DAILY_LIMIT` (default 5, local validation environment 10); sections have separate effect ledgers. An UNKNOWN child is never automatically resubmitted. If the synchronous audio response is lost, investigate the vendor request before a new paid request.

Video tasks save the vendor task ID before polling; restoring a known video task queries that ID. Generated files persist to App local storage, not to provider public URLs. Conversations expose owner-bound expiring playback tickets only.
