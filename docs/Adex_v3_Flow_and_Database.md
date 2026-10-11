# Adex v3.1 · 四服务端到端流程与数据库读写

> 与 v3.1 设计保持一致：四个业务服务为 `adex-app` / `adex-agent` / `adex-automation` / `adex-tools`；Frontend 为 Web / Desktop / Mobile；Runner 独立隔离；PostgreSQL + Redis 是首期权威/缓存组合，Elasticsearch 为可选检索基础设施。图中端点是建议契约，不代表已上线。

## 数据所有权与读写

| 服务 | 关键模块 | 主要 PG / Redis / ES 数据 |
|---|---|---|
| App | Identity、Conversation、Knowledge、Memory L2/L3、Workspace、UI、Notification | PG：完整消息、用户、摘要、长期记忆、通知；Redis：L1 缓存；ES：异步索引及搜索 |
| Agent | Context Builder、Model Gateway、Planner、Skills Loader | 通过 App Context API 读取记忆，不能直接写 App 的表；Agent 内部保存必要配置与诊断 |
| Automation | Task/Run、Schedule、Monitor、Subscription、Rule、Outbox | PG：调度、任务、监控观测及业务触发；可通过受控接口做 ES 候选检索 |
| Tools | MCP、Connectors、Skill/Tool Registry、Browser/Code | PG：工具/凭证引用/Effect；Redis：可重建工具缓存；Runner：独立隔离 |

## 三层记忆

| 层 | 内容 | 存储 |
|---|---|---|
| L1 Working Memory | 当前上下文、短期状态、工具热结果 | Agent Runtime / Redis，缓存可失效 |
| L2 Conversation Memory | 原始聊天与会话摘要 | App PostgreSQL，长期保存且可重建摘要 |
| L3 Long-term Memory | 跨会话个人事实、偏好、画像、语义记忆 | App PostgreSQL 权威，ES 为可重建检索索引 |

## 流程说明


### ① 普通聊天 / 多轮记忆 / 联网问答 / 大卡
同步交互主链路；不创建 Automation Task。ES 只在检索相关记忆、知识或历史时使用。

| # | 调用链 | 操作类型 | 接口 / 关键操作 | 数据访问 |
|---:|---|---|---|---|
| 1 | `client → app` | 调用 | POST /v1/chat/turns | — |
| 2 | `app → redis` | 读取 | GET auth/rate-limit cache | Redis R |
| 3 | `app → pg` | 读取 | SELECT identity + conversation + usage | PostgreSQL R |
| 4 | `app → pg` | 写入 | INSERT conversation.messages + outbox | PostgreSQL W |
| 5 | `app → agent` | 调用 | POST /internal/agent/turns | — |
| 6 | `agent → app` | 调用 | GET /internal/conversations/{id}/context | — |
| 7 | `app → redis` | 读取 | GET chat:context:* | Redis R |
| 8 | `app → pg` | 读取 | SELECT messages / conversation_summaries | PostgreSQL R |
| 9 | `app → pg` | 读取 | SELECT memory.entries | PostgreSQL R |
| 10 | `app → es` | 读取 | _search chat / memory / knowledge (optional) | ES R |
| 11 | `app → agent` | 返回 | 200 ContextPackage | — |
| 12 | `agent → tools` | 调用 | POST /internal/tools/{name}:invoke | — |
| 13 | `tools → ext` | 调用 | HTTPS provider API | — |
| 14 | `ext → tools` | 返回 | tool result | — |
| 15 | `tools → agent` | 返回 | 200 ToolResult | — |
| 16 | `agent → ext` | 调用 | LLM streaming API | — |
| 17 | `agent → app` | 流 | HTTP stream / NDJSON | — |
| 18 | `app → client` | 流 | SSE /v1/chat/turns | — |
| 19 | `app → pg` | 写入 | INSERT/UPDATE messages + usage | PostgreSQL W |
| 20 | `app → redis` | 写入 | SET/DEL chat:context:* | Redis W |
| 21 | `app → es` | 索引 | INDEX chat_messages (async) | ES W |
| 22 | `agent → app` | 事件 | memory.candidate | PostgreSQL W (App 内处理) |

