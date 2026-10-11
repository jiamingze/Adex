# ADR 001 — 本次交付范围

用户明确授权 Web 聊天、定时任务及工业级持久性底座，因此本次按 M00→M01→M02(core)→M03→M04→M05(core) 的依赖順序迭代。iOS、旅游、音乐、多模态、任意代码执行推迟。原设计文档保留为完整路线图，不代表已实现。

四个业务域及原语言不变；数据库采用四个独立 schema / role。共享 Java kernel 仅包含认证、数据库和 HTTP 基础组件，不构成第五个业务域。

单 owner 部署使用 BCrypt 密码与 PG 中保存哈希的 12 小时 opaque bearer session，前端只保存在内存。无默认管理员、注册、刷新令牌或匿名 API。内部 HMAC capability 是 3 分钟有效、含 issuer/audience/scope/owner/resource 的签名授权，各 issuer 独立密钥。生产使用 HTTPS，凭证通过环境注入。

日程支持 once / interval / daily，daily 使用 IANA timezone；DST gap 采用时区库前移规则，重复时间只触发一次。错过执行合并为一次，下一次推进到未来，避免恢复风暴。每个日程一个进行中 run，前次尚未结束则本轮跳过并记录 occurrence。

遗忘优先：L3 删除或纠正增加 memory revision、清除 L2 摘要，并将删除前历史排除出后续模型上下文（UI 历史保留）。后台结果发布校验当前 revision；旧上下文结果不能重新附加。此策略保守，牺牲部分历史上下文以避免语义改写复活。墓碑保持，显式重新添加同内容返回冲突。

模型默认 MiniMax-M2.5，兼容接口由 Agent 隔离。测试必须显式选择 mock。模型调用已发送而结果未知时进入 UNKNOWN，真实供应商不盲重试；可能重复计费的调用须人工重新发送新的逻辑请求。搜索按用户要求使用 Google HTTP，只读、有限大小/超时、无验证码绕过，返回来源与抓取时间；Google HTML 变化可能导致不可用。

Checkpoint 是 Agent 的 immutable PG 对象（本次小 JSON，不包含二进制）；先写 checkpoint 再向 Automation CAS 提交 ref。未提交对象保留为孤儿供诊断，禁止自动从未提交对象恢复。大型对象未来通过 App LocalFileStorage。

## 范围更新
用户最新指令覆盖此前延期范围：实现一期 M00–M16，按依赖顺序推进；搜索改为 Tavily API。真实媒体供应商、真机签名和云部署验收仍须具备外部条件后验证。
