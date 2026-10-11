# Contributing to Adex

Thank you for helping make Adex easier to use and understand. / 欢迎帮助改进 Adex。

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
