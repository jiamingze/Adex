import asyncio
import os
from uuid import uuid4
from adex_kernel.core import Core, digest
from adex_agent.execution.runtime import Runtime
from adex_agent.models.provider import ProviderFailure


async def main():
    core = Core("agent")
    await core.start()
    runtime = Runtime(core)

    class NeverCalled:
        model = "unknown-test"

        async def stream(self, messages):
            raise AssertionError("Unknown provider call must not be retried")
            yield

    runtime.provider = NeverCalled()
    os.environ["ADEX_MODEL_PROVIDER"] = "minimax"
    messages = [{"role": "user", "content": "unknown test"}]
    key = "unknown-fixture:" + str(uuid4())
    owner = os.environ["ADEX_UNKNOWN_FIXTURE_OWNER"]
    await core.query(
        "INSERT INTO invocations(invocation_key,owner_id,request_hash,state,provider,model) VALUES(%s,%s,%s,'UNKNOWN','minimax','unknown-test')",
        (key, owner, digest({"messages": messages, "model": "unknown-test"})),
    )
    try:
        async for _ in runtime.invoke(key, owner, messages):
            pass
        raise AssertionError("Expected UNKNOWN refusal")
    except ProviderFailure as exc:
        assert exc.code == "PROVIDER_UNKNOWN"
        print("UNKNOWN no resubmit PASS")
    finally:
        await runtime.redis.aclose()
        await core.pool.close()


asyncio.run(main())
