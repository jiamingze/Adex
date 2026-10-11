# 技术架构

[English](../en/architecture.md) · [首页](../../README.zh-CN.md)

## 四个业务域

| 服务 | 技术 | 数据职责 |
| --- | --- | --- |
| App | Java 21 / Spring Boot | 用户、会话、消息、记忆、文件、作品与公共 API |
| Automation | Java 21 / Spring Boot | 日程、任务发生、Run、租约与结果交付 |
| Agent | Python / FastAPI | 上下文、路由、模型调用与不可变 Checkpoint |
| Tools | Python / FastAPI | 供应商适配器、工具效果账本、媒体 Job 与对账 |

Runner 属于隔离执行基础设施，不新增业务服务。服务通过专属 PostgreSQL schema 和角色访问各自数据，内部调用校验 issuer、audience、scope、owner 与 resource；客户端只访问 App。

## 一次聊天

客户端提交消息、`client_message_id` 和模型选择。App 校验身份并持久化用户消息及 Turn，返回接受回执。Agent 组装上下文，按需搜索或读取附件，再把处理进度和回答增量发送给 App。App 发布持久事件，最终原子提交回答与卡片。SSE 用事件序号恢复，iOS 同时保留快照拉取降级。

客户端的乐观消息不是权威状态。相同消息标识必须保持幂等。思考界面展示有限的处理状态，不公开模型隐藏推理。定时与创作意图先经过功能路由，实际成功必须来自服务回执，不能相信模型编造的任务 ID。

## 三层记忆

- L1：Redis 工作态缓存，可从权威数据重建。
- L2：持久会话消息与摘要。
- L3：有版本、来源和用户查看、纠正、删除能力的长期事实。

Memory、Agent Checkpoint、Automation Run 是三种不同状态。删除采用墓碑和版本检查，防止旧摘要、延迟提取和索引重建恢复用户已删除的事实。

## 自动化与恢复

调度器在短事务内通过 `FOR UPDATE SKIP LOCKED` 领取到期任务，用 `(schedule_id, scheduled_at)` 唯一约束保证一次逻辑发生。Worker 用租约、fencing epoch 和 attempt ID 领取执行权，模型与浏览器运行不持有数据库锁。

Agent 先写不可变 Checkpoint，Automation 再 CAS 提交引用。外部操作使用稳定 effect key 和供应商 Job ID，UNKNOWN 状态通过对账处理，不能盲目重发。Outbox 与消费去重把结果回流原对话。这是恢复与去重机制，不承诺供应商侧绝对 exactly-once，也不把单机描述成高可用部署。

## 文件、媒体与安全

App 管理私有磁盘文件和 PG 元数据。写入采用临时文件、持久元数据、原子重命名和 READY 状态，包含完整性与配额校验。播放使用绑定会话的短期票据，支持 Range。作品保留不可变版本与可编辑源。

生成 HTML 在独立 origin 和受限 Runner 中运行，不能在 App 主域执行任意代码。附件、网页与供应商内容作为不可信数据。商业歌曲目录不提供播放授权，真实媒体与 Mock 样例明确区分。

## 故障边界

PostgreSQL 不可用时拒绝不安全写入；Redis 故障退化为缓存未命中；Elasticsearch 异步重试并退回 PG 搜索；磁盘异常报告存储或完整性失败；供应商异常保留拒绝、超时或 UNKNOWN 状态。

继续阅读 [服务契约](../SERVICE_CONTRACTS.md)、[文件存储](../LOCAL_FILE_STORAGE.md)、[运维恢复](../RUNBOOK.md) 与 [原始设计](../Adex_Product_Technical_Design_v4.1.md)。设计是目标契约，是否通过测试要看验收证据。
