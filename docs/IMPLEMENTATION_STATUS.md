# 一期实现与验收记录

本文件按日期累计记录，下面早期章节是历史验收快照，不代表当前实现。最新变更与验证见文末及 [CHANGELOG](../CHANGELOG.md)，源码清单见 `VALIDATION_MANIFEST.json`；真实外部服务的 BLOCKED_EXTERNAL 状态须逐项核实。GitHub 提交历史提供源码版本，不能将历史测试数字当作当前覆盖率。

## 实现范围

| 模块 | 已实现 | 验收边界 |
|---|---|---|
| 身份与聊天 | BCrypt、PG 会话、所有权、消息幂等、排序、SSE 回放、停止、引用、重新生成、Markdown、历史检索 | Web 登录与 API 已实测；iOS 同步未真机验证 |
| 三层记忆 | Redis L1、可追溯 L2 摘要、明确记忆 L3 CRUD、修订、墓碑、旧结果丢弃、ES 异步索引 | 自动抽取保守地只采集明确“记住”语句；摘要采用可追溯摘录 |
| 联网 | Tavily 搜索与正文提取、来源/时间/证据级别、预算、有限超时、不可用提示 | 真实 Tavily 已验证，Google 已移除 |
| 定时与恢复 | ONCE/INTERVAL/DAILY、时区、确认草稿、暂停/恢复/取消、唯一 occurrence、SKIP LOCKED、lease/epoch/attempt、immutable checkpoint、outbox | 三实例竞争、SIGKILL、新 attempt 恢复、旧 epoch 拒写、PG 故障已测试 |
| 监控 | 共享关键词采集、内容去重、静默间隔、取消；Open-Meteo 气温/降水/风速阈值 | 关键词取消已测试；天气实时接口需要地域可达，不是商业价格库存 API |
| 研究和旅行 | 多次检索、正文证据、后台 Run、冻结计划、结果回流、下载源文件；真实地理坐标/天气/地点及酒店来源 | 真实 MiniMax+Tavily 研究和杭州两日行程已完成；酒店库存及价格明确未验证 |
| Workspace | 私有上传/PDF文本读取/图片理解、文件权限、Range、SHA 校验、版本 CAS、不可变历史、更新源文件、删除作品 | 文本附件问答及编辑后新旧下载已测；Office 适配尚未实现，一期优先 PDF/文本/图片 |
| 音乐 | 真实 Apple 元数据、持久歌单卡、官方平台打开、私有音频播放器 | 周杰伦 12 条目录真实返回；Mock 原创 WAV 可播放；未提供商业歌曲站内全曲许可 |
| 图与小游戏 | Mermaid 编辑/严格渲染/清洗/SVG PNG 导出，并登记到私有文件库及对应版本；独立 CSP opaque-origin 预览、受控分享和撤销、Docker Runner | Web 源码第二版、纯 SVG 标签与白底 PNG 导出入库、小游戏点击和阻止 parent 访问已实测；Docker Runner 已实测正常渲染通过，无限循环按时终止并清理容器 |
| 图片/原创音乐/视频 | provider 协议、Mock PNG WAV MP4、引用图片权限、参数验证、Automation 任务、provider job/effect 账务、已有 job 查询恢复、签名 webhook、去重、私有作品版本 | **BLOCKED_EXTERNAL：真实生成模型未提供。** Mock 不执行真实图片编辑，不按风格/时长参数生成真实作品；不是接通真实供应商 |
| 图片/语音输入 | MiniMax Coding Plan VLM 适配器、私有图片读取、结果账务；浏览器语音能力检测、iOS Camera、Keychain、本机语音桥 | 提供的 MiniMax 账号可调用 VLM，合成图片 OCR 的文字与两种颜色正确；96px 纯色图颜色判断失败，应保留供应商识别精度限制；iOS 原生桥仍未通过 Xcode/真机编译测试 |
| 审批与离线通知 | CalDAV 草稿/批准/撤销、持久 Run、执行租约检查、IN_FLIGHT/UNKNOWN、查询对账；PG 通知与 SMTP 发送账务、配额 | **BLOCKED_EXTERNAL：CalDAV、SMTP 尚无实际服务配置。** 未声称写入真实日历或真实送达邮件；不具备 APNs |
| 部署恢复 | 独立 Dockerfiles、Compose、非 root、资源限制、私有文件挂载、CI、PG+文件停写备份及独立恢复校验 | 四服务/Web/Migrate/Runner/Gateway 镜像和隔离 Compose 启动已通过，App 重建后聊天与文件 SHA 保持；本地恢复已通过；**BLOCKED_EXTERNAL：ECS TLS 上线和真机验收** |

## 已观察到的验证

- `make build`：Java reactor / TypeScript / Vite 成功，Mermaid 有体积告警，非构建失败。
- `make test`：Java 4 项、Agent 9 项、Tools 6 项通过；OpenAPI 操作数 53。
- `make test-integration`：25 项通过。包括消息并发/权限/预算、三调度器竞争、SIGKILL checkpoint 恢复、过期租约、重复事件、Redis/ES 降级、PG 拒写及连接恢复、删除会话后来源记忆墓碑/延迟抽取丢弃、文件 Range、审批与作品修订、媒体 UNKNOWN 查询恢复和乱序签名回调。
- 真实 MiniMax 流式聊天、架构图和小游戏生成完成，生成游戏通过 Docker Runner；真实音乐聊天卡返回 12 条；附件问答准确返回验收文本代号和数值；研究和旅行 Run 均 COMPLETED。
- 本地 ES 真实记忆入索引、删除后空内容墓碑通过。
- Web 浏览器：登录、作品列表、Mermaid 渲染、保存第二版、小游戏计数按钮 0→1，主页面访问显示“跨域访问已阻止”。截图 `.local-data/web-acceptance.png`。
- 容器验收：四业务服务 + PG + Redis + Web + Runner Gateway 独立启动，Mock 聊天、鉴权/Range、App 强制重建后消息及文件 SHA 保持；Agent→Tools→签名 Gateway→无网络 Docker Runner 渲染通过。Web 就绪检查代理 App，Docker DNS 定期刷新。
- `cap add ios`、`cap sync ios` 与 Swift 语法解析成功；完整 Xcode 缺失，不能声称真机安装成功。
- 备份 `20261010T225429Z` 独立恢复已校验消息、Run、checkpoints、文件及作品；恢复包含 17 条消息、10 个 Run、11 个 checkpoint、18 个文件和 10 个作品，19 个备份对象校验通过；后续新增数据应再备份。

## 发布门禁

ACC-12、ACC-18 和正式 ECS 环境 ACC-19 尚未具备环境；真实外部动作/离线送达和真实生成供应商未验收。ACC-10/16/21/24 的真实设备或更广泛输入仍需验证。不能将以上全部标 PASS，也不能宣称一期工业生产验收已完成。

其他尚需完善：统一 Card Registry 已有版本协议、来源/音乐/任务/作品卡与各模块入口，部分细节通过专属页面呈现；Token 用量与可配置费率估算已实现，供应商价格账单还未实测校对；Web 已有音频切歌和视频海报，原生音频焦点仍需设备验收。正式 Provider 必须补充授权、计费、取消与对账能力测试。

## 行程交互和 Markdown 修复

2026-10-11：普通“安排上海到普吉岛四天三晚行程”改为持久交互 turn，直接流式回复并自动检索 Tavily；不创建 Automation Run、不展示任务编号。明确后台请求仍走原恢复流程，明确“不用后台”会保持交互。聊天和作品正文共用支持 GFM 的安全 Markdown 渲染，补齐表格/标题/列表样式及窄屏横向滚动；原会话已实测表格显示。缺日期时约束相对天数、明确草案假设；搜索营销报价不得当作机酒可订报价。

新增路由、旅行提示与“不创建后台 Run”的测试。Agent 9 项、集成 25 项通过，TS/Vite 成功；真实 MiniMax+Tavily 已观察到直接完成、来源卡、没有任务和机酒金额，日志 `.local-data/travel-interactive-real-final.log`。模型建议仍需核实，单次实测不是全面事实准确性保证。旧会话文字未改写，因此旧任务通知和已生成报价仍是历史内容。

### 2026-10-11 界面与自动搜索修复

全局界面使用中性浅色 / 深色主题，统一侧栏、聊天气泡、输入框、任务、记忆、作品、工具和登录页，支持桌面与窄屏。设置分为常规、个性化、通知、用量、安全、监控；当前设备保存主题、Enter 发送和默认搜索偏好，服务端保存记忆与通知设置。邮箱可清空，空值类型及非法邮箱拒绝；用量展示真实调用、Token、工具额度及文件容量，未配置计价显示明确状态。

明确搜索请求和近期动态自动使用 Tavily，查询与提示注入 Asia/Shanghai 的实际日期。MiniMax 流式伪工具协议在标记输出前拒绝；历史伪工具回复不作为模型示例重放，页面显示失败说明。重新生成使用对应的用户问题，避免失去搜索意图。无自动付费模型重试。

验证：Web TypeScript / Vite 构建通过；Java 4、Agent 13、Tools 6 单元测试与 53 项 OpenAPI 校验通过；25 项隔离集成测试通过（含邮箱设置清空和非法类型）。真实 MiniMax + Tavily 用“帮我搜一下近期周杰伦的演唱会”在原会话成功返回 Markdown 表格、真实来源卡片与抓取时间，手动联网开关关闭。搜索结果内容仍需结合来源可靠性核实；本次验证证明搜索链路与渲染正常，不等于逐项审计演出信息。浏览器验证桌面 1280×900 与默认窄屏、深色主题、用量卡片。截图 `.local-data/settings-redesign.png`，测试日志 `.local-data/ui-refresh-*.log`。

### 2026-10-11 用户注册、访客与百炼模型切换

- Web 默认进入隔离访客空间；注册将当前访客 UUID 升级为账户并保留会话。Web 使用 HttpOnly Cookie，原生使用 Keychain。访客每日 8 次聊天，创作与后台任务需注册。
- 会话 URL 为 `/c/{conversation_id}`，刷新恢复同一会话；已用真实网页验证。
- 文本改用北京百炼 `qwen3.8-max`，真实 API 返回 200；共享 SSE 适配器保留推理过滤、用量、错误及无盲重试规则。Key 仅在忽略的本地 `.env`，不下发 Web/iOS。
- 原创音乐自动路由到 `fun-music-v1`，视频路由到 `wan3.0-video`。音乐官方处于邀测，当前 Key 实测 403 AccessDenied，**未生成真实音乐**。Wan 适配器记录远端 task_id、轮询及 UNKNOWN 查询恢复；模型适配单测通过，完整真实视频生成验收尚未完成。
- 本地 ACE-Step 官方源码及依赖已下载到忽略目录，备用适配器已测试；未启动模型、未生成音频，当前默认仍为百炼。
- iOS 修复 SceneDelegate 自定义桥接入口及 Keychain/Speech 生命周期。同步、Swift 语法检查通过；完整 Xcode/Simulator 缺失且磁盘空间不足，模拟器与真机验收未完成。
- 联网仍为 Tavily 搜索和公开页面提取，通用自主 Browser Use 尚未接入。

### 2026-10-11 聊天中的每日定时任务修复

- 聊天先识别每日执行请求，再进入普通聊天／联网流程。支持中文小时、数字小时、半点及早晚；缺少或无效时间时要求补充，不伪造成功。
- `每天八点帮我整理网上最新关于spacx的信息` 解析为 Asia/Shanghai 每天 08:00，拼写归一为 SpaceX；App 调用现有 Automation 服务持久化，绑定原会话。以 turn_id 为幂等键，首发时间从原始 turn 创建时间确定，重放不创建重复日程。
- 注册账户收到真实日程回执和管理卡片；访客明确提示注册后创建，当前未创建，不再声称产品没有定时功能。
- Qwen 的 `[TOOL_CALL]`、`{tool =>` 和 `<tool_call` 伪指令被流式过滤器拦截，包含跨帧拆分测试；历史污染回复不再加入模型上下文。

### 2026-10-11 音乐会话排障

会话 `d0c4f791-e032-4b77-8fed-e1fe1e4d81e1` 正确提交 AUDIO，Run `bcffba97-12ce-4e20-b886-b1e439ee69e5` 因百炼 `MEDIA_PROVIDER_ACCESS_DENIED` 失败，无音频产物。修复聊天任务卡片只显示初始 QUEUED 的问题，定期读取当前用户任务状态并在终态停止轮询；音乐权限拒绝显示明确中文提示。失败回写针对百炼权限错误提供对应能力提示。不会自动重试失败创作或改写历史消息。

## Alibaba original music and video (2026-10-11)

