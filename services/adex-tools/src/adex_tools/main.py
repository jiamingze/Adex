"""Application composition; endpoint and business logic belong to capability modules."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from adex_tools.dependencies import core
from adex_tools.api import health, retrieval, creation, approvals, workspace, usage


@asynccontextmanager
async def lifespan(app):
    await core.start()
    try:
        yield
    finally:
        await core.pool.close()


async def error(request, exc):
    return JSONResponse({"code": exc.detail}, status_code=exc.status_code)


def create_app():
    app = FastAPI(title="Adex Tools", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_exception_handler(HTTPException, error)
    app.include_router(health.router)
    app.include_router(retrieval.router)
    app.include_router(creation.router)
    app.include_router(approvals.router)
    app.include_router(workspace.router)
    app.include_router(usage.router)
    return app


app = create_app()
