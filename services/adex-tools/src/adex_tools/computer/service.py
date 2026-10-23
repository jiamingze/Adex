"""Owner-bound native commands on existing approval/effect and Automation fencing ports."""

import os
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from adex_kernel.core import digest
from .runner import MacRunner


class ComputerService:
    def __init__(self, core, runner=None):
        self.core, self.runner = core, runner or MacRunner()

    def grant(self, owner, app_name=None):
        if os.getenv("ADEX_COMPUTER_ENABLED") != "true" or str(owner) != os.getenv("ADEX_COMPUTER_OWNER_ID"):
            raise HTTPException(403, "COMPUTER_HOST_NOT_GRANTED")
        # Configuration is host-controlled, never supplied by model or remote clients.
        pairs = [p.split("=", 1) for p in os.getenv("ADEX_COMPUTER_APPS", "").split(",") if "=" in p]
        apps = dict(pairs)
        if app_name is None:
            return apps
        if os.getenv("ADEX_COMPUTER_APP_POLICY", "allowlist") == "all_installed":
            return apps.get(app_name, app_name)
        bundle = apps.get(app_name) or next((b for b in apps.values() if b == app_name), None)
        if bundle in {
            "com.apple.Terminal",
            "com.googlecode.iterm2",
            "com.apple.systempreferences",
            "com.apple.keychainaccess",
        }:
            raise HTTPException(403, "COMPUTER_PROTECTED_APP")
        if not bundle:
            raise HTTPException(403, "COMPUTER_APP_NOT_GRANTED")
        return bundle

    async def resolve(self, owner, app_name):
        target = self.grant(owner, app_name)
        result = await self.runner.call({"command": "resolve", "bundle_id": target})
        if not result.get("bundle_id"):
            raise HTTPException(409, "COMPUTER_APP_NOT_INSTALLED")
        return result["bundle_id"]

    async def status(self, owner, app_name=None):
        apps = self.grant(owner)
        if app_name is not None:
            await self.resolve(owner, app_name)
        result = await self.runner.call({"command": "status"})
        return {
            "availability": "READY"
            if result.get("accessibility")
            else "COMPUTER_ACCESSIBILITY_PERMISSION_REQUIRED",
            "apps": list(apps),
            "app_policy": os.getenv("ADEX_COMPUTER_APP_POLICY", "allowlist"),
        }

    async def authorize(self, owner, body):
        run = await self.core.call(
            "automation",
            "effect:execute",
            "POST",
            f"/internal/runs/{body['run_id']}/authorize-effect",
            {
                "epoch": body["epoch"],
                "attempt_id": str(body["attempt_id"]),
                "computer_run_id": str(body["run_id"]),
            },
            owner=owner,
            resource=body["run_id"],
        )
        if run.get("kind") != "COMPUTER":
            raise HTTPException(403, "COMPUTER_RUN_REQUIRED")
        conversation = run.get("origin_conversation_id")
        if not conversation:
            raise HTTPException(403, "COMPUTER_CONVERSATION_REQUIRED")
        await self.core.call(
            "app",
            "computer:access",
            "GET",
            f"/internal/conversations/{conversation}/computer-access",
            owner=owner,
            resource=conversation,
        )
        return run

    @asynccontextmanager
    async def command(self):
        host = os.getenv("ADEX_COMPUTER_HOST_ID", "local-mac")
        command = uuid4()
        await self.core.query(
            "INSERT INTO computer_host_mutex(host_id) VALUES(%s) ON CONFLICT DO NOTHING", (host,)
        )
        claim = await self.core.query(
            "UPDATE computer_host_mutex SET command_id=%s,lease_until=clock_timestamp()+interval '35 seconds' WHERE host_id=%s AND lease_until<clock_timestamp() RETURNING host_id",
            (command, host),
            one=True,
        )
        if not claim:
            raise HTTPException(409, "COMPUTER_HOST_BUSY")
        try:
            yield
        finally:
            await self.core.query(
                "UPDATE computer_host_mutex SET command_id=NULL,lease_until='-infinity' WHERE host_id=%s AND command_id=%s",
                (host, command),
            )

    async def observe(self, owner, body):
        bundle = await self.resolve(owner, body["app_name"])
        query = body.get("search_query")
        navigate = body.get("navigate_url")
        if navigate:
            from urllib.parse import urlsplit
            from adex_tools.runners.browser_policy import admitted_hosts, resolve_public_hosts
            import asyncio

            try:
                address = urlsplit(navigate)
                if address.scheme != "https" or query or bundle != "com.google.Chrome":
                    raise ValueError()
                admitted_hosts(navigate)
                resolved = await asyncio.wait_for(
                    asyncio.to_thread(resolve_public_hosts, (address.hostname,)), 4
                )
                if address.hostname not in resolved:
                    raise ValueError()
            except Exception:
                raise HTTPException(400, "COMPUTER_PUBLIC_HTTPS_REQUIRED") from None
        if query is not None and bundle != "com.google.Chrome":
            raise HTTPException(400, "COMPUTER_SEARCH_REQUIRES_CHROME")
        # Opportunistic retention cleanup uses the existing request path, not a new scheduler.
        await self.core.query(
            "DELETE FROM computer_observations WHERE owner_id=%s AND created_at<clock_timestamp()-interval '1 day'",
            (owner,),
        )
        await self.authorize(owner, body)
        async with self.command():
            snapshot = await self.runner.call(
                {"bundle_id": bundle, "search_query": query, "navigate_url": navigate}
            )
            await self.authorize(owner, body)
            identifier = uuid4()
            await self.core.query(
                "INSERT INTO computer_observations(id,owner_id,run_id,bundle_id,snapshot) VALUES(%s,%s,%s,%s,%s)",
                (identifier, owner, body["run_id"], bundle, Jsonb(snapshot)),
            )
            return {"observation_id": str(identifier), **snapshot}

    async def step(self, owner, body):
        bundle = await self.resolve(owner, body["app_name"])
        run = await self.authorize(owner, body)
        observed = await self.core.query(
            "SELECT * FROM computer_observations WHERE id=%s AND owner_id=%s AND run_id=%s AND created_at>clock_timestamp()-interval '10 minutes'",
            (body["observation_id"], owner, body["run_id"]),
            one=True,
        )
        if not observed or observed["bundle_id"] != bundle:
            raise HTTPException(409, "COMPUTER_OBSERVATION_REQUIRED")
        snapshot = observed["snapshot"]
        step = body["step"]
        node = next((n for n in snapshot["nodes"] if n["id"] == step["element_id"]), None)
        if (
            not node
            or node.get("secure")
            or (step["action"] == "press" and "AXPress" not in node.get("actions", []))
            or (step["action"] == "set_value" and not node.get("settable"))
        ):
            raise HTTPException(403, "COMPUTER_CONTROL_NOT_ALLOWED")
        request = {
            "computer_run_id": str(body["run_id"]),
            "origin_conversation_id": str(run["origin_conversation_id"]),
            "observation_id": str(body["observation_id"]),
            "command_key": body["command_key"],
            "payload": {"app": body["app_name"], "control": node.get("title") or node.get("role"), **step},
        }
        fingerprint = digest(request)
        if not body.get("approval_id"):
            existing = await self.core.query(
                "SELECT id,state FROM approvals WHERE owner_id=%s AND kind='computer.step' AND request_hash=%s ORDER BY created_at DESC LIMIT 1",
                (owner, fingerprint),
                one=True,
            )
            if existing:
                return {"status": "APPROVAL_REQUIRED", "action_id": str(existing["id"])}
            action = uuid4()
            await self.core.query(
                "INSERT INTO approvals(id,owner_id,kind,request,request_hash) VALUES(%s,%s,'computer.step',%s,%s)",
                (action, owner, Jsonb(request), fingerprint),
            )
            return {"status": "APPROVAL_REQUIRED", "action_id": str(action)}
        effect_key = f"computer:{body['run_id']}:{body['command_key']}"
        async with self.command():
            async with self.core.pool.connection() as conn:
                async with conn.transaction():
                    cursor = await conn.execute(
                        "SELECT *,expires_at>clock_timestamp() valid FROM approvals WHERE id=%s AND owner_id=%s AND kind='computer.step' FOR UPDATE",
                        (body["approval_id"], owner),
                    )
                    approval = await cursor.fetchone()
                    if not approval or approval["request_hash"] != fingerprint:
                        raise HTTPException(403, "COMPUTER_APPROVAL_MISMATCH")
                    cursor = await conn.execute(
                        "SELECT * FROM effects WHERE owner_id=%s AND effect_key=%s", (owner, effect_key)
                    )
                    old = await cursor.fetchone()
                    if old:
                        if old["request_hash"] != fingerprint:
                            raise HTTPException(409, "IDEMPOTENCY_CONFLICT")
                        if old["state"] == "SUCCEEDED":
                            return old["result"]
                        await conn.execute(
                            "UPDATE effects SET state='UNKNOWN' WHERE owner_id=%s AND effect_key=%s AND state='IN_FLIGHT'",
                            (owner, effect_key),
                        )
                        await conn.execute(
                            "UPDATE approvals SET state='UNKNOWN' WHERE id=%s AND state='APPROVED'",
                            (body["approval_id"],),
                        )
                        return {"status": "UNKNOWN", "action_id": str(body["approval_id"])}
                    if not approval["valid"] or approval["state"] != "APPROVED":
                        raise HTTPException(409, "APPROVAL_EXPIRED_OR_REVOKED")
                    await conn.execute(
                        "INSERT INTO effects(owner_id,effect_key,request_hash,tool_id,state) VALUES(%s,%s,%s,'computer.step','IN_FLIGHT')",
                        (owner, effect_key, fingerprint),
                    )
            try:
                await self.authorize(owner, body)
                receipt = await self.runner.call(
                    {"bundle_id": bundle, "pid": snapshot["pid"], "tree_hash": snapshot["tree_hash"], **step}
                )
                result = {
                    "status": "COMMAND_APPLIED",
                    "receipt": receipt,
                    "action_id": str(body["approval_id"]),
                }
                await self.core.query(
                    "UPDATE effects SET state='SUCCEEDED',result=%s WHERE owner_id=%s AND effect_key=%s AND state='IN_FLIGHT'",
                    (Jsonb(result), owner, effect_key),
                )
                await self.core.query(
                    "UPDATE approvals SET state='SUCCEEDED',result=%s WHERE id=%s AND owner_id=%s",
                    (Jsonb(result), body["approval_id"], owner),
                )
                return result
            except BaseException:
                # Crash after IN_FLIGHT is deliberately not replayable. APPLIED is only
                # native command evidence, never proof of an external purchase or publish.
                await self.core.query(
                    "UPDATE effects SET state='UNKNOWN' WHERE owner_id=%s AND effect_key=%s AND state='IN_FLIGHT'",
                    (owner, effect_key),
                )
                raise