- Logged-in Beijing Model Studio console inspected. Existing DashScope Key works with its workspace endpoint; no new credentials or account purchase required. Fun-Music remains AccessDenied; original music now routes to `qwen-audio-3.1-tts-next`, video to `wan3.0-video`.
- Real 20-second piano and 5-second video completed through chat → Automation → Tools → private App file → immutable artifact → conversation player. File size, authenticated playback tickets, HTTP Range 206 and unauthenticated ownership rejection verified. Chrome visibly played the generated sea/sunrise video to 0:05.
- Music longer than the model's 120-second limit uses original generated sections with two-second crossfades, not repeated/looped audio. Coordinator ID persists before child submission; child stable effect keys and recorded files allow completed sections to be reused, UNKNOWN submissions remain blocked. Actual composed duration is probed and recorded.
- Browser applications show real provider availability and duration limits. Video now has an inline conversation player and download link. iOS assets synchronized; phone installation still requires the previously noted Xcode/signing prerequisites.
- Automated checks: Tools 20 tests; Agent 17; OpenAPI 55 operations; isolated integration 28 passed. Public Secure cookies remain enabled; isolated loopback HTTP test stack explicitly uses non-Secure cookies.

- Long original music real E2E passed: 180-second request produced a 179.968-second MP3 (4,320,649 bytes), two independently saved original sections, final private Range playback and ownership tests passed; Chrome actually started playback. Validation conversation `/c/9bce5ed0-5d12-4621-8581-df5dc2f9d472`; real video `/c/3371537f-8bc1-4b1f-bd22-f5825321ace7`. Test-only earlier failures exposed child authorization keys and local quota; the child now authorizes with its parent run key while keeping its own effect key. Native Redis remains healthy.

### iPhone 真机安装（2026-10-11）

Xcode 26.3 / iPhone 16 Pro Max（iOS 26.6.1）：真机 Debug 编译通过，修复语音插件 CAPBridgedPlugin 方法数组类型声明；Personal Team 签名校验通过、设备包含在描述文件中，devicectl 已成功安装 io.adex.personal。首次启动等待用户在手机上信任开发者，尚未确认原生 UI 或蜂窝网络功能。客户端独立打包并连接本机服务的 HTTPS 公网隧道；公网首页 200、iOS Origin 访客 API 验证通过。

### iOS 聊天体验修复（2026-10-11）

移除 AI 回答提示行；新回复仅滚动 chat-scroll，保留固定导航；native viewport 随 visualViewport 调整，键盘展开时取消底部安全区额外空隙；语音单按钮开始/停止，优先本机识别，不支持时使用用户授权的 Apple 语音识别；访客附件入口引导注册。真机编译通过并成功更新安装，键盘、录音和附件交互仍需解锁手机后验证。


### 2026-10-11 iOS keyboard regression follow-up
- Removed JavaScript visualViewport height adjustment; Capacitor Keyboard now exclusively resizes the native webview. Native outer scroll/bounce remains disabled, while chat history scrolls inside its own container.
- Fixed native editable fields at 16px to prevent focus zoom.
- Physical iPhone mirror: composer focus, text entry/clear, and opening conversation history verified. Mirroring uses a hardware keyboard, so this does not validate the iPhone software keyboard.
- iOS simulator: software keyboard opened on login input; full composer regression remains unverified because simulator API requests time out and CUA coordinate clicks fail with noWindowsAvailable. Do not count build success as layout acceptance.


### 2026-10-11 press-to-talk interaction
- Composer now uses a circular microphone control with press/hold capture, animated listening indicator, release-to-transcribe progress, and inline empty/permission/error feedback. Recognized text is appended to the draft; sending remains an explicit user action.
- Pointer capture handles release outside the button and interrupted gestures; Space/Enter supports keyboard hold/release. Reduced-motion preference disables animation.
- Browser recognition now keeps interim transcription and stops on release instead of running independently. Native release ends audio and waits for the final recognition result (1.5s fallback) rather than immediately cancelling the last words.
- Web typecheck/build and signed iPhone build passed; updated app installed. Browser UI hold/release without speech verified the empty-transcription feedback. Actual spoken audio transcription on the physical iPhone remains unverified.


### 2026-10-11 mobile chat interface refinement
- Simplified mobile chat header to navigation + Adex + new-chat action. Guest sign-in/register remains accessible in the drawer. Compact welcome chips replace large dashboard cards.
- Composer textarea grows with the draft up to 144px; circular attachment/microphone/send controls, attachment chips, and icon reply actions reduce clutter.
- Added attachment bottom sheet with image/file pickers and native camera capture, uploading/error states, Escape dismissal, and focus return. Mobile auth dialogs now present as bottom sheets.
- Web build/typecheck and signed iOS build passed. Browser at phone-sized viewport verified drawer/account access, guest attachment sign-in flow, and four-line textarea growth/clear.
- Direct comparison with the installed ChatGPT iPhone app remains blocked by iPhone Mirroring reporting Mac locked. No claim of direct inspection or full iPhone software-keyboard regression.


### 2026-10-11 account, per-turn model and interaction regression
- Updated a private local administrator account while preserving the existing owner ID/data. Credentials are intentionally omitted from this public record. Registration no longer enforces the 12-character minimum; required nonempty input remains. Verified administrator login and registration with one-character password over API.
- Added model picker for qwen3.8-max and MiniMax. Model travels through MessageInput, durable turns.model (migration app/015.sql), ChatWorker and a per-request Agent provider instance; invocation provenance and request hash include the actual model. Changing model on an existing idempotency key returns 409.
- UI test conversation f3585059-98be-4728-82b7-ac592e6fcf78 completed requests with provider provenance qwen/qwen3.8-max and minimax/MiniMax-M2.5.
- Send immediately clears draft and displays optimistic user bubble; failed sends restore draft. Guard submission while creating a new conversation. Deferred streaming Markdown + memoized prior Markdown reduces repeat parsing. Auto-scroll follows only while near bottom and no longer starts a smooth animation for every token. Poll snapshots avoid unchanged message updates; native snapshots carry active partial output.
- Recovered missing conversation links to an empty chat instead of repeated NOT_FOUND. Sidebar brand is Adex. Voice is on the right; upward gesture cancels, release transcribes, known recognition failures now show Chinese guidance. Hide voice overlays behind the open drawer.
- Directly inspected installed ChatGPT iPhone chat composer and attachment menu via iPhone Mirroring. Real iPhone drawer and native model picker verified. Browser actual sends verified immediate bubble, no duplicate committed bubble, both models and long-reply scrolling; reading position remained after completion.
- 18 Agent tests passed; OpenAPI validated (55 operations); web build/typecheck and signed iPhone build passed; latest build installed.
- Actual iPhone microphone transcription cannot be verified via Mirroring: macOS explicitly displays 'Cannot use iPhone microphone from Mac'. Do not claim audio recognition or iPhone software-keyboard layout acceptance.


### 2026-10-11 automatic search UI
- Removed the composer search toggle and the default-search preference control. Chat sends no manual search flag; Agent decides from lookup and freshness intent.
- Expanded automatic detection for current news/information, weather, exchange rates, prices/flights and English freshness queries. Explicit Chinese requests not to search remain honored.
- 19 Agent tests passed, covering fresh SpaceX information, weather, English latest updates and ordinary writing/algorithm questions. Browser DOM verified no composer search toggle remains.

### 2026-10-11 history and voice controls
- History deletion has a confirmation dialog; deleting the active conversation returns home. Browser verified deletion of a newly created empty test conversation.
- Voice hints expire after four seconds, allow dismissal, and reset on navigation. Browser verified hint removal on opening navigation. Microphone is 48px and placed at the far left.
- Typecheck, web build and signed iPhone build passed. Latest app installed successfully; native screenshot verified the left microphone. Real microphone recognition remains unverified through Mirroring.

### 2026-10-11 native attachment, intent and streaming regression
- Fixed routing of the observed `创造一首` music request and explicit `创建定时任务每天8:00发送...` request. Invalid/ambiguous scheduling requests ask for time rather than being answered as unsupported. Added regression assertions; 19 Agent tests pass.
- Latest actual music run completed with real Qwen audio (179968ms). Public HTTPS playback verified audio/mpeg, 206 and 1024-byte range. Added player connection error and ticket reload UI; no new billable music request was needed for this verification.
- Native photo-library entry calls CameraSource.Photos directly. Native upload now explicitly encodes the file through CapacitorHttp formData rather than depending on patched fetch body inference. Public image upload returned image/png with 7375 bytes. Native photo selection/upload awaits physical UI verification: native click automation currently reports noWindowsAvailable for both Mirroring and Simulator.
- Native chat now attempts streaming WebView fetch, retaining authenticated 500ms snapshot fallback. Added durable turn.progress events under turn lease fencing and current running-turn snapshot summaries. Server batches at 80ms/64 characters; UI gradually reveals buffered text. Shows bounded processing status, not raw hidden reasoning. Browser verified immediate optimistic message, processing status, final Markdown response and composer reset.
- Voice button moved back to the right. Signed physical-device build and installation succeeded; screenshot verifies right control and chat-created schedule. Test schedule was cancelled after verification.
- Native-origin SSE verification returned turn.progress and at least five token.delta frames with capacitor://localhost CORS allowed. Public HTTPS image/music/schedule checks passed earlier; a later default TLS connection timed out, while IPv4 public HTTP subsequently responded. No tunnel hostname or credentials were changed. Final rebuild and physical reinstall include audio ticket reload and explicit failure reasons.

### 2026-10-11 inline failures, bounded upload and history titles
- Failed turns render an inline notice attached to their user message with a retry action. Initial snapshots restore these notices; changing chats clears transient notices. SSE/native polling no longer writes reply failures into the global banner. Browser intentionally triggered guest SIGN_IN_REQUIRED and verified inline notice plus zero error-banner elements.
- Upload uses a 45-second total deadline, native 10-second connection and 30-second read timeouts. Failure releases the spinner and offers retry with the same file/idempotency key; late native responses do not append an attachment after timeout. Deadline success, rejection and never-settling-request tests passed.
- First accepted user message persists a whitespace-normalized 24-character title. Existing default-title chats display their first user message prefix. Backend API and browser history verified this behavior. Manual renamed historical chats keep their title.
- Web typecheck/build, Java build and signed iPhone build passed. Physical photo selection and upload still require device verification because native click control is unavailable.

## 2026-10-11 后端模块化重构

四业务服务内部按能力划分，Java 控制器拆分并提取身份、账户、会话、记忆、通知、调度和运行用例；Agent 分离上下文、模型调用、检查点、交互与后台执行；Tools 分离 API、供应商、审批和 Runner。引入 ConversationStore / UploadedFile 端口、模型/媒体能力契约与供应商工厂，保留原有 HTTP/数据库契约。参见 `docs/architecture/engineering.md` 与 ADR 002。

验证：`make build test check-style`；隔离数据库 `make test-integration`；秘密扫描。格式和边界约束纳入 CI。旧版验证记录仅代表当时源码；大型生产容量、SLO 和剩余 Workspace 耦合不由本次重构证明。

## 2026-10-11 — Built-in Skill architecture and Travel v1

Added a trusted, versioned Skill registry/plan compiler and Travel Skill. Interactive
and background context assembly includes its policy; persisted plan/checkpoint messages
freeze skill version and evidence. Travel uses bounded sequential guide and practical
requirements searches, preserves partial evidence, handles explicit day counts and
limited follow-up edits. BookingQuote/BookingProvider ports and explicit disabled
transaction capability metadata are present; real booking, checkout UI, transaction
approval, structured itinerary validation and route solving are not implemented.
See ADR 003 and `docs/architecture/skills.md` for precise boundaries.

Verification for this change: Agent 33 unit tests, Tools 25 unit tests, 31 isolated
integration tests, OpenAPI 55 operations, architecture/lint/style gates passed.
Agent wheel built and verified to contain `skills/builtin/travel.toml`. Tests use
mock suppliers; no actual reservation, order or payment was submitted.

## 2026-10-13 — Connectors, action approvals, proactive signals and task matrix

Implemented Google Calendar/Gmail connector adapters, session-bound PKCE OAuth,
AES-GCM credential vault, scopes/refresh/revocation, common action snapshots and
provider receipts on existing approvals/effects. Connector sync/action Runs and
recurring templates reuse Automation leases/fencing/checkpoints/Outbox. App adds
signal dedupe/correlation/importance, notification preferences, APNs adapter/device
ledger and authenticated conversation/Run/action resume. Web/iOS gain assistant and
four-quadrant task interfaces; native notification bridge is wired.

Validation: `make build test check-style`, lint/secret checks and contract validation;
Java 7 + Agent 33 + Tools 32 unit tests; OpenAPI 77 operations; isolated integration
39 passed. Latest iOS unsigned simulator build passed. External providers in these
E2Es are labelled TEST_FIXTURE, not real Google writes/mail or APNs phone delivery.
Real Google/APNs remain BLOCKED_EXTERNAL pending configuration/consent/signing/device
acceptance. Physical reinstall attempt failed: revoked development certificate and
no usable Xcode account; repair and actual installation remain outstanding.

Details and remaining native OAuth/delta-sync/reconciled-Run limits:
`docs/architecture/proactive-assistant.md`. Migrations: app/016.sql,
automation/005.sql, tools/006.sql. Personal runtime data and credentials excluded.

