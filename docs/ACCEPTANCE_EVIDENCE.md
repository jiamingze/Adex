# 一期验收证据（2026-10-11）

范围：本机 Web / native 四服务 / 隔离 Compose。`PASS_LOCAL` 仅指下列已执行场景，不代表全部生产发布门禁通过。尚无 Git 提交；源码 SHA 清单为 `VALIDATION_MANIFEST.json`。执行者：Codex；仍需人工生产审核。

| 门禁 | 状态 | 实际证据与剩余边界 |
|---|---|---|
| ACC-01 | PASS_LOCAL | 同消息并发、客户端幂等键、消息/任务唯一性，25 项集成测试 |
| ACC-02 | PARTIAL | Web SSE 序号回放及最终快照通过；iPhone 杀进程未测 |
| ACC-03 | PASS_LOCAL | 长期记忆墓碑、修订及旧结果丢弃；会话删除后的关联记忆和延迟抽取不复活；真实 ES 墓碑；L2 为摘录摘要 |
| ACC-04 | PASS_LOCAL | Redis/ES 不可达降级、PG 中断拒写和恢复；测试使用独立数据库 |
| ACC-05 | PASS_LOCAL | 3 个调度器竞争、occurrence 唯一、并发领取 |
| ACC-06 | PASS_LOCAL | checkpoint 提交后 SIGKILL，epoch 增长，新 attempt 复用冻结计划；无重复模型调用 |
| ACC-07 | PASS_MOCK | 调用 UNKNOWN 不重提，已有 provider job 查询对账；真实 CalDAV/SMTP 未配置 |
| ACC-08 | PARTIAL | 重投事件与同 Run 去重通过；尚未覆盖每一个 publisher 指令点的强杀 |
| ACC-09 | PARTIAL | Apple 真实目录 12 条、合法 Mock WAV、商业歌曲官方跳转；真机音频焦点未测 |
| ACC-10 | PARTIAL | MiniMax/Tavily 杭州旅行 Run 完成、地点坐标及天气；商业库存/价格未验证、更广泛日期地区未验收 |
| ACC-11 | PASS_LOCAL | Web iframe 计数 0→1、parent 访问被阻止；无网络 Docker Runner 与无限循环清理通过 |
| ACC-12 | BLOCKED_EXTERNAL | Capacitor sync / Swift 语法通过，缺完整 Xcode、Personal Team 真机环境 |
| ACC-13 | PASS_LOCAL | 备份 20261010T225429Z，fresh DB 恢复与 checkpoint/file SHA 验证通过；本地备份未异地复制 |
| ACC-14 | PARTIAL | 监控状态、取消及去重账务已实现；完整实际采集回放与故障组合仍需更广泛验收 |
| ACC-15 | PASS_LOCAL | 跨用户权限、内部 scope、独立 DB roles、模型预算拒绝 |
| ACC-16 | PARTIAL | 真实研究和游戏完成，源文件、修订和受控分享验证；更多游戏迭代用例未全覆盖 |
| ACC-17 | PASS_LOCAL | 商业目录路径不提供站内音频；仅官方链接；站内音频来自私有文件库 |
| ACC-18 | BLOCKED_EXTERNAL | 无 ECS 主机，无法执行整机重启演练 |
| ACC-19 | PASS_LOCAL / BLOCKED_EXTERNAL | 隔离 Compose App 强制重建后消息、文件 SHA 与鉴权 Range 保持；ECS 磁盘挂载仍待实测 |
| ACC-20 | PARTIAL | UUID 存储、上传幂等、路径/权限、PENDING/孤儿回收及磁盘余量保护；未穷举所有上传指令点强杀及真实磁盘耗尽 |
| ACC-21 | PASS_LOCAL | Mermaid 源第二版、纯 SVG 标签、SVG/白底 PNG 导出并登记版本，危险 SVG 拒绝；浏览器实际下载检查文字/箭头 |
| ACC-22 | PASS_MOCK / BLOCKED_EXTERNAL | 确定性 PNG、引用权限与 provider 接口；未接真实生成/编辑供应商 |
| ACC-23 | PASS_MOCK | 确定性原创样例 WAV、私有下载、版本和防重复发布；真实音乐生成供应商待提供 |
| ACC-24 | PARTIAL / BLOCKED_EXTERNAL | Mock MP4/海报/鉴权 Range、provider job 恢复；真实生成与 iPhone 视频播放待验证 |
| ACC-25 | PASS_MOCK | HMAC webhook、重复/乱序回调、UNKNOWN 对账、旧租约拒绝，无重复文件/作品 |
| ACC-26 | PARTIAL | SSRF/范围/权限校验、恢复 SHA 与受控容量保护；真实磁盘满、ECS 恢复及供应商输入仍待验证 |

## 执行记录

- `make build`：Java / TS / Vite 成功；Mermaid 分包体积告警保留。
- `make test`：Java 4、Agent 9、Tools 6 项通过；OpenAPI 53 operations。
- `make test-integration`：25 passed。最新日志 `.local-data/travel-markdown-integration.log`。
- 四业务服务、Web、Migrate、Code Runner 和 Gateway Docker 镜像构建成功；Compose `config --quiet` 通过。
- `uv run python scripts/verify_compose.py`：四服务真实就绪、Mock chat、私有 Range、App recreate 后消息/文件 SHA、签名隔离 Runner 全通过。日志 `.local-data/compose-verification.log`。临时 Compose 已停止，测试卷保留。
- `scripts/verify_runner.py`：错误签名拒绝、正常渲染和无限循环超时清理通过。日志 `.local-data/final-runner-gateway.log`。
- 真实 MiniMax/Tavily、文件问答、研究/旅行、音乐、游戏记录在 `.local-data/real-*.log`；不是 CI 默认外部调用。
- MiniMax 图片理解：合成 800×500 图文字及颜色正确，96px 纯色图片颜色识别失败。保留供应商精度限制，不能当作可靠视觉事实验证器。
- `scripts/backup.py` + `scripts/restore_drill.py`：恢复 17 消息、10 Run、11 checkpoint、18 文件、10 作品；19 备份对象校验通过。日志 `.local-data/final-backup.log` / `final-restore.log`。
- `scripts/check_secrets.py`、`make doctor` 通过；密钥仅在忽略的 0600 私密配置中。

日志、数据库、备份、私密配置和合成验收截图不随 Git 提交。正式上线前仍需补齐上述 PARTIAL 和 BLOCKED_EXTERNAL，不能宣称 ACC-01..26 全 PASS。

行程交互修复补充：9 项 Agent 测试、25 项集成测试、Web 构建通过；原用户会话的 6 个表格实际渲染。真实同文请求在隔离验收账户下直接由 MiniMax 流式回答并使用 Tavily 来源卡，未创建后台任务、未给机酒金额；日志 `.local-data/travel-interactive-real-final.log`。旧记录的营销报价和旧通知不改写，新的提示约束仍不能代替预订前的事实核实。
