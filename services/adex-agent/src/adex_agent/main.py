"""Application composition; endpoint and business logic belong to capability modules."""

from contextlib import asynccontextmanager
import asyncio
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from adex_agent.dependencies import core, runtime
from adex_agent.api import health, chat, checkpoints, schedules, usage


@asynccontextmanager
async def lifespan(app):
    await core.start()
    task = (
        asyncio.create_task(runtime.worker())
        if os.getenv("ADEX_BACKGROUND_WORKER", "true") == "true"
        else None
    )
    audit = asyncio.create_task(runtime.audit_checkpoints())
    try:
        yield
    finally:
        audit.cancel()
        await asyncio.gather(audit, return_exceptions=True)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await runtime.redis.aclose()
        await core.pool.close()


async def error(request, exc):
    return JSONResponse({"code": exc.detail}, status_code=exc.status_code)


def create_app():
    app = FastAPI(title="Adex Agent", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_exception_handler(HTTPException, error)
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(checkpoints.router)
    app.include_router(schedules.router)
    app.include_router(usage.router)
    return app


app = create_app()
