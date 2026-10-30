"""Durable model invocation ledger: timeout means UNKNOWN, never blind replay."""

import asyncio
import os
from uuid import uuid4
from psycopg.types.json import Jsonb
from adex_kernel.core import digest
from adex_agent.models.provider import ProviderFailure


class InvocationService:
    def __init__(self, core, model_provider, provider_mode=None):
        self.core = core
        self.provider = model_provider
        if provider_mode is not None:
            self.provider_mode = provider_mode

    async def invoke(self, key, owner, messages):
        identity = {"messages": messages, "model": self.provider.model}
        if engine := getattr(self.provider, "engine", None):
            identity["engine"] = engine
        request_hash = digest(identity)
        name = getattr(self, "provider_mode", os.getenv("ADEX_MODEL_PROVIDER", "minimax"))
        await self.core.query(
            "INSERT INTO invocations(invocation_key,owner_id,request_hash,state,provider,model) VALUES(%s,%s,%s,'PREPARED',%s,%s) ON CONFLICT DO NOTHING",
            (key, owner, request_hash, name, self.provider.model),
        )
        row = await self.core.query("SELECT * FROM invocations WHERE invocation_key=%s", (key,), one=True)
        if str(row["owner_id"]) != str(owner) or row["request_hash"] != request_hash:
            raise ProviderFailure("IDEMPOTENCY_CONFLICT")
        if row["state"] == "COMPLETED":
            yield row["result"]
            return
        if row["state"] == "DISPATCHED":
            # Only expired calls can become UNKNOWN; another replica may still be live.
            await self.core.query(
                "UPDATE invocations SET state='UNKNOWN',updated_at=now() WHERE invocation_key=%s AND state='DISPATCHED' AND lease_until<clock_timestamp()",
                (key,),
            )
            row = await self.core.query("SELECT * FROM invocations WHERE invocation_key=%s", (key,), one=True)
        if row["state"] == "UNKNOWN" and name == "mock":
            await self.core.query(
                "UPDATE invocations SET state='PREPARED' WHERE invocation_key=%s AND state='UNKNOWN'", (key,)
            )
        attempt = uuid4()
        async with self.core.pool.connection() as conn:
            async with conn.transaction():
                current = await (
                    await conn.execute(
                        "SELECT state FROM invocations WHERE invocation_key=%s FOR UPDATE", (key,)
                    )
                ).fetchone()
                acquired = current and current["state"] == "PREPARED"
                if acquired:
                    budget = await (
                        await conn.execute(
                            "INSERT INTO daily_budgets(owner_id,day,reserved_calls) VALUES(%s,(clock_timestamp() AT TIME ZONE 'UTC')::date,1) ON CONFLICT(owner_id,day) DO UPDATE SET reserved_calls=daily_budgets.reserved_calls+1 WHERE (%s=0 OR daily_budgets.reserved_calls<%s) RETURNING reserved_calls",
                            (
                                owner,
                                int(os.getenv("ADEX_DAILY_MODEL_CALL_LIMIT", "50")),
                                int(os.getenv("ADEX_DAILY_MODEL_CALL_LIMIT", "50")),
                            ),
                        )
                    ).fetchone()
                    if not budget:
                        raise ProviderFailure("DAILY_MODEL_BUDGET_EXCEEDED")
                    await conn.execute(
                        "UPDATE invocations SET state='DISPATCHED',attempt_id=%s,lease_until=clock_timestamp()+interval '180 seconds',updated_at=now() WHERE invocation_key=%s",
                        (attempt, key),
                    )
        if not acquired:
            raise ProviderFailure(
                "PROVIDER_UNKNOWN" if row["state"] in ("UNKNOWN", "FAILED") else "INVOCATION_BUSY"
            )
        try:
            async for event in self.provider.stream(messages):
                if event["type"] == "completed":
                    n = await self.core.query(
                        "UPDATE invocations SET state='COMPLETED',result=%s,usage=%s,updated_at=now() WHERE invocation_key=%s AND attempt_id=%s AND state='DISPATCHED' AND lease_until>clock_timestamp()",
                        (Jsonb(event), Jsonb(event["usage"]), key, attempt),
                    )
                    if n != 1:
                        raise ProviderFailure("STALE_EXECUTION")
                yield event
        except BaseException as e:
            code = e.code if isinstance(e, ProviderFailure) else "PROVIDER_UNKNOWN"
            state = (
                "UNKNOWN" if code == "PROVIDER_UNKNOWN" or isinstance(e, asyncio.CancelledError) else "FAILED"
            )
            await asyncio.shield(
                self.core.query(
                    "UPDATE invocations SET state=%s,updated_at=now() WHERE invocation_key=%s AND attempt_id=%s AND state='DISPATCHED'",
                    (state, key, attempt),
                )
            )
            if isinstance(e, asyncio.CancelledError):
                raise
            raise ProviderFailure(code) from None