### 2026-10-13 — Signed iPhone reinstall and public access repair

Xcode account/team view refreshed and a new valid Apple Development certificate
created using existing authorization; user completed the macOS keychain prompt.
Signed device build passed, codesign deep/strict verification passed, and the bundle
was checked for the current HTTPS endpoint. devicectl confirmed installation and
launch of io.adex.personal on the connected iPhone 16 Pro Max. Local migrations
app/016, automation/005 and tools/006 applied; all four services returned ready 200.

The prior temporary tunnel had lost connectivity/DNS availability. Public bootstrap
now defaults to HTTP/2 over IPv4 (protocol configurable with ADEX_TUNNEL_PROTOCOL).
A new temporary endpoint returned homepage 200 and protected API 401; iOS assets
were rebuilt for that endpoint. No private signing material or tunnel address is
committed. Real Google/APNs and full phone interaction validation remain separate
external acceptance gates.

### 2026-10-13 — Personal assistant experience

Added Today daily overview and a bounded, editable planning draft over existing
owner-scoped tasks/schedules. Grouped sidebar, mobile page tabs, consistent light/dark
surfaces, account onboarding and settings shortcuts; fixed matrix/assistant page
reload/history. Assistant now separates suggestions, approvals, connections and
notification preferences and creates an origin conversation on demand. Read failures
stay unknown; external actions still require approved snapshots and provider receipts.

Validation: client 6 + Java 7 + Agent 33 + Tools 32 tests, isolated integration 39,
OpenAPI 77 operations; Web build/style/architecture/secrets passed. Responsive
browser checks include completion, approval routing, HTTP 503 partial failure,
deep links/history and theme. Signed iPhone package installed/launched; full physical
keyboard/microphone/push checks remain separate. Synthetic screenshots and scope/gap
analysis: `docs/product/personal-assistant-experience.md`. Google/APNs remain
BLOCKED_EXTERNAL as previously documented; goals/projects, health, cross-device
control and real booking are not advertised as implemented.

White-theme follow-up: light canvas restored to white; Today header/summary made
compact; mobile bottom navigation now includes chat and responds to keyboard
show/hide events. Six client regressions, style/architecture/secrets checks,
Web and signed iOS builds passed. Browser smoke confirms 375px without horizontal
overflow, white RGB255 canvas, draft preservation across Chat/Today and keyboard
event hide/restore using explicit TEST_FIXTURE controls. This does not establish
physical iPhone keyboard geometry; packaging and installation remain verified.

### 2026-10-14 — Bounded, session-local matrix reads

Today and Matrix share an in-memory, owner-session read projection. Reads have an
8-second deadline, concurrent deduplication and 15-second freshness; revalidation
keeps task rows visible. Authentication changes clear snapshots and invalidate old
attempts; confirmed writes invalidate freshness. This is not durable state, an
Automation scheduler or a write retry system. Unknown first-read counts stay unknown.

Ten client regressions, style/architecture/secret checks, Web TypeScript/Vite and
signed iOS builds passed. UI fixture verifies delayed reads exit waiting and Matrix
→Chat→Matrix keeps three rows without loading placeholders. No personal data or
real external operations used. Latest phone reinstall could not proceed: CoreDevice
reported no matching reachable device (paired entry alone did not enable install).
The signed app is prepared; actual installation requires reconnecting the phone.

### 2026-10-14 · Today calendar agenda

- “接下来” now reads upcoming meetings from the first active Google Calendar connection through the existing authenticated Connector query endpoint; automatic schedules are displayed separately.
- Session-local cache, eight-second deadline, retry via refresh, cancelled/ended event exclusion, all-day and ongoing labels, partial-result warning. No database migrations or new scheduler.
- Local Google OAuth client, redirect and credential-encryption settings are missing: real personal-calendar reading is **BLOCKED_EXTERNAL**, not validated by fixtures. Native iPhone EventKit calendars are not connected by this change.
- Verification: `make test-client` (12 passed), `make check-style` (Spotless/Ruff/architecture passed), Web TypeScript/Vite build and secret scan. Calendar date tests are synthetic projection tests, not evidence of real Google execution.

### 2026-10-14 · iPhone system-calendar clarification

- User selected iPhone system calendars rather than Google. Native Today now reads EventKit locally, including synced calendars and expanded recurring events; Web keeps the Google connector option.
- Explicit permission button, iOS 17 full-access disclosure, read-only bridge, no server upload/persisted calendar cache. Denied access gives settings guidance; refresh/foreground rechecks permissions. Only title/id/start/end are exposed, with 200-result cap and partial warning. No database migration.
- Validation: `make test-client` (12 passed), `make check-style`, TypeScript/Vite via `pnpm --dir apps/ios prepare`, signed `xcodebuild` and secret scan. Physical-calendar authorization and actual event display still require user acceptance on the phone; synthetic projection tests do not establish real calendar access.


### 2026-10-14 · Today performance, native meeting details and private notes

- Top header now displays Today / Todo without the Adex breadcrumb. Today removes recent artifacts and its fetch; sections independently publish with eight-second deadlines and session-local caches. Returning to a visited Today immediately shows cached projections. No server-side scheduling changes.
- EventKit adds organizer and location when supplied; local-only calendar content stays off server. Metadata projection test excludes invented organizer/location.
- Notes replaces the workspace navigation entry at `/notes`; `/workspace` remains compatible. Private App PostgreSQL table in app/017.sql, authenticated CRUD/search/pinning, stable-create UUID, CAS saves/deletes and soft deletion. Existing artifacts/files are retained. Explicit saves; unsaved drafts are session-memory only and cleared on account changes. No Apple Notes synchronization, attachments or durable offline drafts in this release.
- Checks: `make test` (13 client, 9 Java, 33 Agent, 32 Tools; 82 OpenAPI operations), `make test-integration` (41 passed, isolated PG), `make check-style`, secret scan, Web and native builds, signed iPhone install. Browser fixture checks: mobile open/back, retained draft on navigation, cached Today revisit, light/dark notes contrast; forced matrix timeout shows an inline retry error while approvals, schedules and runs remain available. Real native organizer/location display depends on device calendar metadata and still requires device acceptance.
- Screenshot: [synthetic note example](images/notes-mobile-fixture.jpg), labelled TEST_FIXTURE with no personal data.

### 2026-10-14 · Daily planning includes today's calendar

- Fixed the planning button omitting calendar context. Clicking performs a bounded fresh calendar read, then prepares an editable draft containing today's device-local overlapping meetings and all-day events, including elapsed/ongoing intervals and supplied locations. Native reads now start at local midnight; upcoming-display filtering still excludes ended events.
- Verified unknown/unauthorized/failed/partial calendars remain distinct from a confirmed empty day; calendar text is quoted as data, capped at 40 events and labelled incomplete when needed. Session changes cancel draft handoff. Calendar data is sent only when the user submits the prepared chat draft. No database or HTTP contract change.
- Checks: 16 client tests passed (day boundaries/overnight/all-day/current/past/cancelled/tomorrow/partial/unknown/bounds), `make check-style`, Web build, iOS prepare, signed Xcode build, secret scan. Browser TEST_FIXTURE verified button-to-chat draft includes today's morning meeting/location and excludes tomorrow. This does not prove real personal-calendar access or model execution; those depend on existing phone permission and real data. No fixture prompt was submitted.

### 2026-10-14 · Cached navigation and bounded notes editor

- Removed duplicate Today/Matrix/Notes headings; notes header is now 笔记 without Adex breadcrumb. Meetings use time rail/title/secondary location with expandable metadata.
- Notes fills remaining flex viewport; editor/textarea no longer uses vh minimums. Keyboard-hidden tab bar and bounded internal textarea scrolling prevent empty footer and horizontal overflow. Session-local query/detail caches, last selection/search/scroll restoration and authoritative-save cache updates; no cached write is marked successful before its API response. In-flight reads are fenced when a confirmed response updates the cache. Failed writes retain drafts; no automatic retry. Text typed during delayed save is retained with the confirmed revision. Caches and pending writes cancel/reset on account changes.
- Verification: 18 client tests; check-style/architecture and secret scan; Web/iOS prepare and signed Xcode build, iPhone installed/launched. Browser TEST_FIXTURE: new note at 390×844 (tab bottom=844, title/body inside width=390), keyboard event + 390×520 resize (textarea bottom=512, tab hidden), cached selected-note restoration, confirmed save and delayed-save concurrent typing retained. Fixture writes only modify in-memory synthetic data.
- Physical keyboard visual acceptance is not claimed: iPhone Mirroring reported the phone in use and could not connect. Existing services/API/database unchanged; no migration.

### 2026-10-14 · Conversation scroll restoration

- Each conversation remembers its scroll offset and near-bottom state in session memory (bounded to 100 conversations, cleared on account changes). First opening defaults to latest messages; tab return restores prior history position or bottom. Restoration waits for that conversation's message snapshot, not its loading placeholder. Content resize follows only while at bottom; sending retains the existing follow-latest behavior.
- Checks: 19 client tests, Web/native builds, check-style/architecture and secret scan. Browser TEST_FIXTURE with 40 messages at 390×844: historical offset 9685 before/after Today return, bottom offset 11373 before/after return (scrollHeight 11972, clientHeight 599). No test prompt submitted, no personal messages accessed. No database/API changes.

### 2026-10-14 · Compact attention and recent task outcomes

- Today merges focus tasks and approvals into “待你处理” with maximum five rows total, UNKNOWN/approvals first and task quadrant priorities as colored right-hand text tags. Compact rows measured 56.5px at 390×844; no horizontal overflow. Completing a task and opening approval detail preserve existing authoritative workflows.
- “交给 Adex 的事” now projects the newest five notification-backed Run/monitor outcomes within 24 hours of delivery, including read/unread records, plain-text summaries and original-conversation links. Exact 24h boundary, invalid/future timestamps, unrelated notifications and duplicate event IDs are excluded. Original records remain in history/notifications. Existing notification API caps at 100 records; this is not a complete archive. Revalidates through existing session read cache, no scheduler or migration.
- Notification list excludes records belonging to deleted conversations, preventing deleted text reappearing through this new projection; internal delivery ledger is retained. No new API contract or schema.
- Checks: 21 client tests, Java unit tests, 42 isolated-PG integration tests, check-style/architecture, secret scan, Web/iOS prepare and signed Xcode build. Native app installed; all four readiness endpoints return 200. Synthetic UI verified read/recent monitor outcomes shown, 25h unread result absent, and click opens original conversation. No real external service execution is claimed by fixtures.
- Screenshots: [attention](images/today-attention-mobile-fixture.jpg), [recent results](images/today-results-mobile-fixture.jpg); all content is TEST_FIXTURE.

### Compact page context bars

- Single route heading in the top bar; removed repeated page names/marketing blocks from Today, Matrix, Notes, Assistant, Settings, automations, memory and tools headers. Context/count and actions share a compact row. Today shows greeting/name alongside device-local date/weekday; night hours use a night greeting. No weather provider is connected, so the decorative sun no longer implies actual weather.
- Validation: 21 client tests, check-style/architecture, secret scan, Web/iOS prepare and signed Xcode build. UI TEST_FIXTURE at 320 and 390 pixels shows no horizontal overflow; Today context and Matrix header measured 36px, Notes header about 34px; one accessible primary route heading. Settings has no repeated body title. No API/database or permission changes.

### Bottom navigation selection policy

- Bottom tab controls and their labels/icons disable text selection, WebKit touch callouts and dragging; the nav-local context menu handler prevents long-press/right-click menus. Ordinary tap, keyboard focus and accessibility remain; no global text/copy/touchstart suppression, so chat and note content remain selectable.
- Verification: check-style/architecture, Web build, iOS prepare/signed Xcode build, secret scan and diff whitespace check. This is a scoped reversible styling/event change, no API/schema changes or new synthetic tests. Physical-device long-press acceptance remains a user check after installation.

### 2026-10-15 · Flat tasks, inline calendar metadata and explicit AI notes

- Today/Tasks share a two-badge importance/urgency component. Tasks now render one priority-sorted list with status/search filters and independent priority checkboxes in the editor; underlying Matrix flags/CAS unchanged. Calendar organizer is right-aligned on time/location row with truncated-text titles, no details expander. Task outcomes follow the agenda in the grid.
- Reply “转成笔记” calls authenticated App `/notes/from-message`, reads only the owned assistant reply, delegates to Agent note composition, validates JSON and commits the note. Scoped invocation ledger key is stable per owner/message; source-message uniqueness in app/018.sql makes retries idempotent. Existing edited notes are returned without replacement. Source conversation deletion retains intentional saved copies; deleted notes are not resurrected. No new service/worker/recovery system. A dedicated message action handles progress/errors/open-note and owner-session cancellation; no automatic copying of replies.
- Validation: `make test` (21 client, 35 Agent, 32 Tools, Java tests and 83 OpenAPI operations), `make test-integration` (44 passed, isolated real PG with explicitly mocked model), check-style/architecture, secret scan, Web/iOS builds. Model-format probe against real configured qwen3.8-max used only synthetic public technical text and returned valid title/body (663 characters); this was not a production-database test. Browser TEST_FIXTURE verifies paired badges, flat list, no agenda expander, correct module order, and reply action opens the saved synthetic note.
- Initial integration failures were caused by rebuilding target JARs while test JVMs read them; test startup now copies immutable JARs per isolated run. Full rerun passed. Local app/018 applied, App/Agent restarted, four readiness endpoints 200. iPhone installation performed. Real phone calendar metadata visibility still depends on permission/provider; no external booking/calendar/email action was executed.
- Example screenshots: [flat tasks](images/flat-tasks-mobile-fixture.jpg), [reply note](images/reply-to-note-mobile-fixture.jpg); synthetic data only.

