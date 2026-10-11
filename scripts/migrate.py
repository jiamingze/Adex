import hashlib
import psycopg
from psycopg import sql
from config import load, ROOT

e = load()
conn = psycopg.connect(
    host=e["ADEX_PG_HOST"],
    port=e["ADEX_PG_PORT"],
    dbname=e["ADEX_PG_DB"],
    user="adex_admin",
    password=e["ADEX_ADMIN_PASSWORD"],
    autocommit=True,
)
with conn:
    conn.execute("CREATE SCHEMA IF NOT EXISTS migration_meta")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS migration_meta.applied (service text,version text,sha256 text,PRIMARY KEY(service,version))"
    )
    conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    for service in ("app", "automation", "agent", "tools"):
        role = "adex_" + service
        schema = service
        if not conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)
        ).fetchone():
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role),
                    sql.Literal(e[f"ADEX_{service.upper()}_DB_PASSWORD"]),
                )
            )
        conn.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {}").format(
                sql.Identifier(schema), sql.Identifier(role)
            )
        )
        conn.execute(
            sql.SQL("ALTER ROLE {} SET search_path TO {},pg_catalog").format(
                sql.Identifier(role), sql.Identifier(schema)
            )
        )
        for file in sorted((ROOT / "migrations" / service).glob("*.sql")):
            sha = hashlib.sha256(file.read_bytes()).hexdigest()
            with conn.transaction():
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    ("migration:" + service,),
                )
                old = conn.execute(
                    "SELECT sha256 FROM migration_meta.applied WHERE service=%s AND version=%s",
                    (service, file.name),
                ).fetchone()
                if old:
                    if old[0] != sha:
                        raise RuntimeError(
                            "Applied migration checksum changed: "
                            + service
                            + "/"
                            + file.name
                        )
                    continue
                conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
                conn.execute(
                    sql.SQL("SET LOCAL search_path TO {},pg_catalog").format(
                        sql.Identifier(schema)
                    )
                )
                conn.execute(file.read_text())
                conn.execute("RESET ROLE")
                conn.execute(
                    "INSERT INTO migration_meta.applied VALUES(%s,%s,%s)",
                    (service, file.name, sha),
                )
            print("Applied " + service + "/" + file.name)
