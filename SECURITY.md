# Security policy

Adex is early-stage software. There are no supported stable release branches yet; fixes target the current main branch. Self-hosters are responsible for HTTPS, secrets, access controls, backups and provider budgets.

## Reporting

Do not publish credentials, exploit payloads containing private data, or sensitive logs in a public issue. Use the repository's Security → Report a vulnerability feature if enabled. If unavailable, open a minimal issue requesting a private reporting channel without disclosing the vulnerability. No private-reporting response SLA is promised.

## Deployment checklist

- Generate distinct credentials; never use example placeholders or a shared developer password.
- Keep `.env`, signing material, database directories, backups and generated media out of Git.
- Expose only the authenticated HTTPS gateway; keep databases and internal services private.
- Configure exact allowed origins and provider budgets. Guest use is intentionally limited.
- Treat HTML, uploaded documents and model output as untrusted data.
- Back up PostgreSQL and local file storage together; practice restoration.

注册仅要求非空密码，部署者应评估是否需要加强密码策略；当前项目不应在未经安全审查时作为公开多租户生产服务。安全问题不要在公开 Issue 中披露密钥或个人数据。