**关键约束：**
- 普通聊天不进入 Automation；App 先持久化用户消息，Agent 使用 App 提供的授权 Context API 读 L1/L2/L3。
- 大卡由 Agent 产生结构化建议，App 校验 UI Schema 后通过 SSE 下发，客户端渲染。
- ES 通过可重放索引事件异步写入，不是原始聊天数据的权威来源。

### ② 创建定时任务 → 到期 → Agent 执行 → 通知
例：明天 08:00 根据天气推荐亲子酒店或景点；真正的执行发生在未来，Scheduler 不直接调用 LLM。

| # | 调用链 | 操作类型 | 接口 / 关键操作 | 数据访问 |
|---:|---|---|---|---|
| 1 | `client → app` | 调用 | POST /v1/chat/turns | — |
| 2 | `app → pg` | 写入 | INSERT conversation.messages | PostgreSQL W |
| 3 | `app → agent` | 调用 | POST /internal/agent/turns | — |
| 4 | `agent → app` | 返回 | automation.proposal | — |
| 5 | `app → client` | 返回 | ui: automation_confirm_card | — |
| 6 | `client → app` | 调用 | POST /v1/automations | — |
| 7 | `app → auto` | 调用 | POST /internal/automations | — |
| 8 | `auto → pg` | 写入 | INSERT schedule.schedules, outbox | PostgreSQL W |
| 9 | `auto → app` | 返回 | 201 automation.created | — |
| 10 | `app → client` | 返回 | ui: automation_card | — |
| 11 | `auto → pg` | 读取 | SELECT ... FOR UPDATE SKIP LOCKED | PostgreSQL R |
| 12 | `auto → pg` | 写入 | INSERT occurrence/run/outbox + UPDATE schedule | PostgreSQL W |
| 13 | `auto → agent` | 事件 | run.ready event | — |
| 14 | `agent → auto` | 调用 | POST /internal/runs:claim | — |
| 15 | `auto → pg` | 写入 | UPDATE task_runs ... RETURNING epoch | PostgreSQL W |
| 16 | `agent → tools` | 调用 | POST /internal/tools/weather:invoke | — |
| 17 | `tools → ext` | 调用 | Provider API | — |
| 18 | `tools → agent` | 返回 | ToolResult | — |
| 19 | `agent → ext` | 调用 | LLM API | — |
| 20 | `agent → auto` | 调用 | POST /internal/runs/{id}/steps:commit | — |
| 21 | `auto → pg` | 写入 | UPDATE task_runs + INSERT events/outbox | PostgreSQL W |
| 22 | `auto → app` | 事件 | notification.requested | — |
| 23 | `app → pg` | 写入 | INSERT notification.messages | PostgreSQL W |
| 24 | `app → push` | 调用 | APNs / FCM / others | — |
| 25 | `push → client` | 事件 | push notification | — |

**关键约束：**
- `UNIQUE(schedule_id, scheduled_at)` 保证单个计划时刻至多有一个逻辑 Occurrence。
- Worker 使用持久化队列信号+claim、Lease、epoch 和 Step Checkpoint；执行尝试可能多次，外部副作用需独立幂等。
- 单纯定时提醒可绕过 Agent，直接从 Automation 产生通知意图。

### ③ 监控订阅 → 共享采集 → 规则匹配 → 推送
例：关注周杰伦上海演唱会。用户创建的是 Subscription，Monitor 可跨用户共享；发现变化通常无需 LLM。

| # | 调用链 | 操作类型 | 接口 / 关键操作 | 数据访问 |
|---:|---|---|---|---|
| 1 | `client → app` | 调用 | POST /v1/chat/turns | — |
| 2 | `app → agent` | 调用 | POST /internal/agent/turns | — |
| 3 | `agent → app` | 返回 | monitor.proposal | — |
| 4 | `app → auto` | 调用 | POST /internal/automations | — |
| 5 | `auto → pg` | 写入 | UPSERT monitor + INSERT subscription | PostgreSQL R/W |
| 6 | `auto → app` | 返回 | 201 subscription.created | — |
| 7 | `app → client` | 返回 | ui: monitor_card | — |
| 8 | `auto → pg` | 读取 | SELECT due monitor / source_event_id | PostgreSQL R |
| 9 | `auto → tools` | 调用 | POST /internal/tools/source:collect | — |
| 10 | `tools → ext` | 调用 | WebSearch / Provider API | — |
| 11 | `ext → tools` | 返回 | SourceEvent[] | — |
| 12 | `tools → auto` | 返回 | 200 observations | — |
| 13 | `auto → pg` | 写入 | INSERT monitor.observations | PostgreSQL W |
| 14 | `auto → es` | 读取 | _search monitor_events or percolate (optional) | ES R |
| 15 | `auto → pg` | 读取 | SELECT subscriptions + rules | PostgreSQL R |
| 16 | `auto → pg` | 写入 | INSERT trigger_events/outbox | PostgreSQL W |
| 17 | `auto → app` | 事件 | notification.requested | — |
| 18 | `app → pg` | 写入 | UPSERT notifications | PostgreSQL W |
| 19 | `app → push` | 调用 | provider Push API | — |
| 20 | `push → client` | 事件 | push | — |
| 21 | `ext → app` | 事件 | POST /v1/webhooks/{provider} (optional) | — |

