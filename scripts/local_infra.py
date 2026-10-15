from pathlib import Path
import subprocess
import shlex
from config import load, ROOT


def postgres_options(base, port):
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError("Invalid PostgreSQL port")
    # Ubuntu's compiled default /var/run/postgresql is not writable by a
    # normal developer. Keep both the cluster and socket in our private runtime.
    socket = base / "postgres-socket"
    socket.mkdir(mode=0o700, exist_ok=True)
    socket.chmod(0o700)
    return shlex.join(["-h", "127.0.0.1", "-p", str(port), "-k", str(socket)])


def main():
    e = load()
    base = ROOT / ".local-data"
    base.mkdir(exist_ok=True)
    pg = "/opt/homebrew/opt/postgresql@16/bin/"

    if not Path(pg + "initdb").exists():
        pg = (
            "/usr/lib/postgresql/16/bin/"
            if Path("/usr/lib/postgresql/16/bin/initdb").exists()
            else ""
        )

    def run(args, **kw):
        return subprocess.run(args, env=e, check=True, **kw)

    data = base / "postgres"
    pw = base / "init-password"
    if not (data / "PG_VERSION").exists():
        pw.write_text(e["ADEX_ADMIN_PASSWORD"])
        pw.chmod(0o600)
        try:
            run(
                [
                    pg + "initdb",
                    "-D",
                    str(data),
                    "-U",
                    "adex_admin",
                    "--auth=scram-sha-256",
                    "--pwfile=" + str(pw),
                    "--encoding=UTF8",
                    "--locale=C",
                ]
            )
        finally:
            pw.unlink(missing_ok=True)
    status = subprocess.run(
        [pg + "pg_ctl", "-D", str(data), "status"],
        env=e,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if status.returncode:
        run(
            [
                pg + "pg_ctl",
                "-D",
                str(data),
                "-l",
                str(base / "postgres.log"),
                "-o",
                postgres_options(base, e["ADEX_PG_PORT"]),
                "start",
            ]
        )
    e["PGPASSWORD"] = e["ADEX_ADMIN_PASSWORD"]
    args = [
        pg + "psql",
        "-h",
        e["ADEX_PG_HOST"],
        "-p",
        e["ADEX_PG_PORT"],
        "-U",
        "adex_admin",
        "-d",
        "postgres",
        "-tAc",
        "SELECT 1 FROM pg_database WHERE datname='adex_dev'",
    ]
    if not run(args, capture_output=True, text=True).stdout.strip():
        run(
            [
                pg + "createdb",
                "-h",
                e["ADEX_PG_HOST"],
                "-p",
                e["ADEX_PG_PORT"],
                "-U",
                "adex_admin",
                e["ADEX_PG_DB"],
            ]
        )
    redis = base / "redis"
    redis.mkdir(exist_ok=True)
    run(
        [
            "redis-server",
            "--bind",
            "127.0.0.1",
            "--port",
            "56379",
            "--daemonize",
            "yes",
            "--dir",
            str(redis),
            "--pidfile",
            str(redis / "redis.pid"),
            "--logfile",
            str(redis / "redis.log"),
            "--maxmemory",
            "128mb",
            "--maxmemory-policy",
            "allkeys-lru",
        ]
    )
    (base / "files").mkdir(exist_ok=True)
    print(
        "Local PostgreSQL :55432 / Redis :56379 ready. Data isolated under .local-data."
    )


if __name__ == "__main__":
    main()
