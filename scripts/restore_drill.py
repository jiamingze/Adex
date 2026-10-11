"""Restore backup to a new isolated DB, verify immutable checkpoint hashes and file manifest."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from config import load

e = load()
if e["ADEX_PG_HOST"] not in ("127.0.0.1", "localhost"):
    raise SystemExit("Local sandbox restore only")
folder = Path(sys.argv[1]).resolve()
manifest = json.loads((folder / "manifest.json").read_text())
for file, sha in manifest.items():
    p = folder / file
    if (
        not p.resolve().is_relative_to(folder)
        or hashlib.sha256(p.read_bytes()).hexdigest() != sha
    ):
        raise RuntimeError("Backup hash mismatch")
admin = psycopg.connect(
    host=e["ADEX_PG_HOST"],
    port=e["ADEX_PG_PORT"],
    dbname="postgres",
    user="adex_admin",
    password=e["ADEX_ADMIN_PASSWORD"],
    autocommit=True,
)
name = "adex_restore_" + uuid4().hex[:10]
admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
restore = "/opt/homebrew/opt/postgresql@16/bin/pg_restore"
if not Path(restore).exists():
    restore = "pg_restore"
env = dict(e)
env["PGPASSWORD"] = e["ADEX_ADMIN_PASSWORD"]
try:
    subprocess.run(
        [
            restore,
            "-h",
            e["ADEX_PG_HOST"],
            "-p",
            e["ADEX_PG_PORT"],
            "-U",
            "adex_admin",
            "-d",
            name,
            "--exit-on-error",
            str(folder / "database.dump"),
        ],
        env=env,
        check=True,
    )
    with psycopg.connect(
        host=e["ADEX_PG_HOST"],
        port=e["ADEX_PG_PORT"],
        dbname=name,
        user="adex_admin",
        password=e["ADEX_ADMIN_PASSWORD"],
    ) as conn:
        counts = {
            table: conn.execute(
                sql.SQL("SELECT count(*) FROM {}").format(
                    sql.Identifier(*table.split("."))
                )
            ).fetchone()[0]
            for table in [
                "app.messages",
                "app.memories",
                "automation.runs",
                "agent.checkpoints",
                "app.files",
                "app.artifacts",
            ]
        }
        for state, sha in conn.execute(
            "SELECT state,sha256 FROM agent.checkpoints"
        ).fetchall():
            actual = hashlib.sha256(
                json.dumps(
                    state, sort_keys=True, ensure_ascii=False, default=str
                ).encode()
            ).hexdigest()
            assert actual == sha, "Checkpoint hash mismatch"
        for object_id, sha, size in conn.execute(
            "SELECT object_id,sha256,size_bytes FROM app.files WHERE status='READY'"
        ).fetchall():
            object_id = str(object_id)
            path = folder / "files" / object_id[:2] / object_id
            assert path.is_file() and path.stat().st_size == size, (
                "Missing READY object"
            )
            assert hashlib.sha256(path.read_bytes()).hexdigest() == sha, (
                "Restored object hash mismatch"
            )
    print("Restore PASS:", counts, "backup objects verified", len(manifest))
finally:
    admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
    admin.close()
