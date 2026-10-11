# IntelliJ IDEA / PyCharm debugging

[中文](../zh-CN/jetbrains.md)

Run `make setup`, `make build`, `make up-dev`, then `uv run python scripts/ide.py prepare`. The generated `.idea` configurations and `.local-data/ide` environments are private, ignored by Git and written with file permissions 600. Refresh preparation after changing `.env`; Python reloads its scoped environment on each launch.

In IntelliJ IDEA, import the root `pom.xml` as a Maven project and select Java 21 for Project SDK and Maven Runner. App, Automation and java-kernel remain in one reactor. The generated `Adex app` and `Adex automation` configurations use ordinary Application debugging, available without Spring-specific paid features. Before starting one, run `uv run python scripts/ide.py handoff app` (or `automation`) to release its managed port. Then select the corresponding configuration and Debug. Ports are 8080 and 8081.

Alternatively run `uv run python scripts/ide.py java-debug app` (or `automation`) and use the shared `Attach app (localhost:5005)` or `Attach automation (localhost:5006)` configuration. These local-only JDWP endpoints debug packaged code: rebuild and restart after source changes.

In PyCharm, open `services/adex-agent` and `services/adex-tools` in separate windows. Select each service's existing `.venv/bin/python`. Generated `Adex agent` and `Adex tools` configurations have explicit interpreter paths and invoke `scripts/ide_python.py`. This entry point loads service-scoped settings, hands off only that managed service, and runs Uvicorn inside the debugger so business and shared kernel breakpoints work. Ports are 8105 and 8107; reload is disabled to keep debugger behavior predictable.

After stopping a debugger, use `make up-dev` to restore ordinary service operation. Do not run the ordinary stack and an IDE instance of the same service at once. Handoff validates recorded process identity and refuses to kill an unmanaged port owner. Databases and unrelated services continue running.

Debugging uses local data and configured real providers. Pause live schedules before blocking Automation heartbeat/leases. Use `make test-integration` for isolated database/mock recovery checks. Web remains a Vite project; native iOS work requires Xcode. Check tools and health with `make doctor` and `make status`.
