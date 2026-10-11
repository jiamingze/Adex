# Development and learning path

[中文](../zh-CN/development.md)

## Read a complete vertical slice

1. `apps/web/src/main.tsx` and `api.ts`: optimistic UI, durable snapshots, streaming and model selection.
2. `services/adex-app/.../ChatStore.java`, `ChatWorker.java`: transactional message acceptance and execution.
3. `services/adex-agent/src/adex_agent/main.py`, `runtime.py`, `provider.py`: routing, memory context, model protocol filtering.
4. Automation scheduler and worker: occurrence uniqueness, leases, attempts and checkpoint references.
5. Tools `creative.py` and provider modules: stable effect keys, reconciliation and private file import.
6. `migrations/`: actual persistence boundaries and indexes; compare these with design docs.

## Commands

```bash
make build
make test
make test-contract
make test-integration
uv run python scripts/check_secrets.py
pnpm generate:contracts
```

`make test` runs Java and Python checks plus contracts. Integration tests use isolated databases with mock providers. Runner/container verification may require Docker; real provider checks must be explicitly opted into and budgeted. Do not modify personal data as a test fixture.

## Working safely

Read root `AGENTS.md` and the current design contract. Change service contracts/migrations first, then meaningful tests and implementation. Keep ordinary chat out of Automation unless background execution is requested. Never replace durable memory or task state with Redis-only storage.

Persist task state before external effects. Do not retry an unknown paid provider submission automatically. Preserve lease/epoch checks and deletion tombstones. Keep private files behind App authorization.

## Git workflow

```bash
git switch -c feature/your-change
# edit, verify, and review
git add <files>
git diff --cached
uv run python scripts/check_secrets.py
git commit -m "Describe the concrete change"
git push -u origin feature/your-change
```

Create a pull request with what changed, why, verification evidence and limitations. Use the templates in `.github/`. Do not include logs with API keys, personal conversations, generated private media or signing credentials. See [contributing](../../CONTRIBUTING.md).

[IntelliJ IDEA / PyCharm 独立调试](jetbrains.md)
