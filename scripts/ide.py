"""Prepare private IDE environments and hand one managed service to the debugger."""

import argparse
import xml.etree.ElementTree as ET
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

from config import ROOT
from dev import service_env


def prepare():
    directory = ROOT / ".local-data" / "ide"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    for name in ("app", "automation", "agent", "tools"):
        values = {
            k: v
            for k, v in service_env(name).items()
            if k.startswith("ADEX_")
            or k in ("DASHSCOPE_API_KEY", "MINIMAX_API_KEY", "TAVILY_API_KEY")
        }
        path = directory / f"{name}.env"
        path.touch(mode=0o600, exist_ok=True)
        os.chmod(path, 0o600)
        path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    for name in ("app", "automation", "agent", "tools"):
        java_service = name in ("app", "automation")
        project = ROOT if java_service else ROOT / "services" / f"adex-{name}"
        config_dir = project / ".idea" / "runConfigurations"
        config_dir.mkdir(parents=True, exist_ok=True)
        component = ET.Element("component", name="ProjectRunConfigurationManager")
        config = ET.SubElement(
            component,
            "configuration",
            default="false",
            name=f"Adex {name}",
            type="Application" if java_service else "PythonConfigurationType",
            factoryName="Application" if java_service else "Python",
        )

        def option(key, value):
            ET.SubElement(config, "option", name=key, value=value)

        if java_service:
            option(
                "MAIN_CLASS_NAME",
                f"io.adex.{name}.{'AppMain' if name == 'app' else 'AutomationMain'}",
            )
            ET.SubElement(config, "module", name=f"adex-{name}")
            option("VM_PARAMETERS", "-Djava.net.preferIPv4Stack=true -Xmx512m")
            java = service_env(name).get("JAVA_HOME", "")
            if java:
                option("ALTERNATIVE_JRE_PATH_ENABLED", "true")
                option("ALTERNATIVE_JRE_PATH", java)
            envs = ET.SubElement(config, "envs")
            for key, value in service_env(name).items():
                if key.startswith("ADEX_"):
                    ET.SubElement(envs, "env", name=key, value=value)
            method = ET.SubElement(config, "method", v="2")
            ET.SubElement(method, "option", name="Make", enabled="true")
        else:
            option("SDK_HOME", str(project / ".venv" / "bin" / "python"))
            option("IS_MODULE_SDK", "false")
            option("SCRIPT_NAME", str(ROOT / "scripts" / "ide_python.py"))
            option("PARAMETERS", name)
            option("ADD_CONTENT_ROOTS", "true")
            option("ADD_SOURCE_ROOTS", "true")
            ET.SubElement(config, "method", v="2")
        option("WORKING_DIRECTORY", str(ROOT))
        path = config_dir / f"Adex_{name}.xml"
        path.touch(mode=0o600, exist_ok=True)
        os.chmod(path, 0o600)
        ET.ElementTree(component).write(path, encoding="unicode")
    print(
        "IDE environment prepared; private credentials remain under ignored .local-data/ide."
    )


def handoff(name):
    port = {"app": 8080, "automation": 8081, "agent": 8105, "tools": 8107}[name]
    pidfile = ROOT / ".local-data" / f"{name}.pid"
    if pidfile.exists():
        pid = int(pidfile.read_text())
        try:
            command = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True
            ).stdout
            expected = (
                str(ROOT / ".local-data" / "runtime" / f"{name}.jar")
                if name in ("app", "automation")
                else f"adex_{name}.main:app"
            )
            if expected not in command or os.getpgid(pid) != pid:
                raise SystemExit(
                    f"{name}: stale or unrecognized PID file; refusing to stop process"
                )
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        pidfile.unlink()
    for _ in range(50):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                print(f"{name}: port {port} ready for debugger")
                return
        time.sleep(0.1)
    raise SystemExit(
        f"Port {port} is still occupied. Stop its owner before debugging; no unmanaged process was killed."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "handoff", "java-debug"])
    parser.add_argument(
        "service", nargs="?", choices=["app", "automation", "agent", "tools"]
    )
    args = parser.parse_args()
    prepare()
    if args.action in ("handoff", "java-debug"):
        if not args.service:
            parser.error("handoff requires a service")
        if args.action == "java-debug" and args.service not in ("app", "automation"):
            parser.error("java-debug supports app or automation")
        handoff(args.service)
        if args.action == "java-debug":
            debug_port = 5005 if args.service == "app" else 5006
            environment = service_env(args.service)
            java = (
                str(Path(environment["JAVA_HOME"]) / "bin" / "java")
                if environment.get("JAVA_HOME")
                else "java"
            )
            jar = (
                ROOT
                / "services"
                / f"adex-{args.service}"
                / "target"
                / f"adex-{args.service}-0.1.0.jar"
            )
            if not jar.exists():
                raise SystemExit("Build first: make build")
            command = [
                java,
                f"-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=127.0.0.1:{debug_port}",
                "-Djava.net.preferIPv4Stack=true",
                "-Xmx512m",
                "-jar",
                str(jar),
            ]
            os.execvpe(java, command, environment)


if __name__ == "__main__":
    main()