## Generic browser operator (2026-10-15)

Implemented: constrained AX planner/broker, user takeover, encrypted opt-in login profiles,
request-bound approval, same-Run WAITING_INPUT/resume, effect UNKNOWN reconciliation,
mobile control panel and original-conversation result backfill. No per-site Skills.
Actual website publishing, orders and payment: **BLOCKED_EXTERNAL**; fixture tests do
not verify merchant compatibility. See [operator guide](architecture/browser-operator.md).

## Explicit conversational memory (2026-10-16)

App now executes explicit chat memory commands with atomic Turn receipts, source refs,
owner isolation and existing forgetting/revision invariants. No schema change or new
scheduler. This is persistent user-directed personalization, not model-weight training.
See [supported grammar and constraints](architecture/conversational-memory.md).

## Semantic memory supersedes command routing (2026-10-16)

The previous explicit regex command implementation has been replaced by Agent model
proposals, normalized facts and App-validated atomic commits (App migration 019).
Ordinary durable preferences can be learned without fixed command syntax. Sensitive,
transient, quoted and uncertain candidates are excluded; cancelled answers do not save
incidental memories. See [memory design and limits](architecture/conversational-memory.md).

## 会话内网页操作（2026-10-16）

- 原会话的网页任务卡片承载进度、真实页面衍生的安全登录、扫码／验证码接管、冻结稿件确认与回执。新增 owner-scoped Run 查询，不需要离开聊天到另一个面板。
- 输入凭据经 App→Tools→隔离 Broker 瞬时转交，原生 CDP 文档元数据校验字段来源；不进入模型、聊天、Checkpoint 或效果账本。可选保存七天可撤销加密会话，不保存输入密码；再次任务可复用。
- 登录提交后复用原 Run 暂停／恢复；发表走现有 Action Approval、effect_key 和 outbox。禁止自动跟随写请求重定向／重试，UNKNOWN 不盲目重发；没有实际链接时明确缺失，不拼接站点 URL。
- 无数据库迁移、无新增业务服务或调度系统。接口与局限见 [浏览器设计](architecture/browser-operator.md) 和 [服务契约](SERVICE_CONTRACTS.md)。
- 实测命令：`make build`、`make test`、`make check-style`、`make test-integration`；Java 9、Agent 45、Tools 67 项通过，OpenAPI 91 operations；隔离集成 **55 passed in 178.29s**。新增流程覆盖登录→同 Run 恢复→审批→回执→登录状态复用；修正测试身份复用以遵守注册限流，未放宽生产限流。
- `uv run ruff check services/adex-tools/src/adex_tools/browser services/adex-tools/src/adex_tools/api/browser.py services/adex-agent/src/adex_agent/browser`、新增测试文件 Ruff、`uv run python scripts/check_secrets.py`、`git diff --check` 通过。`uv run python scripts/prepare_ios.py` 与签名 `xcodebuild ... -destination generic/platform=iOS ... build` 成功；用户连接并解锁设备后，`xcrun devicectl device install app` 与 `device process launch` 均成功（`io.adex.personal`）；这只确认安装／启动，不代表真实商家流程真机验收。
- 本机 App／Automation／Agent／Tools 就绪端点均 200。移动端 390×844 合成 UI 实测登录、确认、完成回执及放大预览；body/document 宽度均保持 390。README 截图仅合成数据。
- **BLOCKED_EXTERNAL：真实小红书／淘宝登录、发表、下单兼容性尚未授权实测。** 本地 Chromium／PG 测试不代表真实网站成功执行；验证码、嵌入身份提供商或自定义控件可能需要接管，通用回执识别不等于支付结算核验。

## 开源项目安装与入口修复（2026-10-16）

- GitHub 最近连续五次 CI 的实际失败点为 pnpm 安装自动触发 iOS prepare，并读取缺失的私有临时隧道文件。现改为显式 `pnpm --dir apps/ios bundle`；缺少 HTTPS endpoint 时显示配置说明，保留凭据／路径等 URL 校验。
- 全新归档目录中，无 `.env`／`.local-data`／Xcode／签名，`pnpm install --frozen-lockfile` 与 Web 构建通过。新增 6 项 bootstrap 回归测试；`make demo-ui` 提供只监听 loopback 的合成 UI 预览，不调用真实模型、不做第三方操作。
- 中英文 README 调整产品定位、截图、预览／完整部署入口；补充入门贡献任务、社区规范与 Issue 引导，修正本文开头将历史快照误作当前状态的问题。
- `make build`、`make test`、`make check-style` 均通过；Java 9／Agent 45／Tools 67／bootstrap 6 项，OpenAPI 91。`make test-integration`：55 passed in 180.45s。Ruff、97 个本地文档链接目标、secret scan、diff whitespace 通过。外部仓库配置及 GitHub Linux CI 状态另行核验，见 [审计记录](project/repository-audit.md)。


### GitHub Linux 验收补充

