# Skills and the travel-to-booking roadmap / Skill 与旅行交易演进

Adex now includes a **versioned, built-in Skill mechanism**. Travel is the first
implementation. It is a bounded planning workflow on the existing Agent runtime,
not an unrestricted autonomous browser or a third-party skill marketplace.

## 当前可用

- `trading.mt5-research@1.0.0`：通过本机 MT5 Wine 桥接读取 XAUUSD 三周期行情和挂单，注入只读证据；不发送或取消实盘订单。测试模拟器与终端预检均不能代表真实成交。当前范围和缺项见 [MT5 设计与验收](mt5-trading.md)。

- `travel.plan@1.0.0`：仓库维护的 TOML 定义，包含执行阶段、能力与质量规则。
- 注册表拒绝重复 ID 和不支持的能力；不加载远程代码或用户上传的提示词。
- 计划编译器识别明确天数与交易意图，保持普通行程规划在当前对话执行。
- 两轮顺序检索：地点／路线与营业时间／预约要求／交通；沿用 Tools 用户权限和预算。
- 第二轮失败保留第一轮证据并标记未核实，不将缺失信息包装成事实。
- 支持明确的行程局部修改承接上下文；用户本轮要求优先于已有偏好。
- 编译后的 Skill 标识、策略和证据进入已持久化的交互计划／后台 Checkpoint 消息；重试复用旧计划。
- 酒店下单、景点预约未接入真实供应商，状态为 `BLOCKED_EXTERNAL`，不产生虚构成交回执。

## 实现入口

| 文件 | 职责 |
| --- | --- |
| `services/adex-agent/src/adex_agent/skills/contracts.py` | 不可变 SkillDefinition / SkillPlan |
| `services/adex-agent/src/adex_agent/skills/registry.py` | 白名单、注册、选择和有限上下文承接 |
| `services/adex-agent/src/adex_agent/skills/builtin/travel.toml` | Travel 的版本、阶段与可信规则 |
| `services/adex-agent/src/adex_agent/skills/travel.py` | 明确天数、交易意图与有界检索计划 |
| `services/adex-agent/src/adex_agent/execution/context.py` | 授权检索、证据与记忆装配、可信策略 |
| `services/adex-tools/src/adex_tools/booking/contracts.py` | 未来报价／提交／对账接口与未启用能力状态 |

## 如何增加 Skill

1. 在 Agent 中提交可信定义与编译器，说明输入、阶段、只读能力、预算和结果质量要求。
2. 显式接入注册表，不从名字推导模块导入，也不允许模型选择任意 Python 函数。
3. 使用已有 owner-scoped 工具；新工具先定义契约、权限和失败行为。
4. 添加选择、无关请求、重试、检索失败、约束解析和权限拒绝测试。
5. 写入 ADR 和可用性边界。Skill 声明不能替代后端权限或用户审批。

## 下一阶段

目前仍由模型输出 Markdown 行程，路线、预算、营业时间等规则通过策略引导；尚无独立路线求解器和语义质量评分。下一步应让模型输出类型化行程，增加天数／时段／交通／预算校验，再接地图与授权供应商，而不是继续堆提示词。

预约和下单必须基于有库存、有效期与完整条款的真实报价。展示具体确认卡片，用户批准对应快照后才能经持久效果账本提交；价格或条款变化必须重新确认。网络超时先对账，不能盲目再订。完整设计见 [ADR 003](../adr/003-skills-and-transaction-boundaries.md)。

See [ADR 003](../adr/003-skills-and-transaction-boundaries.md) for the English decision,
transaction consent invariants, remaining quality gates and supplier integration plan.
