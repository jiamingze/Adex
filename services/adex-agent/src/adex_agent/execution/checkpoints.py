"""Immutable checkpoints are written before Automation commits the authoritative reference."""

import asyncio
from uuid import uuid4
from psycopg.types.json import Jsonb
from adex_kernel.core import digest
from adex_agent.models.provider import ProviderFailure


class CheckpointStore:
    def __init__(self, core):
        self.core = core

    async def save_checkpoint(self, run, logical_key, state, memory_revision):
        ref = uuid4()
        sha = digest(state)
        await self.core.query(
            "INSERT INTO checkpoints(id,run_id,owner_id,epoch,attempt_id,logical_key,memory_revision,schema_version,state,sha256) VALUES(%s,%s,%s,%s,%s,%s,%s,1,%s,%s) ON CONFLICT(run_id,epoch,logical_key) DO NOTHING",
            (
                ref,
                run["id"],
                run["owner_id"],
                run["epoch"],
                run["attempt_id"],
                logical_key,
                memory_revision,
                Jsonb(state),
                sha,
            ),
        )
        cp = await self.core.query(
            "SELECT * FROM checkpoints WHERE run_id=%s AND epoch=%s AND logical_key=%s",
            (run["id"], run["epoch"], logical_key),
            one=True,
        )
        if cp["sha256"] != sha:
            raise ProviderFailure("CHECKPOINT_CONFLICT")
        return str(cp["id"])

    async def audit_checkpoints(self):
        """Ask the authoritative owner before classifying uncommitted immutable objects."""
        while True:
            try:
                pending = await self.core.query(
                    "SELECT c.* FROM checkpoints c LEFT JOIN checkpoint_audits a ON a.checkpoint_id=c.id WHERE c.created_at<now()-interval '1 hour' AND (a.checked_at IS NULL OR a.checked_at<now()-interval '1 day') ORDER BY c.created_at LIMIT 20"
                )
                for cp in pending:
                    refs = await self.core.call(
                        "automation",
                        "run:inspect",
                        "GET",
                        f"/internal/runs/{cp['run_id']}/checkpoint-refs",
                        owner=cp["owner_id"],
                        resource=cp["run_id"],
                    )
                    status = "REFERENCED" if str(cp["id"]) in refs["refs"] else "ORPHAN"
                    await self.core.query(
                        "INSERT INTO checkpoint_audits(checkpoint_id,status) VALUES(%s,%s) ON CONFLICT(checkpoint_id) DO UPDATE SET status=excluded.status,checked_at=now()",
                        (cp["id"], status),
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(60)
