"""Small execution facade composing context, invocation and durable background capabilities."""

import os
from psycopg.types.json import Jsonb
from redis.asyncio import Redis
from adex_kernel.core import digest
from adex_agent.models.provider import ProviderFailure, provider


from .context import ContextService
from .invocation import InvocationService
from .checkpoints import CheckpointStore
from .background import BackgroundWorker


class Runtime:
    def __init__(self, core):
        self.core = core
        self.provider = provider()
        self.redis = Redis.from_url(
            os.environ["ADEX_REDIS_URL"], socket_connect_timeout=1, socket_timeout=1, decode_responses=True
        )

        self.checkpoints = CheckpointStore(core)
        self.background = BackgroundWorker(core, self, self.checkpoints)

    async def interactive_messages(self, key, owner, context, search=False):
        # Freeze paid tool evidence before model dispatch. Retries replay the same
        # prompt, but cannot cross a changed authoritative memory revision/context.
        context_hash = digest(
            {"context": {k: v for k, v in context.items() if k != "summary"}, "search": search}
        )
        row = await self.core.query(
            "SELECT * FROM interactive_plans WHERE invocation_key=%s", (key,), one=True
        )
        if not row:
            cards = []
            messages = await self.messages(context, search=search, cards=cards)
            await self.core.query(
                "INSERT INTO interactive_plans(invocation_key,owner_id,context_hash,messages,cards) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (key, owner, context_hash, Jsonb(messages), Jsonb(cards)),
            )
            row = await self.core.query(
                "SELECT * FROM interactive_plans WHERE invocation_key=%s", (key,), one=True
            )
        if str(row["owner_id"]) != str(owner) or row["context_hash"] != context_hash:
            raise ProviderFailure("IDEMPOTENCY_CONFLICT")
        return row["messages"]

    async def context(self, owner, conv, upto=None):
        return await ContextService(self.core, self.redis).context(owner, conv, upto)

    async def working(self, context):
        return await ContextService(self.core, self.redis).working(context)

    async def messages(self, context, search=False, research=False, cards=None):
        return await ContextService(self.core).messages(context, search, research, cards)

    async def invoke(self, key, owner, messages):
        invocation = InvocationService(self.core, self.provider, getattr(self, "provider_mode", None))
        async for event in invocation.invoke(key, owner, messages):
            yield event

    async def save_checkpoint(self, run, logical_key, state, memory_revision):
        return await self.checkpoints.save_checkpoint(run, logical_key, state, memory_revision)

    async def background_run(self, run):
        return await self.background.background_run(run)

    async def worker(self):
        await self.background.worker()

    async def audit_checkpoints(self):
        await self.checkpoints.audit_checkpoints()
