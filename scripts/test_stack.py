"""Isolated real-PG stack: 3 schedulers, mock model, explicit SIGKILL recovery tests."""

import os
import signal
import shutil
import subprocess
import time
from uuid import uuid4
import httpx
import psycopg
from psycopg import sql
from config import load, ROOT
from dev import service_env

e = load()
if e["ADEX_PG_HOST"] not in ("127.0.0.1", "localhost") or e["ADEX_PG_DB"] != "adex_dev":
    raise SystemExit(
        "Test runner only targets the isolated local development PostgreSQL instance."
    )
name = "adex_test_" + uuid4().hex[:10]
admin = psycopg.connect(
    host=e["ADEX_PG_HOST"],
    port=e["ADEX_PG_PORT"],
    dbname="postgres",
    user="adex_admin",
    password=e["ADEX_ADMIN_PASSWORD"],
    autocommit=True,
)
admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
e["ADEX_PG_DB"] = name
e["ADEX_FILE_STORAGE_ROOT"] = str(ROOT / ".local-data" / name / "files")
e["ADEX_MODEL_PROVIDER"] = "mock"
e["ADEX_DAILY_MODEL_CALL_LIMIT"] = "0"
# This isolated stack uses loopback HTTP; do not inherit public HTTPS cookie settings.
e["ADEX_COOKIE_SECURE"] = "false"
e["ADEX_CODE_RUNNER_MODE"] = "disabled"
e["TAVILY_API_KEY"] = ""
e["ADEX_MUSIC_API_KEY"] = ""
e["DASHSCOPE_API_KEY"] = ""
e["ADEX_MUSIC_PROVIDER"] = "mock"
e["ADEX_VIDEO_PROVIDER"] = "mock"
e["ADEX_IMAGE_PROVIDER"] = "mock"
e["ADEX_CALDAV_URL"] = ""
e["ADEX_SMTP_HOST"] = ""
e["ADEX_BACKGROUND_WORKER"] = "false"
e["ADEX_TEST_URL"] = "http://127.0.0.1:18080"
e["ADEX_REDIS_URL"] = "redis://127.0.0.1:56380/0"
e["ADEX_ES_URL"] = "http://127.0.0.1:59499"
e["ADEX_VISION_PROVIDER"] = "disabled"
e["ADEX_VISION_API_KEY"] = ""
e["ADEX_MEDIA_WEBHOOK_SECRET"] = "adex-integration-webhook-fixture"
# External fixtures only run against a random adex_test_* database.
import base64
from secrets import token_bytes

e["ADEX_CONNECTOR_TEST_FIXTURE"] = "true"
e["ADEX_APNS_TEST_FIXTURE"] = "true"
e["ADEX_CONNECTOR_ENCRYPTION_KEY"] = base64.b64encode(token_bytes(32)).decode()
e["ADEX_APNS_DEVICE_ENCRYPTION_KEY"] = base64.b64encode(token_bytes(32)).decode()
e["ADEX_GOOGLE_CLIENT_ID"] = "test-client"
e["ADEX_GOOGLE_CLIENT_SECRET"] = "test-secret"
e["ADEX_GOOGLE_REDIRECT_URI"] = (
    "http://127.0.0.1:18080/api/v1/connectors/google/callback"
)
for service, port in [
    ("APP", 18080),
    ("AUTOMATION", 18081),
    ("AGENT", 18105),
    ("TOOLS", 18107),
]:
    e["ADEX_" + service + "_URL"] = f"http://127.0.0.1:{port}"
os.environ.update(e)
children = []
logs = []
try:
    subprocess.run(
        ["uv", "run", "python", "scripts/migrate.py"], cwd=ROOT, env=e, check=True
    )
    redislog = (ROOT / ".local-data/test-redis.log").open("w")
    logs.append(redislog)
    redisproc = subprocess.Popen(
        [
            "redis-server",
            "--bind",
            "127.0.0.1",
            "--port",
            "56380",
            "--save",
            "",
            "--appendonly",
            "no",
        ],
        cwd=ROOT,
        stdout=redislog,
        stderr=redislog,
        start_new_session=True,
    )
    children.append(redisproc)
    e["ADEX_TEST_REDIS_PID"] = str(redisproc.pid)
    os.environ.update(e)
    fixture_log = (ROOT / ".local-data/test-connector-fixture.log").open("w")
    logs.append(fixture_log)
    children.append(
        subprocess.Popen(
            ["uv", "run", "python", "tests/fixtures/connector_server.py"],
            cwd=ROOT,
            env=e,
            stdout=fixture_log,
            stderr=fixture_log,
            start_new_session=True,
        )
    )
    # Running JVMs must not read target JARs which a subsequent build can replace.
    # Match the dev runtime's immutable-per-launch artifact isolation.
    runtime_jars = ROOT / ".local-data" / name / "runtime"
    runtime_jars.mkdir(parents=True, exist_ok=True)
    for service in ("app", "automation"):
        shutil.copyfile(
            ROOT / f"services/adex-{service}/target/adex-{service}-0.1.0.jar",
            runtime_jars / f"{service}.jar",
        )
    for service, port in [
        ("app", 18080),
        ("automation", 18081),
        ("automation", 18082),
        ("automation", 18083),
        ("agent", 18105),
        ("tools", 18107),
    ]:
        se = service_env(service)
        se["PORT"] = str(port)
        log = (ROOT / ".local-data" / f"test-{service}-{port}.log").open("w")
        logs.append(log)
        if service in ("app", "automation"):
            cmd = [
                "java",
                "-Djava.net.preferIPv4Stack=true",
                "-Xmx256m",
                "-jar",
                str(runtime_jars / f"{service}.jar"),
            ]
        else:
            cmd = [
                "uv",
                "run",
                "--project",
                f"services/adex-{service}",
                "uvicorn",
                f"adex_{service}.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ]
        children.append(
            subprocess.Popen(
                cmd, cwd=ROOT, env=se, stdout=log, stderr=log, start_new_session=True
            )
        )
    for port in (18080, 18081, 18082, 18083, 18105, 18107):
        for _ in range(60):
            try:
                if (
                    httpx.get(
                        f"http://127.0.0.1:{port}/health/ready",
                        timeout=1,
                        trust_env=False,
                    ).status_code
                    == 200
                ):
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("Test service not ready: " + str(port))
    print(
        "Isolated stack ready: PostgreSQL + 3 schedulers + mock Agent + Redis",
        flush=True,
    )
    result = subprocess.run(
        ["uv", "run", "pytest", "tests/integration", "-q"], cwd=ROOT, env=e
    )
finally:
    for child in children:
        if child.poll() is not None:
            continue
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            if child.poll() is None:
                child.terminate()
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
    for log in logs:
        log.close()
    admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
    admin.close()
raise SystemExit(result.returncode)
