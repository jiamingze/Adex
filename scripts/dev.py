import argparse
import os
import signal
import subprocess
import shutil
from pathlib import Path
from config import load, ROOT


def service_env(name):
    e = load()
    e["ADEX_SERVICE"] = name
    e["ADEX_DB_USER"] = "adex_" + name
    e["ADEX_DB_PASSWORD"] = e[f"ADEX_{name.upper()}_DB_PASSWORD"]
    e["ADEX_DB_JDBC_URL"] = (
        f"jdbc:postgresql://{e['ADEX_PG_HOST']}:{e['ADEX_PG_PORT']}/{e['ADEX_PG_DB']}?currentSchema={name}"
    )
    e["ADEX_DB_URL"] = (
        f"postgresql://adex_{name}:{e['ADEX_DB_PASSWORD']}@{e['ADEX_PG_HOST']}:{e['ADEX_PG_PORT']}/{e['ADEX_PG_DB']}"
    )
    java = "/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"
    if Path(java).exists():
        e["JAVA_HOME"] = java
        e["PATH"] = java + "/bin:" + e["PATH"]
    for key in list(e):
        if name != "tools" and (
            key.startswith("ADEX_CODE_RUNNER_")
            or key == "ADEX_RUNNER_KEY"
            or key in ("DOCKER_HOST", "DOCKER_CONFIG")
        ):
            e.pop(key, None)
        if (
            key == "ADEX_ADMIN_PASSWORD"
            or key
            in {
                f"ADEX_{service}_DB_PASSWORD"
                for service in ("APP", "AUTOMATION", "AGENT", "TOOLS")
            }
            and key != f"ADEX_{name.upper()}_DB_PASSWORD"
        ):
            e.pop(key, None)
        if (name not in ("agent", "tools") and key == "DASHSCOPE_API_KEY"):
            e.pop(key, None)
        if (name != "agent" and key == "MINIMAX_API_KEY") or (
            name != "tools" and key == "TAVILY_API_KEY"
        ):
            e.pop(key, None)
        if name != "app" and key.startswith("ADEX_SMTP_"):
            e.pop(key, None)
        if name != "tools" and (
            key.startswith("ADEX_CALDAV_")
            or key.startswith("ADEX_VISION_")
            or key == "ADEX_MEDIA_WEBHOOK_SECRET"
            or (key.startswith("ADEX_MUSIC_") and key != "ADEX_MUSIC_PROVIDER")
        ):
            e.pop(key, None)
        if name != "tools" and key.startswith("ADEX_CALDAV_"):
            e.pop(key, None)
        if name != "app" and key == "ADEX_OWNER_PASSWORD":
            e.pop(key, None)
    for key in list(e):
        if name != "tools" and (key.startswith("ADEX_GOOGLE_") or key.startswith("ADEX_CONNECTOR_") or key == "ADEX_BROWSER_ENCRYPTION_KEY"):
            e.pop(key, None)
        if name != "app" and key.startswith("ADEX_APNS_"):
            e.pop(key, None)
    return e


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["start", "stop", "status"])
    args = p.parse_args()
    state = ROOT / ".local-data"
    state.mkdir(exist_ok=True)
    if args.action == "status":
        import httpx

        for name, port in [
            ("app", 8080),
            ("automation", 8081),
            ("agent", 8105),
            ("tools", 8107),
        ]:
            try:
                r = httpx.get(
                    f"http://127.0.0.1:{port}/health/ready", timeout=3, trust_env=False
                )
                print(name, r.status_code, r.json())
            except Exception:
                print(name, "DOWN")
        return
    for name in ["app", "automation", "agent", "tools", "web"]:
        pidfile = state / (name + ".pid")
        if args.action == "stop":
            if pidfile.exists():
                pid = int(pidfile.read_text())
                try:
                    os.killpg(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                pidfile.unlink()
            continue
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), 0)
                print(name, "already running")
                continue
            except ProcessLookupError:
                pidfile.unlink()
        e = (
            service_env(name)
            if name != "web"
            else {
                key: value
                for key, value in load().items()
                if key in ("PATH", "HOME", "USER", "TMPDIR", "LANG", "LC_ALL")
                or key.startswith("VITE_")
            }
        )
        if name in ("app", "automation"):
            runtime = state / "runtime"
            runtime.mkdir(exist_ok=True)
            jar = runtime / (name + ".jar")
            pending_jar = runtime / (name + ".jar.tmp")
            shutil.copyfile(
                ROOT / f"services/adex-{name}/target/adex-{name}-0.1.0.jar", pending_jar
            )
            pending_jar.replace(jar)
            cmd = [
                "java",
                "-Djava.net.preferIPv4Stack=true",
                "-Xmx512m",
                "-jar",
                str(jar),
            ]
        elif name in ("agent", "tools"):
            port = "8105" if name == "agent" else "8107"
            cmd = [
                "uv",
                "run",
                "--project",
                f"services/adex-{name}",
                "uvicorn",
                f"adex_{name}.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                port,
                "--no-access-log",
            ]
        else:
            cmd = ["pnpm", "--dir", "apps/web", "dev", "--host", "127.0.0.1"]
        with (state / (name + ".log")).open("a") as log:
            child = subprocess.Popen(
                cmd, cwd=ROOT, env=e, stdout=log, stderr=log, start_new_session=True
            )
        pidfile.write_text(str(child.pid))
        print("Started", name)


if __name__ == "__main__":
    main()
