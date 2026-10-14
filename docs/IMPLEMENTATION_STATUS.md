# 一期实现与验收记录

更新：2026-10-11，macOS / Java21 / Python3.12 / 本地 PostgreSQL16、Redis、Elasticsearch8.17.4。当前代码尚无 Git commit SHA；源码文件 SHA 清单见 `VALIDATION_MANIFEST.json`，结合工作区文件和本地测试日志作为证据，不能作为已发布生产版本证明。

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
