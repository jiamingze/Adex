# Development and deployment: MacBook + Alibaba Cloud ECS

## MacBook development

- Install matching Java 21, Python 3.12+, uv, Node LTS/pnpm, Docker Desktop or equivalent and current Xcode. Keep versions in `docs/versions.md` after milestone M00.
- Web: local React Vite; local PG+Redis+ES via Compose profile; bind-mount `./.local-data/files` into App as `/var/adex/files`.
- iOS: Capacitor / Xcode. Choose Apple Account Personal Team, install on your own iPhone. Free provisioned builds expire after 7 days and must be rebuilt/reinstalled periodically. No paid Apple Developer Program is required for personal device testing; it **does not entitle native APNs/TestFlight**.
- Online: iOS/Web requests go to the App BFF over HTTPS; never expose internal services or database ports to public Internet.

## Alibaba Cloud ECS deployment

- Use Git checkout / versioned image tags + Compose rather than editing the live deployment tree with an AI agent.
- Use a dedicated user (not root), source directory separate from `/opt/adex` deployment configuration and persistent storage volumes.
- Minimize ingress to 443, restrict SSH security group, keep PG/Redis/ES private; internal API scope auth even on single host.
- All images/videos/audio/files/reports/games/browser evidence are stored **on ECS disk** under `/data/adex/files`, not OSS/MinIO. Prefer an attached data disk independent of the OS/container layer; App owns the file API and ACL.
- Local disk only survives normal restarts and container recreation. PG+files need disk snapshots or off-host backup and an actual restore drill; ECS/data-disk destruction without backup causes permanent loss.
- Container `adex-app` must bind mount `/data/adex/files:/var/adex/files`; do not expose private media directory as public static files.
- ES + Java services + Python + browser runners may require 8vCPU/32GiB; 4vCPU/16GiB may work for restricted test profiles but is **not validated**. Run a resource profiler before choosing production size.
- Running Codex on ECS is optional. Domestic CLI alternatives also do not get credentials to production DB by default.
- Check local and cloud LLM API terms and network/region availability. Use replaceable Provider adapters, do not assume services unsupported in a region work via proxy.

## iPhone background notifications

- While app is active: SSE + persistent notification center.
- Inactive: email fallback and optional iOS 16.4+ **Home Screen PWA** Web Push with proper permission and HTTPS, which is distinct from native app APNs.
- Always persist task outcome in original conversation; app startup should sync via cursor, irrespective of push delivery.

Official references: https://developer.apple.com/help/account/basics/about-your-developer-account ; https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers

### 本机服务与 iPhone 外网连接

先运行 `uv run python scripts/public_access.py start`，再运行 `uv run python scripts/prepare_ios.py`。iOS 独立资源目录为 `apps/ios/web-dist`，API 使用 `.local-data/public-url.txt` 中的 HTTPS 公网地址，也可通过 `ADEX_IOS_API_URL` 指定固定 HTTPS origin。不会覆盖 Web dist。Native 端启用消息快照轮询以兼容隧道 SSE 限制。Quick Tunnel 地址改变后需重新打包安装；本机服务和隧道必须持续运行，电脑睡眠时无法访问。

真机安装前需完成 Xcode 许可及首次组件初始化，在 Xcode Accounts 登录 Apple 账号并选择 Personal Team，连接并信任 iPhone，按系统要求开启开发者模式。只有 devicectl 安装及启动成功才视为真机完成。
