# Starter tasks / 入门贡献

These are proposed, bounded tasks, not promises of assignment or production readiness.
Check [open issues](https://github.com/jiamingze/Adex/issues) before starting; comment
with your scope to avoid duplicate work. Read [CONTRIBUTING](../../CONTRIBUTING.md).

以下任务可独立完成，开始前请查看 Issues 并沟通范围。不要求每位贡献者都购买模型或拥有 iPhone。

| Task / 任务 | Start here / 入口 | Done when / 验收 |
| --- | --- | --- |
| Fresh-install feedback on Ubuntu / Ubuntu 安装复现 | [Installation](../en/installation.md), `make demo-ui`, `make setup` | Record OS/tool versions and a sanitized failing command, or improve a verified instruction in both languages. No real keys or `.env`. |
| Keyboard accessibility in the demo / 演示页键盘可访问性 | `apps/web/src`, `make demo-ui` | Reproduce one focus-order/label/keyboard issue, submit a focused fix and before/after keyboard steps. Do not disable text selection globally. |
| Document one chat-to-note code path / 聊天转笔记代码导读 | `apps/web/src/ReplyNoteAction.tsx`, App note application service, Agent note composition | One short bilingual walkthrough linking actual symbols and explaining ownership, retries and failure behavior. Validate all paths and links. |

Use `mock` providers or synthetic UI data for first contributions. Mock responses do
not prove real website/model compatibility. Do not change signing, personal accounts,
production data, service ownership or task scheduling as part of these starter tasks.

## How to report a useful first-run issue

Include the source commit, OS, executable versions, exact sanitized command, expected
behavior and actual error. State whether it is UI-only demo or the real four-service
application. Omit keys, cookies, private URLs, personal content and device identifiers.

复现报告请包含提交版本、操作系统、工具版本、脱敏命令与错误，并说明是界面演示还是完整应用。