- 后续实际 Linux CI 暴露并修复 Chromium 沙箱 user namespace 权限，以及普通用户 PostgreSQL 默认 socket 目录权限。保留 `chromium_sandbox=True` 和全局 AppArmor 限制，只为 CI 已安装的精确二进制路径配置规则；数据库 socket 使用项目私有 0700 目录。
- Ubuntu 24.04 一次性容器复现原有 `/var/run/postgresql` 锁文件权限失败；修复后以普通用户启动 PostgreSQL 16／Redis 并建库成功，无宿主业务数据参与。辅助脚本回归测试现为 12 项通过。
- GitHub [run 38824689772](https://github.com/jiamingze/Adex/actions/runs/38824689772)，代码 `16e44bc`：verify 与四服务镜像全部成功，含完整集成测试门禁。未删除／跳过失败测试。
- About 描述、预览入口与 `ai-assistants` 主题已由 GitHub 接口回读确认；未发布 Release 或外部推广。浏览器截图读取间歇异常，不伪造截图；其余候选主题尚未全部设置。详见 [审计记录](project/repository-audit.md)。

### 2026-10-16 · Browser follow-up routing correction

- Replaced polite-prefix browser routing with bounded model semantic proposals; carried recent drafts as untrusted, truncated-marked context into the existing BROWSER Run. Corrected chat capability wording to distinguish read-only lookup from approved browser operations.
- No database migration. Existing approvals/effect ledger/fencing remain authoritative; failed prior submissions are not automatically replayed.
- Verification: `make build`, `make check-style`; Agent 52 tests; isolated full integration 55 tests plus new chat-to-browser integration 1 test; Ruff, architecture and secrets checks. Live configured Qwen returned true for two prefixless operation requests and false for a discussion request (routing only, no external submission).
- Real Xiaohongshu publication: **BLOCKED_EXTERNAL**, not verified by fixture execution. Requires current login, exact content approval and provider business receipt; a surviving approval card does not turn a FAILED Run into success.

### 2026-10-16 · Conversational browsing, live lookup and composer

- Browser routing distinguishes lookup, operation and ordinary dialogue, including website-search and login follow-ups. Query results use current page observations with URL/time/SKU conditions; HTTP/query transport receipts are separate from verified publication/order receipts.
- Tools migration `008.sql` supports multiple independently hashed browser approvals within one Run while preserving connector/calendar uniqueness. Approval/control-mode races suspend rather than fail; transport approvals preserve real HUMAN login handoff; unchanged repeated clicks hand off early.
- Visible embedded login pages can be opened by a bound human command; actual origin/frame/egress checks remain enforced. No invented login forms, model-visible passwords or token-bearing iframe URLs.
- Guest chat can create owner-scoped browser executions and use their inline controls/approvals. Account profiles, connector drafts and cross-owner access remain blocked; guest login profiles cannot be remembered. Adex registration is distinct from merchant login.
- Empty composer now supports short tap to type and a 350ms hold to record, release to transcribe, upward cancellation and recording animation. Typing hides the microphone; desktop browser UI verified the hide/restore behavior without sending test text. Native audio recognition still needs physical-device interaction and permissions.
- Real Taobao lookup reached site/network risk verification. No authenticated merchant session, verified iPhone price, purchase or Xiaohongshu publication is claimed; those external outcomes remain **BLOCKED_EXTERNAL** pending user verification.
- Verification: `make build`, `make test`, `make check-style`, `make test-client`; Agent **61 passed**, Tools **70 passed**, OpenAPI **91 operations**, client **21 passed**; full isolated integration **59 passed in 223.16s**, final routing/core/guest regression **9 passed in 14.32s**. Secrets, architecture and diff checks passed. One earlier test-stack startup hit a transient PostgreSQL connection timeout; reruns passed against isolated databases.
- iOS: bundle/sync and signed `xcodebuild` device build succeeded. An earlier browser update installed/launched successfully; installing the latest composer/guest package is **BLOCKED_EXTERNAL** while the phone is disconnected. Do not treat the earlier installation as proof the newest package is installed.

### 2026-10-17 · Latest iPhone installation

The signed package containing the composer and guest-browser fixes from `3e60147`
was installed successfully on the connected iPhone. `devicectl device install app`
and `device process launch` both returned exit code 0 for `io.adex.personal`.
All four local service readiness checks returned HTTP 200. This supersedes the
latest-package installation blocker above; merchant risk verification and physical
microphone interaction remain separate acceptance steps.

### 2026-10-17 · Strict hold-to-talk lifecycle

Both the microphone button and empty composer require a deliberate 350ms hold.
Short taps do not invoke recognition; release/lost capture stop recording, upward
motion cancels, and page hiding stops an active recording. The recording indicator
is a body-level fixed bottom sheet across the viewport, with a circular 44px button.
Native start/stop calls carry per-gesture IDs, so a delayed start after release is
rejected and an old stop cannot terminate a newer recording. Final transcription
processing is explicitly labelled as recording ended.
Verification includes `make test-ios-speech` (stop-before-start, overlapping start,
stale stop and release fencing), Web type/build/client checks and signed iOS build.
Browser short-tap behaviour was verified without sending a message. Actual microphone
speech remains a physical-device acceptance step, not proven by lifecycle unit tests.
The updated signed package was installed and launched on the connected iPhone;
both device commands returned exit code 0. Web build, 21 client tests, native gesture
regression, architecture/style and secrets checks passed. Short microphone-button
tap produced no recording-state change in the browser UI.

### 2026-10-17 · Recording selection guard and contrast

Recording/transcription temporarily disables selection and iOS touch callouts,
clears existing page selection, and removes the guard on completion/unmount.
The empty hold surface also disables selection; typed drafts retain normal editing.
The full-width recording sheet uses saturated indigo waveform bars and a red cancel
state, with a static reduced-motion alternative. The waveform is a recording-state
animation, not a microphone amplitude measurement.

After reboot, persistent PostgreSQL/Redis, all four services, Web, the existing
Elasticsearch container and the public phone gateway were restarted. Four service
readiness endpoints and local/public Web returned HTTP 200. Elasticsearch is yellow
on the single-node development cluster (replica unassigned, primaries active).
Validation: Web/iOS bundle, signed Xcode build, 21 client tests, native speech
gesture regression, `make check-style`, secrets scan and `git diff --check` passed.
The browser automation surface rejected access to the local tab, so physical iOS
callout/visual acceptance is still required; builds are not reported as UI proof.
The signed update was subsequently installed and launched on the paired iPhone;
both device commands returned exit code 0. Its bundled public API origin was
refreshed to the gateway created after reboot (endpoint kept out of Git).

### 2026-10-17 · Separate voice touch surface from text editing

A physical-device screenshot showed the native iOS text loupe over the recording
sheet despite the CSS/selection guard. The empty unfocused composer now uses a
non-editable button over the textarea: hold gestures never start on editable text.
A non-passive touchstart handler cancels WebKit's native long-press default before
the 350ms voice threshold. Short release focuses the textarea for normal typing;
typed/focused drafts keep normal selection, and keyboard/accessibility activation
enters editing. The existing release/cancel speech lifecycle is preserved.

Web/iOS builds, 21 client tests, native gesture regression, architecture/style,
secrets and diff checks passed. These tests do not prove the physical-device loupe
is absent; the screenshot was the observed regression and requires device retest.
The final signed bundle was installed and launched on the paired iPhone, with
both device commands returning exit code 0; existing app data was retained.

### 2026-10-17 · Unified composer controls

The plus button, text entry and voice/send control now share one rounded input
shell in both empty and typed/multiline states. The hold-to-talk surface is
transparent over the shared background; only its duplicate textarea placeholder
is hidden, preserving focus and normal text editing. Attachments occupy a separate
row inside the shell. The existing touch cancellation and speech lifecycle remain.
Validation: Web and signed iOS builds, 21 client tests, native speech gesture tests,
style/architecture, secrets and diff checks passed.
The signed update was installed and launched on the paired iPhone (both commands
exit 0). Visual alignment and native touch behaviour still require device review.

### 2026-10-17 · Taller voice sheet

The recording sheet minimum height increases from 220px to 280px, adapting its
minimum on short viewports with `55svh`. Vertical padding increases to 36px plus
the bottom safe area, giving the waveform and release/cancel hints more space.
Speech and gesture behaviour is unchanged. Web/iOS builds and diff/secrets checks
validate this CSS-only adjustment; physical-device visual review remains separate.
The signed update was installed and launched on the paired iPhone (both exit 0).

### 2026-10-17 · Inline browser login and interrupted-read recovery

Screenshots and read-only diagnostics showed UNKNOWN GET host-permission reads to
the Xiaohongshu pages host, with publication-specific copy and no takeover CTA.
Read-host GET redirects now produce transport-only receipts; no redirect is treated
as authenticated login, publication or purchase evidence. Existing UNKNOWN reads can
be explicitly discarded and reopened in HUMAN mode on the same Run; UNKNOWN writes
remain protected from recovery/resubmission. The card exposes takeover and expands
the real login/control page, and the missing embedded-login API contract is fixed.
Owner/conversation-scoped state-only context grounds follow-up chat responses.
Article/news browsing now uses lookup semantics rather than requiring business
publication receipts. See [contracts and recovery design](architecture/browser-login-recovery.md).

Commands: `uv run --project services/adex-tools pytest services/adex-tools/tests -q`
(72 passed), the analogous Agent suite (62 passed), `make test-client` (21 passed),
`make check-style`, `uv run python scripts/check_contract.py` (91 operations),
`uv run python scripts/check_secrets.py`, `git diff --check`, Web/iOS bundles and
signed Xcode build. Agent/Tools restarted and all four readiness endpoints returned
HTTP 200. Signed iOS package installed and launched (both commands exit 0).
Isolated integration command: `uv run python scripts/test_stack.py
tests/integration/test_browser_operator.py tests/integration/test_browser_access.py
tests/integration/test_browser_routing.py -q` — 10 passed. This includes UNKNOWN-write
recovery rejection, same-Run interrupted-read recovery, and owner/resource isolation
for the metadata-only browser context endpoint.

BLOCKED_EXTERNAL: real merchant login/CAPTCHA/risk-control acceptance requires user
interaction. Synthetic Chromium fixtures and state-injection tests are regression
evidence only; no real Xiaohongshu login, publication or purchase success is claimed.

### 2026-10-17 · Voice capture tactile confirmation

iOS speech capture emits one light UIKit impact only after the audio engine has
successfully started on the guarded main-thread permission path. Short taps,
permission denial and released-before-start gestures never reach this feedback.
Recording-session haptics are enabled best-effort; unsupported feedback must not
prevent recording. Web has no new vibration dependency. Native gesture regression,
signed iOS build, style/architecture and secrets/diff checks validate the change;
actual tactile feel requires a physical-device check and system haptic support.
The signed update was installed and launched on the paired iPhone (both exit 0).

### 2026-10-17 · Route explicit searches despite prior assistant refusals

The reported Xiaohongshu/Tesla request had a real Qwen route result of `none`,
which let ordinary text generation repeat a capability denial. Intent routing now
receives the explicit latest user request and bounded user history only. Assistant
text remains available as untrusted task/draft data, outside intent classification.
No pattern-based production routing fallback or approval bypass was introduced.

Verification: `uv run --project services/adex-agent pytest services/adex-agent/tests
-q` (63 passed); `uv run python scripts/test_stack.py
tests/integration/test_browser_routing.py -q` (5 passed, isolated PG/Chromium/mock
fixtures, including the exact reported request after a poisoned assistant reply);
`make check-style`, secrets scan and diff checks passed. A live Qwen diagnostic
using the actual reported conversation history returned `lookup` with the new
routing input. This confirms routing, not merchant login/search completion.
Agent restarted; all four readiness checks returned HTTP 200. No client bundle
change was needed. Real Xiaohongshu login/risk verification remains
BLOCKED_EXTERNAL until completed by the user; existing chat messages were not
rewritten and no unknown external action was replayed.

### 2026-10-17 · Prepare login fields without a takeover question

The trusted browser handoff now prepares observed embedded login frames once and
renders actual login fields directly in the conversation. It does not ask users to
approve a separate takeover first. Credentials still require explicit user form
submission; automatic preparation grants no generic network-write window. Real
origin/handle checks and existing publication/order approvals remain in place.

Explicit risky-IP/access-denied page text yields `access_block` and BLOCKED_EXTERNAL,
including existing cached views. The card explains that no login form is available,
hides irrelevant submission/login controls, and does not fabricate inputs or retry
website restrictions. Existing uncertain effects remain durable and unreplayed.

Validation: Tools suite (76 passed), Agent suite (63 passed), client suite (21
passed), Web/iOS bundles and signed Xcode build, architecture/style, OpenAPI (91
operations), secrets and diff checks. Chromium tests use synthetic login credentials
and verify automatic form preparation plus secret redaction. Real stored site
observations confirm access restriction detection; these are not proof that real
Xiaohongshu login works. The signed iOS package was installed and launched (both
exit 0); Agent/Tools restarted and all four readiness checks returned HTTP 200.
Real Xiaohongshu login/search remains BLOCKED_EXTERNAL for the currently restricted
server browser environment. Ordinary desktop-browser success does not prove shared
session/network state with this isolated runner.

Final cross-service login regression: `uv run python scripts/test_stack.py
tests/integration/test_browser_operator.py::test_inline_login_approval_and_publication_receipt_in_origin_conversation
tests/integration/test_browser_operator.py::test_login_fields_appear_in_conversation_without_takeover_request
-q` — 2 passed. This verifies the prior remembered-login/publication-approval flow
and first-view embedded login fields, explicit credential submission and automatic
same-Run completion. The isolated first-login fixture expires the synthetic profile
left by the preceding test; earlier failures exposed test-state reuse, not a real
merchant login success. The other five existing operator cases passed in the prior
module run. Automatic preparation also has a regression asserting no write grant.

### 2026-10-17 · Developer Program APNs activation

User explicitly requested native task-result push after enrolling in Apple Developer
Program. Paid team and current signing identity were verified. With explicit approval,
a Sandbox APNs provider key was created through Apple's portal and configured only
in the private server environment; private .p8 and signing settings are excluded from
Git. Local signed app/profile both contain `aps-environment=development`, and native
Info.plist environment matches. Profile validity was 364 days at verification.

Existing Automation/outbox -> App notification -> push delivery remains unchanged.
Native registration now reports the signed environment; explicit enrollment enables
push preferences, previously-enabled devices refresh tokens, and logout revokes the
registered device where reachable. Settings has enrollment/status and an idempotent,
rate-limited test notification scoped to an owned conversation. Foreground banner
presentation is enabled. New/reassigned/reactivated devices do not backfill older
notifications. Payloads retain generic text and conversation/run/action identifiers.

Validation: `mvn -q -pl services/adex-app -am test package`, `make check-style`, Web
build, `make test-client` (21 passed), `uv run python scripts/test_stack.py
tests/integration/test_connectors.py -q` (9 passed), OpenAPI (93 operations), secrets
and diff checks; signed Xcode build and signed/profile/native-environment inspection.
App restarted, all four readiness endpoints HTTP 200. Updated signed iOS package
installed and launched (both device commands exit 0). See ADR 004 and
`docs/architecture/apns-activation.md` for setup and environment limits.

Physical follow-up: one real Sandbox device registered after OS authorization and
push preferences were enabled. Two generic test notifications received real APNs
`ACCEPTED` responses without provider errors; corresponding owner-authenticated
notification-resume requests returned HTTP 200. These tests have no Run and do not
prove scheduled Run recovery or lock-screen presentation. The user reported no
visible effect on tap: the target conversation was already displayed. The client
now closes the notification overlay and shows dismissible notification content in
chat even for same-conversation taps, without inserting a synthetic AI message.
Phone UX acceptance of this feedback and real scheduled Run recovery remain pending.
This key/profile setup verifies development Sandbox only, not TestFlight production.

The temporary public tunnel expired during acceptance (`Tunnel not found`). Local
login remained successful; a replacement tunnel passed actual public login HTTP
200 and a rebuilt iOS app was installed/launched. This is temporary connectivity,
not a fixed production endpoint; use a stable HTTPS gateway for dependable access.

Tap-feedback validation: `make test-client` (21 passed), `make check-style`
(including architecture checks), Web TypeScript/Vite build, secret scan and
`git diff --check` passed. This is client presentation feedback, with no schema,
API, task-state or scheduling changes. Real scheduled-task/Run end-to-end device
acceptance remains separate from the generic test notification.

### 2026-10-17 · Chat todos, relative schedules and release-to-send voice

App migration `020.sql` adds unique nullable chat source-turn identity to matrix
items. A semantic Agent todo proposal is validated and persisted by MatrixService
under conversation/turn fencing locks. Only the committed row produces success;
replayed messages do not duplicate items. Shared Today/Todos projection refreshes
when chat finishes. Existing manual CRUD and user isolation remain unchanged.

Relative minute/hour/second requests now create ONCE schedules anchored to durable
turn creation time. ChatScheduleService translates timing into the existing
Automation API; DAILY remains supported. Receipt cards show the actual one-shot
execution time instead of incorrectly labelling every schedule as daily. No new
scheduler or recovery mechanism was introduced.

`uv run python scripts/test_stack.py tests/integration/test_chat_productivity.py
tests/integration/test_core.py::test_daily_schedule_from_chat_persists_once -q`:
**3 passed in 67.23s**. Real isolated PostgreSQL and three scheduler processes
verified todo persistence/replay, full one-minute elapsed trigger, leased Run
execution, origin-conversation result backfill, one notification and one occurrence.
Model/search/provider responses in this stack are explicit fixtures, not proof of
real news quality or physical APNs display. Agent suite: **65 passed**.

Voice release submits final text through the ordinary idempotent chat path;
recognition finishing before release waits for release. Cancellation/unmount never
submits; a failed network send preserves the recognized draft. Composer border,
focus treatment and circular controls are refined. Signed iOS build, physical
install and launch succeeded; microphone interaction still requires phone acceptance.

Additional regression: isolated todo/replay, three-scheduler SIGKILL/fencing/
checkpoint/outbox recovery, and matrix revision/cross-user isolation: **3 passed in
10.63s**. `mvn -q -pl services/adex-app -am test package`, `make check-style`,
`make test-client` (**21 passed**), Web/iOS TypeScript/Vite build, signed Xcode build,
OpenAPI (**93 operations**), secrets and diff checks passed. The isolated stack
claims and invokes the existing worker explicitly for deterministic execution;
the local deployed Agent has its background claim loop enabled. Migration 020 was
applied locally; App/Agent restarted and all four readiness checks returned 200.

### 2026-10-17 · Chat todo defaults and complete creation receipt

Unspecified importance/urgency now remain nullable in Agent proposals; the App
applies important=true, urgent=false and durable turn.created_at + 24 hours when
no deadline is provided. Explicit priorities/dates override defaults. Migration
021 adds a normalized description; manual updates omitting it preserve the value.
The chat reply is rendered from the persisted row with task, details, deadline in
Asia/Shanghai, importance, urgency and status. Existing todos are unchanged.

Validation: `mvn -q -pl services/adex-app -am test package`, `make check-style`,
Agent productivity tests (2 passed), isolated PG/HTTP defaults/deadline/replay,
explicit-priority/description-preservation and ownership/revision tests (3 passed
in 2.82s), secret scan and diff checks. Migration applied locally and App/Agent
restarted. This server-side change works with the currently installed iOS client;
no signing or native capability change is required. Fixture model responses are
labelled and do not claim real semantic-provider acceptance.

### 2026-10-17 · Mountain launch artwork and simplified app icon

Selected second mountain/sunrise design is now the native launch storyboard and
native session-loading artwork. Aspect-fit on white preserves the approved slogan
“让智能，成为日常。” across screen ratios. A 180ms content reveal respects Reduce
Motion and adds no artificial loading delay. The iOS system launch screen is static.
A generated simplified mountain/trail/sun icon replaces the iOS app icon and Web
favicon/sidebar mark. Icon checked at 1024×1024 without alpha. Source design assets
and intent are documented in `docs/design/launch-screen.md`.

Validation: Web/iOS TypeScript/Vite build, signed Xcode build, `make test-client`
(21 passed), `make check-style` including architecture checks, secret scan and diff
check passed. Physical device overwrite installation and launch both exited 0.
Visual cold-launch acceptance on the physical screen remains user-verifiable;
installation success alone is not a screenshot or animation timing measurement.

### 2026-10-17 · Important todo deadline reminders

App migration 022 adds immutable task/deadline reminder identities, an owner reminder
inbox for manual todos without a source conversation, notification correlation and
backfill of future important TODO items. Saving a task atomically records the
reminder and existing App outbox entry. Automation migration 007 permits an internal
MATRIX_REMINDER ONCE template; no second task scheduler or recovery system exists.
The leased/checkpointed worker emits deterministic data without model invocation.
Result consumption validates current owner, todo status, importance and deadline;
APNs dispatch rechecks eligibility. Deadline changes, completion and deletion
suppress obsolete reminders. Inside-ten-minute creation catches up immediately.
Apple-accepted pushes cannot be recalled; existing quiet hours/notification opt-out
remain authoritative. See `docs/architecture/todo-reminders.md` and internal contract.

Validation: signed state is unchanged (server-only feature); Java App/Automation
unit tests/package, Agent suite (66 passed), formatting/architecture checks,
OpenAPI (93 operations), secrets and diff checks. Isolated real-PG scheduling,
reminder delivery, APNs fixture acceptance, zero LLM calls, duplicate outbox,
completed/rescheduled/deleted suppression and immediate catch-up: 4 passed in
24.76s. APNs fixture acceptance is not physical-phone acceptance for this reminder.

Final isolated regression after lock-order review: reminder suite, chat todo defaults,
explicit-priority overrides, matrix ownership/revision, offline notification resume,
and three-scheduler SIGKILL/fencing/checkpoint/outbox recovery: **9 passed in 41.07s**.
Both migrations were applied locally; App/Automation/Agent restarted, all four
service readiness endpoints returned HTTP 200. Physical iPhone reminder display
still depends on the user's notification settings, connectivity and server uptime.


### 2026-10-17 browser reliability and chat scheduling

Colloquial daily news delivery now reaches durable Automation schedules rather than
plain model text. Exact 10-minute and daily 19:00 requests, deduplication and a
one-minute result backfill passed isolated integration tests (4 passed). See
[chat schedule verification](architecture/chat-schedule-delivery.md).

Browser transport now supports an explicit trusted local proxy, full Chromium,
bounded network diagnostics, search Enter and independent AX budgets. Multi-page
research evidence survives the existing checkpoint/resume path. Browser fixture
integration: 11 passed. Actual Xiaohongshu login and Taobao search remain
**BLOCKED_EXTERNAL**; no real cross-merchant quote, publication or purchase is claimed.
See [audit and real probe outcomes](architecture/browser-reliability-audit.md).


### 2026-10-17 JD transport and live speech preview

- Added opt-in pre-TLS direct fallback to the same pinned public IP when the local
  proxy CONNECT fails; read-only same-site redirects are validated/pinned before
  Chromium follows them. No retry of dispatched writes or new scheduler.
- Real JD search reached 京东验证, not a verified offer. Price lookup remains
  **BLOCKED_EXTERNAL** pending website verification; no price is fabricated.
- Actual native/Web interim speech results now appear in the hold-to-talk panel;
  session-bound events are removed after completion, release/cancel semantics retained.
- Validation: Agent 77 tests; Tools 99 full-suite tests plus 46 focused redirect/
  control tests; browser integration 11 tests; client 21 tests; signed iOS build.
  These checks do not constitute physical microphone or actual JD login acceptance.


### 2026-10-18 consented location for local questions

Web/iOS support on-demand approximate location or manual city, with a first-use
consent dialog and Settings → 常规 → 当前位置. No background positioning. City/area
grounds weather and nearby search; explicit user destinations take precedence.
Temporary turn coordinates are erased at completion/cancellation/deletion, excluded
from model prompts, Redis L1 and automatic long-term memory. Migration app/023.

Local weather uses actual Open-Meteo forecast evidence; manual city uses sourced
search. Provider failure cannot become invented weather. Hotel stars, price,
availability and distance still require independent evidence. Location/permission
fixtures are not actual device fixes. See architecture/location-context.md.

### 2026-10-19 assistant interaction refinements

Notes default to safe GFM Markdown reading with an explicit source-edit/preview
switch. Chat intervals now create real Automation schedules (including `每10min`),
return a validated schedule receipt, and retain idempotency/lease/fencing/outbox.
Check-only tasks suppress identical consecutive result notifications; recurring
reports still notify each time. Push resume can omit the blocking Run lookup;
latest-message reads and bounded session-only chat cache improve initial display.
See [contracts, tests and limitations](architecture/assistant-refinements-2026-10.md).

### 2026-10-19 Muse-inspired assistant workspace

Added App-owned goals and links to existing todos (migration 024); AI goal planning
is a proposal until explicit publication. Creation is idempotent, goal edits/archive
use revision CAS, and progress is derived from actual owned todo states. Relevant
chat context can read bounded active-goal progress. The cached Goals/Activity views
and persistent suggestion feedback extend the existing assistant hub. Suggestion
snooze uses timestamp eligibility, not another scheduler. Obvious login/reset mail
subjects are masked before ordinary model context. Real website login/transactions,
additional connectors and per-user VM/eBPF/confidential isolation are not claimed.
See [comparison, contracts and acceptance](architecture/muse-gap-review.md).

## Unified assistant workspace · 2026-10-20

Implemented 今日 / 对话 / 任务 / 资料 navigation with legacy route compatibility, grouped action reviews, deadline task groups, automation lifecycle filters, and private report/file browsing. Chat receives bounded App-owned todo/note observations and Automation-owned schedules. On iPhone, relevant questions can read previously authorized system calendars; transient payloads use migration 025 with idempotency hashes and terminal cleanup. See [contracts and boundaries](architecture/unified-assistant-experience.md). No claim of external shopping/publishing acceptance or autonomous goal pursuit is implied.

## Permanent automation deletion · 2026-10-20

`DELETE /api/v1/automations/{id}?revision=N` physically removes the owned schedule and occurrence rows. Existing runs are retained for audit with nullable schedule links; pending execution is cancelled with a higher fencing epoch. Content-free creation-key tombstones reject resurrection. Active, paused and terminal schedules all expose the confirmed-delete UI. See [deletion contract](architecture/schedule-deletion.md); Automation migration 008 required.

## Account nicknames · 2026-10-20

App 026 adds optional `users.nickname`; GET/PATCH `/api/v1/me` expose the owned display profile. Settings → 常规 → 昵称 edits it independently from other settings reads. Greeting/sidebar/avatar use nickname with username fallback. Profile cache is session-local, reset on auth change; delayed saves cannot publish into a different session. Login and owner IDs remain unchanged. See [nickname contract](architecture/account-nickname.md).

## Conditional task notifications · 2026-10-20

Schedule drafts and creation accept CONDITION_MET with an explicit typed condition. Agent semantically interprets the user request, freezes tool evidence in the existing plan checkpoint and assesses the condition in the result checkpoint. Automation verifies condition correspondence, evidence freshness and numeric comparisons before setting notify. Failed/unknown/unmet checks retain original-conversation results but create no notification records, so cannot enqueue APNs. Existing EVERY_RUN/CHANGES_ONLY remain supported. No migration. Semantic decisions are evidence-backed model judgments, not exchange-grade market feeds; actual sources may remain unavailable. Existing tasks are not silently reclassified. See [contract and boundaries](architecture/conditional-notifications.md).


## 2026-10-20 — Existing conditional schedule repair

- Existing schedules can replace their notification rule through revision-checked PATCH; no migration, no immutable Run rewrite. Current conditional rules additionally gate older Run completion/failure.
- Model MET / NOT_MET / UNKNOWN continues through the evidence validator and Automation final gate; missing/negative/unknown/failure stays silent while origin-conversation delivery persists.
- Observed: `pnpm generate:contracts`, `make format`, `make build test check-style` passed (App 12, Automation 5, Agent 98, Tools 124; architecture and formatting passed). `uv run python scripts/test_stack.py tests/integration/test_conditional_notifications.py`: **4 passed in 16.14s**, including rule revision conflict, unauthenticated update rejection, missing condition validation, legacy in-flight success/failure suppression and existing MET/NOT_MET/UNKNOWN delivery. `uv run python scripts/check_secrets.py` passed.
- Operational repair used authenticated App APIs to apply conditional rules to the affected existing monitors; user data and credentials are excluded from source. No new real market-data or profitable-trade acceptance claim; subjective conditions remain model judgments and unavailable evidence stays UNKNOWN.


## 2026-10-20 — Automatic public browsing

Public read-only cross-site navigation no longer requests domain confirmation; private DNS/ports, critical gestures, known action URLs/query operations, writes and approvals retain their gates. Telemetry is dropped rather than becoming a pending operation. A blocked Google read-only search can automatically use existing authenticated search, explicitly labelled as alternate snippets. See [browser read autonomy](architecture/browser-read-autonomy.md) for contracts, observed checks and real Google challenge limitation. No migration or new execution system.


## 2026-10-21 — Flash model and mobile connectivity

Default Qwen configuration and chat selector now use qwen3.8-flash; old Max selector remains a compatibility alias routed to the configured Qwen provider rather than MiniMax. Contracts, memory routing and background default are consistent. App migration 027 is required for the persisted model selector (corrected after the initial release). Build/unit/style/architecture and secret checks passed (App 12 / Automation 5 / Agent 107 / Tools 132). Public authenticated login verified after replacing the expired temporary tunnel; iOS signed build includes the refreshed API address. Actual Flash API initially returned Arrearage; final post-recharge call returned HTTP 200 with model qwen3.8-flash. Updated iOS app was overwrite-installed and launched with the existing data container; see [verification](architecture/qwen-flash-default.md).


## 2026-10-21 — Flash message persistence correction

Initial Flash rollout missed the database CHECK constraint installed by App migration 015: HTTP allowlists accepted Flash but turns_model_check rejected the insert, rolling back the send and returning DATABASE_UNAVAILABLE. Additive migration 027 preserves existing selectors and admits Flash; no user/history rewrites. Applied locally and read back the actual constraint definition.

`uv run python scripts/test_stack.py tests/integration/test_chat_model_persistence.py`: **4 passed in 0.98s**, using isolated PG and real authenticated message POST/idempotent retry for Flash, legacy Max, MiniMax and default. This proves message persistence, not real LLM execution in the fixture stack. `make build test check-style` and secret checks verify unchanged service code plus migration delivery. Phone reinstall unnecessary.


## 2026-10-21 — Natural-language personal priorities

Removed the keyword gate from authenticated owner-scoped personal context and the native calendar bridge. “帮我梳理今天最重要的三件事” now receives bounded current tasks/notes, HTTP-owned automation observations and an available already-authorized device calendar snapshot. Partial/unavailable sources stay explicit rather than becoming a blanket refusal. Context is untrusted read-only data, not write authority, memory or cached calendar storage.

Build/unit/style/architecture passed (Agent 108 / Tools 132). Personal-context real PG integration: **2 passed in 2.14s**. Actual Flash sample with synthetic tasks passed. Signed iOS overwrite install/launch succeeded; no user data exposed in tests. See [contracts and limits](architecture/always-personal-context.md).


## 2026-10-21 — Editing automatic schedules

Active/paused chat schedules now have a pencil action for title/instruction, frequency, timezone, time and explicit notification rules. Save uses owner/revision-checked PATCH; timing changes recalculate future occurrences under the existing schedule lock. Content-only edits retain next execution; historical/in-flight Runs remain immutable. Terminal and managed connector/reminder work cannot be rewritten as chat schedules.

Build/unit/style/contract/security checks passed; real PG integration **6 passed in 28.45s**, including actual future claim and existing conditional/deletion regressions. Mobile-size synthetic UI save/reopen/scroll verified. Signed iOS overwrite install/launch succeeded. See [contract and evidence](architecture/schedule-editing.md).

## 2026-10-22 — Typed actions, durable research and autonomous memory

Studied the official openai/codex tool routing/orchestration at a pinned revision and
independently adapted its execution principles; no Rust harness/private prompt is vendored.
[Contracts, migrations, source references and limits](architecture/task-action-kernel.md).

- Semantic task proposals use a closed schema, bounded repair, observed owner/ID/revision
  binding and frozen replay. App alone executes and generates receipts after readback.
  App 028 stores per-Turn receipts; Automation 009 atomically journals replayable PATCH
  commands. Todo edits preserve default/deadline/ownership and commit receipts locally.
- Complex research can create the existing RESEARCH Run with an acceptance checklist.
  Search/read/observe/finish loops preserve the original request, bounded working context
  and step transcript. Checkpoint before/after read dispatch, current lease/fencing,
  recovery, repeat breaking and partial results reuse existing mechanisms. This is a
  read-only research executor, not a universal cross-site transaction engine.
- Semantic memory runs on eligible ordinary turns, normalizes facts, validates literal
  evidence/observed corrections, repairs invalid proposals once and selects relevant
  older memories. Recall rechecks PG ownership, revision and tombstones. L2 global
  compaction remains extractive; candidate recall is bounded, not unlimited vector search.
- Mobile task editing uses top cancel/save navigation, inset groups, no autofocus,
  bounded date/time inputs and a scrolling body. Synthetic 390×844 UI save/reopen/scroll
  passed, document width stayed 390px. Public screenshot contains synthetic data only.

Observed checks:

- `make build test check-style`: Java/Web build, Java 18 tests, script 17 tests, client
  27 tests, Tools 132 tests, OpenAPI 100 operations, style and architecture passed.
- Final `uv run --project services/adex-agent pytest services/adex-agent/tests -q`:
  **119 passed in 0.70s**.
- `uv run python scripts/test_stack.py`: **96 passed in 333.11s**, isolated real PG/HTTP
  with deterministic external/model fixtures. After the final timing/readback hardening,
  `uv run python scripts/test_stack.py tests/integration/test_task_action_kernel.py tests/integration/test_semantic_memory.py tests/integration/test_schedule_editing.py -q`:
  **9 passed in 30.00s**. These are not real third-party execution claims.
- `uv run --project services/adex-agent python scripts/evaluate_agent_kernel.py --live`:
  seven actual Qwen cases passed with synthetic snapshots: delayed creation, update,
  conditional schedule, research routing, normalized preference, correction and recall.
  No application DB writes. This is targeted evidence, not a general success-rate benchmark.
- Secrets scan and new-module Ruff checks passed. App 028 / Automation 009 applied locally;
  all four services ready. Public API unauthenticated GET returned actual App JSON 401.
- `pnpm --dir apps/ios bundle` and signed `xcodebuild ... -allowProvisioningUpdates build`
  succeeded. Device currently unavailable: this update has **not** been installed on iPhone.

## 2026-10-22 — Restore push registration after logout

Removed the local-device-hint prerequisite from native login/foreground restoration.
Existing account preferences and system authorization govern registration; silent native
restoration does not request permission or override opt-out. Authentication cleanup blocks
stale callbacks. Logout revocation and server eligibility timestamps remain intact.

`make test-client`: 29 passed. `make build check-style`: passed. Signed iOS build succeeded.
`uv run python scripts/test_stack.py tests/integration/test_push_restore.py tests/integration/test_connectors.py::test_offline_push_and_resume_original_run -q`:
2 passed in 8.66s, isolated PG/API with explicit APNs fixture. Actual device unavailable and
its server registration still inactive: real push restoration/delivery not yet verified.
See [lifecycle and acceptance boundary](architecture/push-registration.md).

## 2026-10-23 — M17 owner-bound macOS computer adapter

User-requested extension beyond original desktop exclusion; four business domains and
existing Automation lease/fencing/checkpoint/outbox retained. Tools migration 009 adds
private AX observations and a serialized host command lease. Semantic `computer.start`
creates/readbacks an owned Run; per-action chat approvals resume the same Run. Native
press/set_value are bound to app/PID/fresh tree and recorded in existing effect ledger.
Deleted conversations, other owners, expired observations and stale Run epochs deny
execution. Interrupted IN_FLIGHT is UNKNOWN and is never blindly dispatched again.

- `make build test check-style`: passed. Scripts 17, client 29, Java App 13 / Automation 5,
  Agent 119 and Tools 135 tests passed; contract and architecture checks passed.
- `uv run python scripts/test_stack.py`: **99 passed, 1 skipped in 371.48s**. Synthetic
  computer flow covers wait → approve → same Run resume → final original-chat result;
  isolated fault checks cover owner/fence/expiry/host contention/UNKNOWN/deleted chat.
- Opt-in actual Calculator test uses isolated PG, real native Accessibility dispatch,
  approvals/effects and final AX readback `1+2=3`. No personal documents or application
  database are test fixtures. Default CI uses explicit synthetic UI, never native proof.
- Native Swift compiled and locally signed; macOS Accessibility granted to the helper.
  Production/local Tools capability API reports READY for the configured existing owner.
  Tools 009 applied locally; four services and Redis report UP. Web and iOS bundle built.
- Chat approval UI checked with synthetic data in browser: correct target/action,
  approval state transition and disabled duplicate submission. Private evidence remains
  in ignored `.local-data`; no personal desktop captures or credentials in Git.

Limitations: Calculator/TextEdit only in initial local allowlist. No direct shell,
scripts, screenshot, global keyboard/coordinate actions, arbitrary filesystem API or
universal custom UI support. Every mutation requires an exact approval. A native command
receipt does not prove external business success. Broader apps require explicit local
configuration and further acceptance tests; see the [runbook](runbooks/macos-computer.md).

## 2026-10-23 — Chrome routing, whole-Mac app policy and private document return

- Add explicit `all_installed` host policy while retaining exact owner binding. Resolve
  installed applications before creating Runs; allowlist remains the deployment default.
  This local owner explicitly opted into all installed apps and Desktop document access.
- Schema-guided task-plan repair includes safe validation locations and the failed
  proposal. Chrome search remains one COMPUTER goal; parsing failure no longer asks for
  a schedule time. Two actual Qwen file-selection checks passed with invented filenames,
  including selecting “1” from prior options; no personal documents were model fixtures.
- Native Chrome opens Google using a fixed HTTPS query constructor, reads only the
  focused document, waits for real result links and returns observed source evidence.
  No remote-debugging port, profile/cookie extraction or page JS. Initial planning does
  not inspect an unrelated existing page. Search summaries exclude account/header/footer.
- Render search results from observed headings, excerpts and URLs as at most five
  numbered named links, with timestamp/provenance; no raw model URL dump or “desktop
  stopped” success prefix. Fixture tests cover Markdown/URL safety and title duplication.
- `computer.start.file_path` freezes an explicit return request. Automation returns
  that exact live-Run file grant; Tools rejects browser-task escalation before reading.
  Desktop regular files are bounded, no-follow and imported through App File API only.
  READY/hash/size readback and stable Run/step keys produce an owned file card. No DB
  migration. A Finder button is no longer misused to transfer files to the phone.

Validation:

- `make format build test check-style`: passed (scripts/client/Java, Agent 125, Tools 141;
  OpenAPI 100 operations, architecture and formatting checks).
- `uv run python scripts/test_stack.py`: **99 passed, 2 skipped in 391.02s** after fixing
  an unrelated push-test account collision. Each push test now has a private account;
  the production 30-second notification limit remains enforced.
- Final targeted integration with computer/file flow, stale worker recovery and offline
  push: **5 passed, 2 skipped in 32.78s**. Synthetic document bytes through real isolated
  PG/HTTP: private download, cross-user rejection, exact grant denial and idempotent
  import replay. No production database or personal files used as development fixtures.
- Opt-in real Chrome/Qwen flow is tracked separately from fixture acceptance. Native
  search and source readback have run against actual Chrome; provider output/network
  remain external dependencies, not an overall reliability-rate benchmark.
- Signed iOS build succeeded. Updated `io.adex.personal` installed and launched on the
  connected iPhone using devicectl. The new system share/save sheet still requires a
  user tap for physical-device acceptance; do not claim a file was saved without it.
- Local public App API returned actual JSON 401 unauthenticated. Four services/Redis UP.
  Secrets remain excluded; private screenshots, runtime data and keys are not Git files.

Limits: AX controls remain bounded; custom-rendered software is not universally
operable. Document return supports single files up to 25 MiB, not app bundles/folders.
Whole-Mac application access does not grant arbitrary file export or shell execution.

Final external check: `ADEX_TEST_REAL_CHROME=1 uv run python scripts/test_stack.py tests/integration/test_computer.py::test_actual_chrome_search_returns_to_original_conversation -q`
returned **1 passed in 16.56s** with actual Chrome and Qwen, structured headings and
private original-conversation readback. An earlier real invocation exposed invalid
operator JSON; the operator now has a strict generated schema and one bounded
validation repair on journaled model output, with no tool-effect replay. The final
repair unit test passed; the live check is a targeted case, not a global success claim.

Native bundle/install commands: `pnpm --dir apps/ios bundle`;
`xcodebuild -project apps/ios/ios/App/App.xcodeproj -scheme App -configuration Debug -destination 'generic/platform=iOS' -derivedDataPath .local-data/computer-files-ios -allowProvisioningUpdates build`;
`xcrun devicectl device install app --device <connected-device> .local-data/computer-files-ios/Build/Products/Debug-iphoneos/App.app`.
Observed BUILD SUCCEEDED, App installed, and successful launch of io.adex.personal.

## Alibaba realtime speech recognition (2026-10-23)

Replaced iOS SFSpeechRecognizer and browser SpeechRecognition with Tools-owned
`qwen3-asr-flash-realtime`. Native AVAudioEngine captures PCM16/16kHz; browser captures
microphone PCM. Existing hold-to-talk, live text, slide cancellation, release-to-send
and haptics remain. Apple speech authorization is removed; microphone authorization
is still required. Provider credentials stay on the server. No audio/transcript is
persisted or logged by this relay. [Contract and deployment](architecture/speech.md).

Migration: `tools/010.sql` provides one-use tickets and a bounded per-owner connection
lease. App authenticates a scoped capability; the gateway exposes only `/speech-ws/`,
not internal Tools APIs. PostgreSQL failure denies new streams. No Automation Run,
checkpoint or scheduling system is duplicated for short microphone input.

Observed validation:
- `make format build test check-style`: Java/web build, 33 client tests, Java tests,
  125 Agent tests, 146 Tools tests, OpenAPI 101 operations and architecture/style passed.
- `make test-ios-speech`: stop-before-start, overlap, stale-stop/release fencing passed.
- `uv run python scripts/test_stack.py tests/integration/test_speech.py -q`:
  **2 passed, 1 skipped** (real PG/auth/WS, wrong-resource ticket, invalid token,
  duplicate ticket and owner connection limit; no-key provider failure).
- `ADEX_TEST_REAL_ASR=1 uv run python scripts/test_stack.py tests/integration/test_speech.py -q`:
  **2 passed, 1 skipped**. Actual Alibaba recognition of locally synthesized speech
  through authenticated App → Tools WebSocket returned partial and final text including
  “明天”“三点”“开会”. Only the missing-key fault case is skipped in this mode.
- Separate synthetic audio provider call returned “请帮我创建一个待办事项。明天下午三点开会。”
- `pnpm --dir apps/ios bundle` and signed Xcode Debug build passed. New iPhone app
  installed and launched via devicectl. This proves installation, not physical
  microphone/noise/accent acceptance; those remain device-specific manual checks.

Known limits: one stream per user, 45-second capture budget, 15-second finalization;
network access and a funded/authorized DashScope account are required. No silent
fallback to Apple or fabricated transcript when Alibaba fails. Browser capture currently
uses ScriptProcessorNode; AudioWorklet migration remains a latency optimization.

## Direct native Chrome navigation and actionable computer errors (2026-10-23)

The native computer operator previously offered only Google `search` plus generic
AX controls. “Open YouTube homepage” could become a search for “YouTube home page”,
then an empty `blocked` plan produced an empty user-facing error. Host policy was
already `all_installed`; granting more macOS permissions would not repair this gap.

Added `navigate` to the typed operator vocabulary and `navigate_url` to Tools
observations. Tools admits public HTTPS destinations and verifies public DNS before
native Chrome navigation. Reading/opening uses the existing observation path, without
an approval. The signed helper uses the user's existing installed Chrome/profile;
it exposes no scripts, debug port, cookies or passwords. Native page readiness has a
bounded poll, and slow loads return `loading` for subsequent observation. Repeated
navigation does not reload a still-rendering page. The planner rejects blank final
reports, completion while loading, repeated navigation and unobserved result URLs.
Web observations sent to the model focus on page content rather than browser chrome.

State ownership is unchanged: navigation intent is checkpointed before native dispatch
and the existing Automation Run/lease/fencing and Tools command mutex stay authoritative.
No migration or additional scheduler. Existing write approvals and file grants remain.

Validation: `make build test check-style` passed (33 client tests, Java tests,
127 Agent tests, 147 Tools tests, 101 OpenAPI operations, architecture/style).
`uv run python scripts/build_computer_runner.py` compiled and signed the helper.
Real isolated-DB Chrome/Qwen YouTube end-to-end checks passed, returning an actual
observed homepage video title/link to the originating conversation with no computer
write approval. Personalized titles, URLs and AX snapshots are kept only in ignored
local evidence, never committed. See the runbook for native prerequisites and limits;
these targeted checks are not a universal website or computer-operation guarantee.

## Native speech latency and agent reliability milestone (2026-10-23)

See [nanoMuse code comparison and implementation plan](architecture/nanomuse-review.md)
for the pinned upstream evidence, license boundary, migration, contracts and acceptance.
Native iOS now captures before network setup and streams PCM through URLSession rather
than one JavaScript bridge event per audio buffer. A synthetic real native test observed
nonempty interim transcription at 2.484 seconds, while finish was sent at 16.176 seconds.
This proves pre-release native transport, not a microphone or touch-tracking UI acceptance.
Following real iPhone feedback, already-authorized on-device recognition now owns the
submitted text as well as the displayed draft. A bounded 800 ms tail-finalization window
preserves the final words; a different cloud interpretation cannot overwrite accurate
local text. Alibaba remains the final source when no local text is available. The released
panel is frozen rather than replaying cloud prefixes. Apple cloud recognition remains
disabled and no new speech permission dialog is forced. This supersedes cloud-final mode.


Final observed validation for this milestone:
- `make format build test check-style`: Java/web builds, 17 script tests, 34 client tests,
  131 Agent tests, 147 Tools tests, Java tests, OpenAPI 101 operations, architecture/style passed.
- `make test-ios-speech test-ios-speech-stream test-ios-speech-choice`: gesture fencing,
  one-shot native transport cancellation, local transcript priority and no late cloud
  overwrite passed. Native live transport with synthetic speech also received interim
  text before finish. Latest source-choice behavior is unit-tested; final microphone
  accuracy still depends on device language support and actual speech.
- `uv run python scripts/test_stack.py tests/integration/test_observation_notifications.py tests/integration/test_conditional_notifications.py tests/integration/test_reliability.py::test_three_schedulers_sigkill_fencing_resume_and_outbox tests/integration/test_reliability.py::test_memory_deletion_invalidates_context_and_inflight_results tests/integration/test_reliability.py::test_unknown_provider_call_never_resubmits tests/integration/test_speech.py -q`:
  **10 passed, 1 skipped in 33.63 seconds**. The skipped case requires explicit real-ASR opt-in;
  it is not a fabricated external execution. Change-only tests verify identical evidence /
  changed prose is silent, changed evidence / identical prose notifies, every result still
  reaches its original chat, and concurrent identical occurrences create only one push.
- Applied `automation/010.sql` locally. Agent planning includes typed schemas and one bounded
  correction of invalid completed output; normalized query signatures and novelty feedback
  reduce empty repetition while preserving the existing 24-step budget and pending-intent
  checkpoint protocol. Memory repair includes actual validation details but cannot bypass
  App evidence/revision/deletion rules.
- Notification comparison takes a short per-schedule advisory lock before locking the Run;
  no network/LLM work occurs inside it. The existing outbox/fencing remains authoritative.
- Latest signed iOS build: BUILD SUCCEEDED; devicectl confirmed installation and launch.
  All four services report UP. No public URL or credentials were changed.

Known limits: this is the first bounded reliability milestone from the comparison,
not all nanoMuse capabilities. Automatic destructive memory consolidation, universal
computer access, new connectors and broader self-directed goal execution remain separate
acceptance work. On-device speech requires prior authorization and language support;
Alibaba is used when usable local text is unavailable. Both may run concurrently.

## Read-only site search and stale desktop recovery (2026-10-23)

Read-only site searches use the public HTTPS GET search URL without approving text entry.
Native observation/pid guards remain strict. A definite pre-dispatch stale observation
returns REOBSERVE_REQUIRED, records the effect as FAILED and revokes the obsolete approval;
the Agent checkpoints the non-applied step and observes again. UNKNOWN actions are never
blindly replayed. Publishing, ordering and other external writes still require approval.

Observed validation:
- `make format build test check-style`: passed, including 131 Agent and 147 Tools tests.
- `uv run python scripts/test_stack.py tests/integration/test_computer.py tests/integration/test_observation_notifications.py -q`: 4 passed, 4 skipped in 21.20s. Skips are opt-in real desktop cases.
- `ADEX_TEST_REAL_CHROME=1 uv run python scripts/test_stack.py tests/integration/test_computer.py::test_actual_youtube_site_search_does_not_request_typing_approval -q`: 1 passed in 18.88s. Actual Chrome/Qwen opened YouTube search without approval and returned video/Shorts links present in actual observations.
- One earlier live attempt encountered a provider rejection; a fresh run passed. This is not a guarantee of provider availability or all-site login/shopping support. Safe diagnostics record only HTTP status and a bounded provider error code.

## Localized Mac application discovery and Futu boundary (2026-10-24)

Diagnosed conversation failures as COMPUTER_SCREEN_LOCKED, an exhausted observation loop,
and COMPUTER_APP_NOT_INSTALLED before a Futu Run could start. The installed application is
FutuNiuniu.app / cn.futu.Niuniu; its Chinese name lives in localized bundle metadata.
Native discovery now reads installed localized names and accepts only unique normalized
name/prefix matches. Ambiguity fails closed; authorization and action approvals are unchanged.
Added a bounded native startup wait, no-progress observation guard, and explicit lock-screen
and ambiguous-name messages. No database migration or new execution system was introduced.

Validation includes Java/web builds, native helper compilation/signing,
`make build test check-style` (136 Agent tests, 148 Tools tests, client/Java/contract
tests and architecture/style checks), plus the following real/isolated acceptance.
`ADEX_TEST_REAL_CHROME=1 uv run python scripts/test_stack.py tests/integration/test_computer.py::test_actual_futu_localized_name_and_login_boundary -q`: **1 passed in 11.92s**, using the real
installed Futu application and Qwen with isolated database state. All three Chinese names
resolved, the actual login UI was observed, and no action approval/trade was created.

The initial login boundary was **BLOCKED_EXTERNAL**. The user subsequently signed in.
Native observation now selects the focused/main AX window instead of traversing unrelated
application menus, activates/reopens the requested application, and supplies bounded
Vision OCR for custom-drawn quotes/charts when Screen Recording is already authorized.
It selects only windows of the target process: matching AX geometry where available,
otherwise an unambiguous principal window. Missing permission, ambiguous windows or
capture/OCR failure remain explicit unavailable states. Images stay in memory; bounded
OCR text is private observation evidence, never executable controls. Native mutations
continue to fence on the AX tree rather than fluctuating OCR pixels.

Added `confirm` only for controls exposing AXConfirm, using the existing approval/effect
ledger. It permits submitting native search fields without global keyboard injection.
Planner input explicitly surfaces OCR evidence and distinguishes the main instrument
from other stocks in the watchlist. Regression tests cover no-progress termination,
visual evidence forwarding and rejection of confirm on unsupported controls.

Actual signed-in desktop extraction read the 09961 chart, displayed price and BOLL
values. Complete historical OHLCV extraction and prediction quality are not accepted
by this milestone; forecasts must remain limited conditional scenarios, not guaranteed
future prices. OCR can misread values; read time is not quote-update time.

Native toolbar search is independently restricted to a unique non-secure input under
AXToolbar with a recognized search placeholder and AXConfirm. The lookup focuses that
field, verifies the target application remains frontmost, and permits only the fixed
Return needed to submit/select its search candidate. It exposes neither arbitrary keys
nor model-provided coordinates. The previous generic native AXConfirm action remains
approval-bound. Read-only searches reuse pending-search checkpoints and do not request
per-keystroke approval; actual instrument readback, not command acknowledgement, is the
success criterion. Desktop applications without qualifying search controls fail closed.

Window OCR now preserves normalized text positions and numeric emphasis. An AX context
label must corroborate the visual heading; only a unique aligned highlighted numeric
readback is selected. Typed quote_instrument/quote_price must match that readback, with
one bounded planning repair on mismatch. The reply renders the native source value
directly. Conflicting/insufficient evidence cannot produce a done forecast. Tests reject
an indicator midpoint substituted for the current price. This reduces the observed
watchlist/main-chart and BOLL/current-price confusion; it is not a universal visual parser
or a substitute for licensed historical market data.

Final observed acceptance:
- `ADEX_TEST_REAL_CHROME=1 uv run python scripts/test_stack.py tests/integration/test_computer.py::test_actual_futu_current_quote_uses_visual_evidence -q`: **1 passed in 32.42s**. The test first uses native toolbar lookup to open TCOM, sends a natural-language chat request for 09961, verifies the main AX instrument really switches to 09961, checks returned numeric readback against actual spatial evidence, and waits for the result in the origin conversation. No action approval or trade is created. The inspected final reply uses the correct main-chart value and limited conditional BOLL scenarios.
- `uv run python scripts/test_stack.py tests/integration/test_computer.py -q`: **3 passed, 6 skipped**. Skips are explicitly opt-in actual Mac/Chrome/Futu acceptance, not simulated external execution.
- Earlier live runs exposed mismatched watchlist/chart values and a BOLL midpoint
  misreported as price. Those results were rejected during development; position-aware
  evidence and typed readback validation were added before deployment. Complete historical
  market-data ingestion and investment prediction quality are still not validated.

## MT5 research and preflight increment (2026-10-24)

Added `trading.mt5-research@1.0.0`, a closed read/preflight Wine bridge targeting
the owner's installed Mac MT5, and a synthetic proposal simulator. The Agent
can obtain XAUUSD evidence through signed `trading:read` HTTP requests; Tools
checks the configured host owner before terminal access. Only bounded bars enter
model context. M1/M5/H4, broker symbol constraints and pending-order metadata are
read from the terminal, not generated by the model. No new scheduler or database
state owner is introduced.

On the actual installed terminal: connected non-demo account, three timeframes
with 120 bars each, and pending-order metadata were read. A hypothetical 0.01-lot
request returned `order_check.retcode=0`. The bridge never calls `order_send`,
modifies a position or cancels an order. Market closure/future broker acceptance
is not validated by preflight. Private data remains outside Git.

Observed checks: `make build test check-style` passed; after adding the final
regressions, Agent **139 passed**, Tools **159 passed**. Trading-specific tests
cover exact approval/snapshot binding, expiration, strategy ownership, lot limit
and step, stale quotes, UNKNOWN/NO_SETUP and native preflight without submission.
Real Agent-signed request → Tools → installed MT5 returned `TERMINAL_READ_ONLY`
and `broker_executed=false`. Services were restarted and health checks passed.
`uv run python scripts/test_stack.py`: **103 passed, 7 skipped in 380.61s**
against an isolated database. Skipped actual external tests are not counted as
proof of real MT5 order execution.

This is not complete autonomous trading: simulator receipts are process-local
test evidence only; durable proposal approval/client cards, chart import and
browser ChatGPT handoff remain pending. No demo-trade execution or real order
submission has been verified. See [MT5 scope and runbook](architecture/mt5-trading.md).

## MT5 domain routing correction (2026-10-24)

Explicit MT5/XAUUSD terminal requests now take precedence over generic computer,
task and browser-commerce classification. “帮我下单xauusd” and “用mt5下单安”
enter the existing read/preparation Skill; they cannot create a brokerage website
Run. Stale browser/login context is excluded from the current system context.
Explicit website documentation requests remain browser-capable; recurring read
monitor requests retain the existing scheduler path. No trading permission or
live order dispatch is added. MT5 progress no longer shows travel labels or
forces Tavily search merely because a Skill was selected.

Observed: Agent **149 passed**; related browser/task-kernel integration **9 passed
in 32.49s**; two full isolated chat regressions **2 passed in 7.73s**, checking
the frozen MT5 Skill prompt and absence of Automation browser Runs despite
synthetic stale brokerage/login history. These use the test model and do not
execute trades or validate broker execution. Python compilation, Ruff, style and
architecture checks passed. Agent restarted; all four readiness endpoints UP.
No database migration was required.

## Gold-language routing and complete reply regression (2026-10-24)

The previous MT5 correction covered literal MT5/XAUUSD but missed the actual
phrase “帮我下一单黄金的交易”. Common spot-gold trading language now selects
the same MT5 Skill before generic tasks/browser routing; physical gold,
jewellery, ETF and futures are not silently normalized. Added buying/long/short/
lot-size/order variants and negative product cases. The receipt guard still
rejects unverified success claims, but no longer asks for unrelated todo/schedule
“事项及时间”. Missing trade parameters and terminal read errors use the trading
reply policy, without exposing internal error codes or promising real execution.

Observed verification:

- Agent: **167 passed**; Tools trading: **12 passed**; script tests: **17 passed**.
- Java App/kernel tests and `make build check-style` passed; architecture and Ruff passed.
- Isolated four-phrase chat regression: **4 passed in 17.12s**.
- Real Qwen language checks of the two gold phrases, with synthetic stale website
  history: **4 passed in 39.90s** (two real model responses; two mock controls).
- Final real Qwen run with stale website **and task-error** history, terminal
  disabled by fixture: **4 passed in 22.69s**. Explicit terminal-read + real
  Qwen original-phrase acceptance: **1 passed, 3 deselected in 7.41s**.
- After final plain-language reply policy: real Qwen original phrase with terminal
  blocked: **1 passed, 3 deselected in 8.22s**; no internal BLOCKED_EXTERNAL code
  in the reply, no browser Run, no unrelated task-time request.

Real model tests use isolated App/Agent/Automation databases. Native reads are now
separately opt-in; no test submits, cancels or modifies a financial order. These
checks establish routing/context/reply behavior, not a complete trading workflow.
No database migration or iOS binary change was required.
