# Contributing to Adex

Thank you for helping make Adex easier to use and understand. / 欢迎帮助改进 Adex。

## Your first contribution / 第一次参与

Contributions are welcome from beginners and experienced developers alike. Code, UI/UX design, iPhone/browser testing, provider adapters, documentation and reproducible bug reports all help.

欢迎新朋友和有经验的开发者一起参与。除了代码，界面设计、iPhone/浏览器测试、模型适配、文档和可复现的 Bug 报告同样有价值。

Start with the [bounded starter tasks](docs/project/starter-tasks.md); try `make demo-ui` without a database or paid model. / 可先查看入门任务，无需数据库或付费模型即可体验界面。

1. Browse the [roadmap](ROADMAP.md) and [issues](https://github.com/jiamingze/Adex/issues), or propose a focused improvement. / 查看路线图和 Issues，或提出一个具体的改进。
2. Comment on the issue to coordinate scope; fork the repository and work on a feature branch. / 在 Issue 中沟通范围，Fork 仓库并创建开发分支。
3. Follow the installation guide, make the change, and run the relevant checks. / 按安装指南搭建环境，完成修改并验证。
4. Open a [pull request](https://github.com/jiamingze/Adex/pulls) describing the behavior and validation. / 提交 PR，说明改动和验证结果。

If you are unsure where to begin, open an issue describing your interests. Discussion and review can happen in English or Chinese. / 不确定从哪里开始，可以开 Issue 说明感兴趣的方向，支持中文或英文沟通。

## Before you start / 开始前

Read [development](docs/en/development.md) ([中文](docs/zh-CN/development.md)), `AGENTS.md`, and the relevant service contracts. Open an issue for substantial architecture changes. Small bug fixes and documentation corrections can go directly to a PR.

Use a feature branch and keep each PR focused. Include a reproducible trigger, concrete behavior change, checks run, and any provider/device limitations. Update both README languages when changing setup or user-facing capabilities.

## Verification / 验证

Run checks appropriate to the changed domain, plus contracts when APIs change. Real provider tests must be opt-in and cost-bounded. Device-specific claims need device evidence. Do not claim mocks establish real model compatibility.

## Reliability / 可靠性

Preserve service-owned schemas, transaction boundaries, idempotency, lease fencing, checkpoint ordering, outbox deduplication, and non-resurrection of deleted memory. Generated content is untrusted; keep it isolated.

## Privacy / 隐私

Never submit `.env`, keys, cookies, private user data, generated private media, signing profiles, device IDs or unredacted logs. Follow [SECURITY.md](SECURITY.md) for vulnerabilities. Be respectful and constructive in reviews; avoid personal attacks or sharing another person's private information.

## License / 许可

By submitting a contribution, you agree it may be distributed under the project's MIT license. Only submit work you have the right to contribute. Third-party assets require attribution and compatible licensing.

Community expectations: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). / 社区行为规范见该文件。
