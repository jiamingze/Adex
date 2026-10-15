# 安装指南

[English](../en/installation.md) · [首页](../../README.zh-CN.md)

## 先体验界面

克隆后可先运行 `make demo-ui`（Node.js 22、pnpm 10.11.0、uv 与 Python 3.12+），打开 http://127.0.0.1:18117/today?fault=calendar-plan。无需 Java、数据库、Key 或 Xcode。此合成演示不持久保存工作，不执行真实模型或外部操作；Ctrl+C 停止，切勿公开暴露。`pnpm install` 不会自动构建 iOS，手机打包需显式执行。

## 环境选择

本地开发直接运行服务，便于阅读日志与调试；Docker Compose 用于容器部署。iOS 需要可连接的服务端、macOS 和完整 Xcode，手机本身不承担服务端运行。

## macOS 依赖

从官方渠道安装 Homebrew，然后：

```bash
brew install openjdk@21 maven node@22 pnpm uv postgresql@16 redis ffmpeg
export JAVA_HOME="$(brew --prefix openjdk@21)/libexec/openjdk.jdk/Contents/Home"
export PATH="$JAVA_HOME/bin:$(brew --prefix node@22)/bin:$PATH"
```

pnpm 使用 10.x，仓库固定 10.11.0。FFmpeg 用于媒体拼接与测试样例；Docker Desktop 或 Colima 用于隔离 Runner 和容器测试。基础聊天可直接本地运行，不要求 Docker。Ubuntu 使用对应版本的依赖，PostgreSQL 16 路径支持 `/usr/lib/postgresql/16/bin`，以普通用户运行，不能用 root 执行 `initdb`。

## 初始化

```bash
git clone https://github.com/jiamingze/Adex.git
cd Adex
make doctor
make setup
uv run python scripts/init_env.py
```

初始化生成私有随机密码与服务凭证，已有 `.env` 会保留。不要直接使用 `.env.example` 中的占位密码部署。先在 `.env` 选择 Mock 演示或真实模型配置，详见 [配置说明](configuration.md)。

```bash
make build
make up-dev
make status
```

打开 http://127.0.0.1:5173。访客可聊天，注册或登录后使用附件、自动化和创作。初始化账户信息只保存在自己的 `.env`。

本地 PostgreSQL 为 55432，Redis 为 56379；App / Automation / Agent / Tools 分别为 8080 / 8081 / 8105 / 8107，Web 为 5173。数据与日志在忽略提交的 `.local-data/`。`make down-dev` 停止业务服务，不删除数据，也不会停止基础设施。后端代码修改后须重新构建并重启服务，单独编译不会更新运行中的 JAR。

## Docker Compose

先生成 `.env` 并检查配置：

```bash
docker compose --env-file .env -f deploy/compose/compose.yaml config --quiet
docker compose --env-file .env -f deploy/compose/compose.yaml up -d --build
```

默认 Web 仅绑定本机 5173。需要 Elasticsearch 时增加 `--profile search`。容器运行需要为数据库、两个 JVM 服务、Python 服务和可选 Runner 留出内存与磁盘。文件目录与 PostgreSQL 必须共同备份；Linux 可设置 `ADEX_FILES_HOST_DIR=/data/adex/files`，部署前检查最终 Compose 配置。详见 [运维指南](../RUNBOOK.md)。

## 安装到 iPhone

1. 安装完整 Xcode 和 iOS 平台，完成系统要求的初始化。
2. 连接手机，开启开发者模式并信任电脑。
3. 准备手机可访问的 HTTPS 网关，手机的 localhost 不是电脑。
4. 构建并打开工程：

```bash
ADEX_IOS_API_URL=https://your-gateway.example uv run python scripts/prepare_ios.py
open apps/ios/ios/App/App.xcodeproj
```

5. 在 Signing & Capabilities 选择自己的 bundle identifier 和 Personal Team，选择真机运行。

免费个人签名通常七天需要续签，不分发项目作者的签名账户和证书。原生权限包括相册、相机、麦克风和语音识别；本机识别不可用时，Apple 语音服务可能使用联网处理。API 地址是编译时配置，变更后重新构建。开发用临时隧道可能失效，不等同于稳定生产部署；`scripts/public_access.py` 提供开发隧道入口。

## 常见问题

- 缺依赖：执行 `make doctor`，检查版本与 JAVA_HOME。
- 数据库失败：检查 55432、PostgreSQL 16 和项目目录权限，以普通用户运行。
- 模型拒绝：检查 Key、地域、模型名称、权限与额度；聊天权限不代表有音乐或视频权限。
- 手机无法连接：检查 HTTPS 网关、CORS、隧道有效性与打包时的 API 地址。
- 上传超时：检查网络、25 MiB 文件限制与存储配额，使用界面重试入口。
- 任务等待：检查四服务与 Worker，不要直接修改生产数据库绕过状态机。

分享日志前移除密钥、Cookie、Token、媒体票据、个人内容和设备标识。
