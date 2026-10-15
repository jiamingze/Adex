<div align="center">

![Adex](docs/assets/banner.svg)

**支持多用户、长短期记忆与可靠 Agent 执行的开源 AI 工作空间。**

[English](README.md) · [简体中文](README.zh-CN.md) · [安装指南](docs/zh-CN/installation.md) · [技术架构](docs/zh-CN/architecture.md) · [参与贡献](CONTRIBUTING.md)

[![CI](https://github.com/jiamingze/Adex/actions/workflows/core.yml/badge.svg)](https://github.com/jiamingze/Adex/actions/workflows/core.yml)
![Java](https://img.shields.io/badge/Java-21-ED8B00)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB)
![React](https://img.shields.io/badge/React-19-61DAFB)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

Adex 是支持多用户的开源、自托管 AI 应用，提供 Web 与 iOS 客户端。它将流式聊天、长短期记忆、自主联网检索、定时执行和创作作品连接在一个私有工作空间中。后端由四个职责明确的服务组成，将用户数据、Agent 执行、自动化调度与工具调用分开，支持服务独立部署和后台任务中断恢复。

## 项目核心特色

| 核心能力 | 已实现的工程机制 |
| --- | --- |
| **AI 回复转笔记** | 一键生成标题并整理正文，校验后保存到私有笔记；按用户与源消息去重，生成失败不创建空笔记，明确保存的副本独立于原会话保留。 |
| **笔记与日程概览** | 私有笔记支持搜索、置顶、版本冲突保护；今日模块独立加载并复用缓存，合并待处理事项并展示最近 24 小时的任务结果；iPhone 本地会议按实际元数据展示邀请人和地点。笔记暂不与 Apple 备忘录同步。 |
| **多用户与数据隔离** | 支持访客、注册和登录；会话、记忆、定时任务、文件与作品按用户归属校验。内部服务调用同时验证凭证范围和资源所有权。 |
| **长短期三层记忆** | L1 为 Redis 工作上下文，L2 为持久会话历史与摘要，L3 为带来源的用户长期事实。支持查看、纠正和删除，通过删除标记与版本校验阻止旧提取任务恢复已删除记忆。 |
| **分布式服务架构** | Java / Python 四个服务可独立部署，各自拥有 PostgreSQL 数据域。调度器与 Worker 使用数据库抢占、租约和 fencing 协作，已有多调度实例竞争的集成测试。 |
| **可恢复 Agent 执行** | 使用不可变 Checkpoint、执行 attempt 与权威检查点引用恢复任务；记忆、Checkpoint 和任务运行状态分别管理。 |
| **持久化自动化** | 从对话创建定时任务和后台任务，关闭客户端后继续执行；唯一调度 occurrence、Outbox 与去重交付将结果送回原会话。 |
| **模型与工具可扩展** | Qwen / MiniMax 聊天、Tavily 搜索、服务端浏览器读取和可配置的图片／音乐／视频适配器；工具效果账本对不确定的供应商请求进行对账，避免盲目重复提交。 |
| **私有、可追溯的作品空间** | 文件访问权限、不可变作品版本、私有媒体播放、可编辑图形源文件，以及隔离的生成代码执行。 |
| **可学习的完整后端工程** | 按能力划分模块，分离应用服务、持久化接口与供应商适配器，并用架构检查、格式门禁和集成／故障测试约束实现。 |

**外部服务状态：** Google／APNs 集成测试使用明确标注的本地测试夹具，不代表真实账户已修改或手机已收到推送。缺少 OAuth／APNs 凭证时返回 `BLOCKED_EXTERNAL`。当前 Google 授权从 Web 发起，iOS 登录同一注册账户后可使用这些连接。

**分布式部署边界：** 已实现服务拆分与多实例协调，仓库附带的 Compose 是单机部署起点。一期文件仍存放在 App 管理的持久本地磁盘；跨主机部署多个 App 实例时，需要明确的文件路由或经架构决策批准的存储方案，多个独立本地磁盘不等于共享存储或自动高可用。详见 [技术架构](docs/zh-CN/architecture.md) 与 [文件存储约定](docs/LOCAL_FILE_STORAGE.md)。

**项目阶段：早期开发，持续迭代。** 已有可运行服务和测试，但不代表全部功能已达到生产验收标准。真实模型能力需要配置自己的供应商凭证；具体证据与限制见 [实现状态](docs/IMPLEMENTATION_STATUS.md) 和 [验收记录](docs/ACCEPTANCE_EVIDENCE.md)。

## 功能

| 模块 | 使用体验 |
| --- | --- |
| 今日概览 | 汇集重点待办、接下来的自动任务、待确认操作、主动建议、后台工作和近期成果；生成可编辑的今日计划聊天草稿 |
| 聊天 | 流式回复、Qwen / MiniMax 切换、Markdown、历史删除、停止与重试 |
| 联网搜索 | 根据问题自行搜索最新资料，通过 Tavily 返回来源 |
| 浏览器访问 | 服务端打开公开 HTTPS 网页、读取动态渲染正文与有限同域链接，返回来源与时间；无登录状态、只读，阻止内网访问 |
| 记忆 | 工作态、会话和长期记忆；查看、纠正与删除 |
| 定时执行 | 从聊天创建每日任务，管理任务和运行记录，结果回到原会话 |
| 连接服务 | Google Calendar / Gmail OAuth、增量授权、凭证加密、查询与撤销；真实连接需自行配置 OAuth |
| 操作审批 | 查看具体日历变更或邮件内容，明确批准后执行，以供应商回执确认结果，未知结果先对账 |
| 主动助手 | 日历冲突、重要邮件变化、事件去重与关联、重要性评估和通知偏好；持续检查复用 Automation |
| 任务四象限 | 按重要／紧急整理待办，移动象限、完成与删除任务，可关联已有 Run |
| 离线通知 | APNs HTTP/2 适配、私有设备登记和原会话／Run／操作恢复；真实推送需具备相应 Apple 签名和凭证 |
| 创作 | 研究报告、旅游行程、沙箱 HTML 游戏、可编辑图形与媒体作品 |
| 原创音乐与视频 | 配置真实模型后生成，保存私有作品、播放和下载 |
| 附件 | 图片、文档上传与问答；iOS 原生相册和语音桥接 |
| 作品空间 | 文件权限、版本历史、预览与导出 |

图片生成是否可用取决于适配器配置。Mock 媒体明确标注为测试样例，不会冒充真实生成结果。商业音乐目录只能跳转授权平台，检索结果不等于站内播放授权。iOS 相册上传、麦克风识别和键盘交互仍需按实际设备验证，最新边界记录在实现状态文档中。

## 示例界面

从看清今天的安排，到讨论方案、处理待办、留下笔记，形成连续的个人助手体验。
以下截图**全部采用虚构演示数据**，由隔离的本地演示服务提供，不读取个人账号、聊天、日历或文件。日历和任务结果仅展示界面，不代表真实外部服务执行成功。这些是 Web 截图，不是 iOS 真机验收截图。

### 手机端体验

390 × 844 手机视口，浅色主题；全部为虚构演示数据，展示移动端 Web 布局。

| 今日 | 聊天 | 待办 | 笔记 |
| --- | --- | --- | --- |
| [<img src="docs/images/gallery/today-mobile.jpg" alt="今日 · synthetic mobile demo" width="195" />](docs/images/gallery/today-mobile.jpg) | [<img src="docs/images/gallery/chat-mobile.jpg" alt="聊天 · synthetic mobile demo" width="195" />](docs/images/gallery/chat-mobile.jpg) | [<img src="docs/images/gallery/tasks-mobile.jpg" alt="待办 · synthetic mobile demo" width="195" />](docs/images/gallery/tasks-mobile.jpg) | [<img src="docs/images/gallery/notes-mobile.jpg" alt="笔记 · synthetic mobile demo" width="195" />](docs/images/gallery/notes-mobile.jpg) |

### 桌面端体验

| Today · 一眼看清今天 | 聊天 · 让回答成为积累 |
| --- | --- |
| [![今日概览](docs/images/gallery/today.jpg)](docs/images/gallery/today.jpg) | [![聊天](docs/images/gallery/chat.jpg)](docs/images/gallery/chat.jpg) |
| 集中查看优先待办、待审批事项和接下来的会议。 | 阅读结构化 Markdown，将有价值的回复一键转成私有笔记。 |
| **待办 · 分清轻重缓急** | **笔记 · 留住想法与方案** |
| [![待办](docs/images/gallery/tasks.jpg)](docs/images/gallery/tasks.jpg) | [![笔记](docs/images/gallery/notes.jpg)](docs/images/gallery/notes.jpg) |
| 重要性与紧急程度独立标记，支持搜索、完成状态筛选。 | 支持搜索、置顶、编辑与带版本校验的保存。 |

点击图片查看原图。[安全复现和更新截图](docs/product/screenshot-gallery.md)。

## 快速开始

需要 Git、Java 21、Maven、Node.js 22、pnpm 10、Python 3.12+、uv、PostgreSQL 16 和 Redis。本地基础设施脚本支持 macOS/Homebrew 与 Ubuntu PostgreSQL 16 路径，使用普通用户运行。

```bash
git clone https://github.com/jiamingze/Adex.git
cd Adex
make doctor
make setup
uv run python scripts/init_env.py
```

初始化会生成 `.env` 中的私有密码和服务凭证，已有配置不会被覆盖。仅学习代码时，可在 `.env` 设置 `ADEX_MODEL_PROVIDER=mock`、`ADEX_MUSIC_PROVIDER=mock`，无需真实模型 Key；测试回复会明确标注。真实聊天配置 MiniMax 或 Qwen，联网搜索另行配置 Tavily，详见 [配置说明](docs/zh-CN/configuration.md)。

```bash
make build
make up-dev
make status
```

打开 **http://127.0.0.1:5173**。访客可以聊天，附件、定时和创作需要注册或登录。初始化账户凭证保存在自己的 `.env`，项目没有公开通用密码。

```bash
make down-dev
```

依赖安装、Docker Compose、iOS 签名及排错请阅读 [完整安装指南](docs/zh-CN/installation.md)。外网访问需使用有身份验证的 HTTPS 网关，数据库与内部接口不能直接公开。

## 技术结构

```mermaid
flowchart LR
  UI[React Web / Capacitor iOS] --> App[App · Java 21]
  App --> Agent[Agent · Python]
  App --> Auto[Automation · Java 21]
  Auto --> Agent
  Agent --> Tools[Tools · Python]
  Tools --> Provider[模型 / 搜索 / 媒体]
  Tools --> Runner[隔离执行 Runner]
  App --> PG[(PostgreSQL)]
  Auto --> PG
  Agent --> PG
  Tools --> PG
  Agent --> Redis[(Redis 缓存)]
  App --> ES[(Elasticsearch 索引)]
  App --> Files[私有本地文件存储]
```

四个业务服务分别拥有自己的数据边界。PostgreSQL 是权威存储，Redis 和 Elasticsearch 可重建。普通聊天保持交互式执行，耗时任务交给 Automation，通过租约、fencing epoch、Checkpoint 和 Outbox 恢复与交付。详见 [技术架构](docs/zh-CN/architecture.md)。

## 目录与学习路线

| 目录 | 内容 |
| --- | --- |
| `apps/web` / `apps/ios` | React 客户端、Capacitor 容器和 Swift 桥接 |
| `services/adex-app` | 账户、聊天、记忆、文件及公共 API |
| `services/adex-automation` | 调度、持久任务、租约与结果交付 |
| `services/adex-agent` | 意图路由、上下文、模型和 Checkpoint |
| `services/adex-tools` | 联网、旅游、研究、媒体和工具效果账本 |
| `packages` / `migrations` | 共享 UI、契约、内核和分域数据库迁移 |
| `runners` / `deploy` | 隔离执行、Compose、镜像和网关 |
| `scripts` / `docs` | 环境初始化、测试、备份恢复、设计和验收证据 |

推荐先阅读 [开发与学习指南](docs/zh-CN/development.md)，再从 `apps/web/src/api.ts` 追踪 `conversation/ConversationService`、`PostgresConversationStore`、`ChatWorker` 到 `adex_agent/api/chat.py` 和 `execution/interactive.py`，最后学习自动化调度和工具幂等。

## 测试

```bash
make test
make check-style
make test-contract
make test-integration
uv run python scripts/check_secrets.py
```

集成测试使用独立 `adex_test_*` 数据库与 Mock 外部能力，不用个人 Key 执行付费模型请求。部分检查需要 Docker 和本机基础设施。

## 更多文档

- [Connector、统一审批、主动建议与 APNs 接入](docs/architecture/proactive-assistant.md)
- [Skill 架构与行程／预约／下单演进](docs/architecture/skills.md)
- [安装](docs/zh-CN/installation.md)、[配置](docs/zh-CN/configuration.md)、[开发](docs/zh-CN/development.md)
- [运维与恢复](docs/RUNBOOK.md)、[文件存储](docs/LOCAL_FILE_STORAGE.md)
- [路线图](ROADMAP.md)、[更新记录](CHANGELOG.md)、[安全说明](SECURITY.md)
- [原始设计](docs/Adex_Product_Technical_Design_v4.1.md)、[验收门禁](docs/ACCEPTANCE.md)

## 一起参与开发

欢迎大家一起把 Adex 做得更好，无论你是刚开始学习，还是有工程经验，都可以参与代码开发、界面设计、设备测试、文档完善和需求讨论。可以先看看 [路线图](ROADMAP.md)、[现有问题](https://github.com/jiamingze/Adex/issues) 和 [贡献指南](CONTRIBUTING.md)。较大的功能建议先开 Issue 讨论范围，小修复和文档改进欢迎直接提交 PR。

欢迎提交可复现问题、设备测试、供应商适配器和文档改进。参与前请阅读 [贡献指南](CONTRIBUTING.md)。安全问题请按 [安全策略](SECURITY.md) 私下报告。

Adex 独立开发，不隶属于 OpenAI、阿里云或 MiniMax。供应商名称仅用于说明集成。项目采用 [MIT](LICENSE) 许可证，依赖及生成内容遵守各自适用的许可和权利。

## 通用网页操作

基于网页可访问性树操作，无需为每个站点维护 Skill。支持登录接管、请求冻结与审批、执行回执核验，复用 Run、Checkpoint 和效果账本。入口为「助手 → 浏览器」。真实商家发布、下单及支付仍为 **BLOCKED_EXTERNAL**，需用授权账户完成验证。

[Architecture and operating guide](docs/architecture/browser-operator.md)

<img src="docs/images/browser-operator-mobile.jpg" width="260" alt="Browser takeover — synthetic test data only" />

支持直接在聊天中管理长期记忆，例如“记住：我喜欢清淡饮食”“把记忆‘我住在上海’更新为‘我住在杭州’”“忘记关于上海的记忆”“你记住了什么”。保存后可跨会话使用；修改对象不明确时先澄清。[记忆说明](docs/architecture/conversational-memory.md)。
