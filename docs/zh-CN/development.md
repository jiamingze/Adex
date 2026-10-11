# 开发与学习路线

[English](../en/development.md)

## 从一条完整链路开始

1. 阅读 Web 的 `main.tsx` 和 `api.ts`，理解乐观消息、SSE、快照与模型选择。
2. 阅读 App 的 `ChatStore.java`、`ChatWorker.java`，理解事务接受与执行。
3. 阅读 Agent 的 `main.py`、`runtime.py`、`provider.py`，理解路由、记忆和供应商协议过滤。
4. 阅读 Automation 调度器与 Worker，理解发生唯一性、租约、attempt 和 Checkpoint 引用。
5. 阅读 Tools 的 `creative.py` 与供应商模块，理解效果账本、对账和文件导入。
6. 对照 `migrations/` 与设计文档，理解权威状态和索引。

```bash
make build
make test
make test-contract
make test-integration
uv run python scripts/check_secrets.py
pnpm generate:contracts
```

集成测试使用独立数据库与 Mock。Runner/容器验证需要 Docker；真实供应商测试必须明确启用并控制预算，不使用个人数据作为测试夹具。

开发前阅读 `AGENTS.md` 与设计契约。先改契约、迁移和有意义的测试，再改实现。普通聊天不默认交给 Automation；不能用 Redis 替代持久记忆和任务；UNKNOWN 外部提交不能盲目重试；租约、epoch、墓碑和文件权限不能绕过。

## 提交修改

```bash
git switch -c feature/your-change
# 修改、验证、审查
git add <files>
git diff --cached
uv run python scripts/check_secrets.py
git commit -m "Describe the concrete change"
git push -u origin feature/your-change
```

PR 说明具体问题、行为变化、验证和限制，使用 `.github/` 模板。不要提交 Key、聊天内容、私有媒体或签名凭证，详见 [贡献指南](../../CONTRIBUTING.md)。

[IntelliJ IDEA / PyCharm 独立调试](jetbrains.md)
