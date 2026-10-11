# IntelliJ IDEA / PyCharm 独立开发与调试

[English](../en/jetbrains.md)

## 环境准备

```bash
make setup
make build
make up-dev
uv run python scripts/ide.py prepare
```

Java 21、Maven、uv、pnpm、PostgreSQL 和 Redis 都保留使用。私有环境由根 `.env` 按服务生成；`.idea` 和 `.local-data` 全部忽略，不要把其中的运行配置提交到 Git。生成的凭据文件权限为 600。修改 `.env` 后重新执行 prepare 刷新 Java 配置；Python 每次启动重新读取。

## IntelliJ IDEA：两个 Java 服务

**打开仓库根 `pom.xml`，作为 Maven 工程导入**，保持 App、Automation 与 java-kernel 在同一 reactor 中，避免共享库依赖断开。Project SDK 和 Maven Runner 选择 JDK 21；本机路径为 `/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home`。

生成的 `Adex app` / `Adex automation` 是标准 Application 配置，免费 IDE 也可用，不依赖 Spring 专属付费插件。它们使用各自 main class、模块、环境变量和独立 JVM。

启动前在终端让选中的服务释放端口：

```bash
uv run python scripts/ide.py handoff app
# 或 handoff automation
```

然后选择对应配置点击 Debug。App 8080、Automation 8081。停止调试后用 `make up-dev` 恢复普通运行；调试期间不要同时启动同一服务。

也可用仓库提供的远程 JVM 调试入口：

```bash
uv run python scripts/ide.py java-debug app
# 或 java-debug automation
```

选择 `Attach app (localhost:5005)` / `Attach automation (localhost:5006)` 点 Debug。此方式调试打包后的代码，源码改变后需重新 `make build` 并重启；调试端口仅绑定本机。

## PyCharm：两个独立 Python 工程

分别打开 `services/adex-agent` 和 `services/adex-tools`，选择新窗口。使用已有解释器：

- Agent：`services/adex-agent/.venv/bin/python`
- Tools：`services/adex-tools/.venv/bin/python`

每个工程都有生成的 `Adex agent` 或 `Adex tools` Python 配置，设置了明确的解释器路径。选择配置点 Debug 即可。入口 `scripts/ide_python.py` 在当前调试进程中读取服务环境，安全接管该服务端口，再执行 Uvicorn；因此业务源码和共享 kernel 断点都能命中。Agent 8105、Tools 8107。不启用 reload，修改后重新 Debug。

## 开发时注意

接管只停止开发脚本记录且身份校验匹配的进程，不随意杀占用端口的程序；PG、Redis 和其他服务继续运行。若提示端口被占用，先停止此前的 IDE 调试进程。

调试使用本机已有数据和实际模型配置。Automation 的断点停顿会影响租约和 heartbeat，请先暂停真实定时任务；故障测试使用 `make test-integration` 的隔离数据库和 Mock。

Web 继续通过 `pnpm --dir apps/web dev` 开发；iOS 原生部分仍用 Xcode。可运行 `make doctor`、`make status` 检查工具链和服务。Java 安装共享包可运行 `MAVEN_OPTS=-Djava.net.preferIPv4Stack=true mvn -B -DskipTests install`（JAVA_HOME 指向 JDK 21）。

## 本机验证（2026-10-11）

Java Maven 构建/install 通过；两个 Python IDE 入口实际启动后 readiness 均通过；两个 Java JVM 入口 readiness 和 JDWP 握手通过。检查后恢复四个常规服务，全部 readiness 为 UP。已安装 ARM 版 IntelliJ IDEA / PyCharm 2026.2.3。以上不等于已在 IDE 界面逐个命中断点；首次启动设置、工程索引和源码断点仍需在 IDE 中确认。