**关键约束：**
- 用户 Subscription 不共享，允许共享公共采集 Monitor。
- 有实时 Webhook 可优先事件驱动，Polling 可作补偿；两个来源都须归一化与去重。
- ES 用于复杂文本候选，不用于替代精确阈值的数据库过滤与规则判断。

### ④ 网页预约 / Computer Use / 长任务恢复
授权允许的第三方网页操作。浏览器 Worker 独立沙箱，带 effect_key、检查点和用户接管，不承诺第三方交易 exactly-once。

| # | 调用链 | 操作类型 | 接口 / 关键操作 | 数据访问 |
|---:|---|---|---|---|
| 1 | `client → app` | 调用 | POST /v1/chat/turns | — |
| 2 | `app → agent` | 调用 | POST /internal/agent/turns | — |
| 3 | `agent → app` | 返回 | booking.proposal | — |
| 4 | `client → app` | 调用 | POST /v1/grants/{id}/approve | — |
| 5 | `app → auto` | 调用 | POST /internal/tasks | — |
| 6 | `auto → pg` | 写入 | INSERT task / run / outbox | PostgreSQL W |
| 7 | `auto → agent` | 事件 | run.ready | — |
| 8 | `agent → auto` | 调用 | POST /internal/runs:claim | — |
| 9 | `auto → pg` | 写入 | UPDATE task_runs | PostgreSQL W |
| 10 | `agent → tools` | 调用 | POST /internal/tools/browser:invoke | — |
| 11 | `tools → pg` | 写入 | UPSERT tool.effects | PostgreSQL R/W |
| 12 | `tools → runner` | 调用 | Runner Control API | — |
| 13 | `runner → ext` | 调用 | Browser UI actions | — |
| 14 | `runner → oss` | 写入 | PUT object screenshot/evidence | OSS W |
| 15 | `runner → tools` | 返回 | RunnerResult | — |
| 16 | `tools → agent` | 返回 | ToolResult | — |
| 17 | `agent → app` | 事件 | takeover.requested | — |
| 18 | `app → client` | 返回 | ui: browser_takeover_card | — |
| 19 | `agent → auto` | 调用 | POST /internal/runs/{id}/steps:commit | — |
| 20 | `auto → pg` | 写入 | UPDATE step/run + INSERT outbox | PostgreSQL W |
| 21 | `agent → auto` | 调用 | POST /internal/runs/{id}:complete | — |
| 22 | `auto → app` | 事件 | result.ready | — |
| 23 | `app → pg` | 写入 | INSERT conversation.message + notification | PostgreSQL W |
| 24 | `app → client` | 流 | SSE / Push | — |

**关键约束：**
- 只有允许的第三方网页自动化才能执行；验证码、支付和人工验证走受控接管。
- Browser Runner 必须与 Tools API 进程隔离；外部提交超时后先核对状态而不是直接重复点击。
- Automation 的 Run/Step 状态和 Tools 的外部 Effect 状态相互引用但所有权独立。

## 部署说明

- 同一 Monorepo，四个后端服务可以单独构建、运行与部署；Browser Runner 与 Agent Worker、Scheduler/Monitor Worker 分进程扩容。
- 初期 PostgreSQL + Redis；ES 视跨会话搜索、RAG 和语义检索需求开启。ScyllaDB 属未来消息存储适配选项，图中当前的消息权威存储仍是 PostgreSQL。
- 所有服务只通过带鉴权的内部 API、授权快照和持久事件协作，不允许越权访问其他服务的业务表。