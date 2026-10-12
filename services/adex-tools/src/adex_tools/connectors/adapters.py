"""Connector provider ports; registration is explicit, never derived from user input."""

from typing import Protocol
from fastapi import HTTPException
from . import google


class ConnectorAdapter(Protocol):
    async def query(self, token: str, service: str, query: dict) -> dict: ...
    async def snapshot(self, token: str, resource_id: str) -> dict: ...
    async def submit(self, token: str, action_id, request: dict) -> dict: ...


class GoogleAdapter:
    async def query(self, token, service, query):
        return await (
            google.calendar_query(token, query) if service == "calendar" else google.gmail_query(token, query)
        )

    async def snapshot(self, token, resource_id):
        return await google.calendar_event(token, resource_id)

    async def submit(self, token, action_id, request):
        return await google.write(token, action_id, request)


_REGISTRY = {"google": GoogleAdapter}


def adapter(provider="google") -> ConnectorAdapter:
    factory = _REGISTRY.get(provider)
    if not factory:
        raise HTTPException(503, "CONNECTOR_PROVIDER_NOT_ENABLED")
    return factory()
