"""Read-only local operational summary; never print prompts, tokens or user content."""

import psycopg
from config import load

e = load()
with psycopg.connect(
    host=e["ADEX_PG_HOST"],
    port=e["ADEX_PG_PORT"],
    dbname=e["ADEX_PG_DB"],
    user="adex_admin",
    password=e["ADEX_ADMIN_PASSWORD"],
) as c:
    for table in [
        "app.turns",
        "automation.runs",
        "agent.invocations",
        "agent.checkpoint_audits",
    ]:
        col = "state" if table == "agent.invocations" else "status"
        rows = c.execute(
            f"SELECT {col},count(*) FROM {table} GROUP BY {col}"
        ).fetchall()
        print(table, rows)
    for table in ["app.outbox", "automation.outbox"]:
        print(
            table,
            "pending",
            c.execute(
                f"SELECT count(*) FROM {table} WHERE delivered_at IS NULL"
            ).fetchone()[0],
        )
    print(
        "uncommitted checkpoints",
        c.execute(
            "SELECT count(*) FROM agent.checkpoints c WHERE NOT EXISTS(SELECT 1 FROM automation.steps s WHERE s.checkpoint_ref=c.id)"
        ).fetchone()[0],
    )
