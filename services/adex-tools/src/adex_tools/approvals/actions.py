"""Common action approvals on the existing durable approval/effect ledger.

Consent is immutable and owner scoped. Network dispatch occurs only after IN_FLIGHT
is durable, never while holding a row lock. Interrupted writes remain UNKNOWN.
"""

from uuid import uuid4
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from adex_kernel.core import digest
from adex_tools.connectors.service import ConnectorService
from adex_tools.connectors import google


class ActionService:
    def __init__(self, core):
        self.core = core
        self.connectors = ConnectorService(core)

    async def list(self, owner):
        return {
            "items": await self.core.query(
                "SELECT id,kind,connection_id,request,request_hash,state,expires_at,result,run_id FROM approvals WHERE owner_id=%s AND kind<>'calendar.create' ORDER BY created_at DESC LIMIT 100",
                (owner,),
            )
        }

    async def create(self, owner, body):
        request = body.model_dump(mode="json")
        connection = body.connection_id
        row, token = await self.connectors.credential(
            owner, connection, "write" if body.kind == "calendar.update" else "send"
        )
        if row["service"] != ("calendar" if body.kind == "calendar.update" else "gmail"):
            raise HTTPException(400, "CONNECTOR_ACTION_MISMATCH")
        if body.kind == "calendar.update":
            google.interval(request["payload"])
            before = await self.connectors.adapter.snapshot(token, request["payload"]["event_id"])
            if not before.get("etag") or not before.get("id"):
                raise HTTPException(503, "CALENDAR_RECEIPT_REQUIRED")
            request["before"] = {key: before.get(key) for key in ("id", "etag", "start", "end", "summary")}
        request["connection_revision"] = row["revision"]
        await self.connectors.check_revision(row)
        return await self.core.query(
            "INSERT INTO approvals(id,owner_id,kind,connection_id,request,request_hash) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id,kind,connection_id,request,request_hash,state,expires_at",
            (uuid4(), owner, body.kind, connection, Jsonb(request), digest(request)),
            one=True,
        )

    async def own(self, owner, action):
        row = await self.core.query(
            "SELECT *,expires_at>clock_timestamp() AS valid FROM approvals WHERE id=%s AND owner_id=%s AND kind<>'calendar.create'",
            (action, owner),
            one=True,
        )
        if not row:
            raise HTTPException(404, "ACTION_NOT_FOUND")
        return row

    async def decide(self, owner, action, decision, request_hash):
        async with self.core.pool.connection() as conn:
            async with conn.transaction():
                cursor = await conn.execute(
                    "SELECT *,expires_at>clock_timestamp() AS valid FROM approvals WHERE id=%s AND owner_id=%s AND kind<>'calendar.create' FOR UPDATE",
                    (action, owner),
                )
                row = await cursor.fetchone()
                if not row:
                    raise HTTPException(404, "ACTION_NOT_FOUND")
                if decision == "revoke":
                    if row["state"] not in ("PENDING", "APPROVED", "REVOKED"):
                        raise HTTPException(409, "ACTION_ALREADY_DISPATCHED")
                    await conn.execute("UPDATE approvals SET state='REVOKED' WHERE id=%s", (action,))
                    return {"state": "REVOKED"}
                if request_hash != row["request_hash"]:
                    raise HTTPException(409, "APPROVAL_SNAPSHOT_CHANGED")
                if row["state"] == "SUCCEEDED":
                    return {"state": "SUCCEEDED", "result": row["result"]}
                if not row["valid"] or row["state"] not in ("PENDING", "APPROVED"):
                    raise HTTPException(409, "APPROVAL_EXPIRED_OR_REVOKED")
                await conn.execute("UPDATE approvals SET state='APPROVED' WHERE id=%s", (action,))
                return {"state": "APPROVED", "request": row["request"]}

    async def execute(self, owner, action, execution):
        # Authorization is checked before preparing a side effect, including on
        # recovery. Automation alone decides whether this attempt is still live.
        await self.core.call(
            "automation",
            "effect:execute",
            "POST",
            f"/internal/runs/{execution.run_id}/authorize-effect",
            execution.model_dump(mode="json"),
            owner=owner,
            resource=execution.run_id,
        )
        row = await self.own(owner, action)
        if row["state"] == "SUCCEEDED":
            return row["result"]
        if row["state"] == "UNKNOWN":
            raise HTTPException(409, "PROVIDER_UNKNOWN")
        if not row["valid"] or row["state"] != "APPROVED":
            raise HTTPException(409, "APPROVAL_EXPIRED_OR_REVOKED")
        connection, token = await self.connectors.credential(
            owner, row["connection_id"], "write" if row["kind"] == "calendar.update" else "send"
        )
        key = "action:" + str(action)
        async with self.core.pool.connection() as conn:
            async with conn.transaction():
                current = await (
                    await conn.execute(
                        "SELECT *,expires_at>clock_timestamp() AS valid FROM approvals WHERE id=%s AND owner_id=%s FOR UPDATE",
                        (action, owner),
                    )
                ).fetchone()
                linked = await (
                    await conn.execute(
                        "SELECT status,revision FROM connector_connections WHERE id=%s AND owner_id=%s FOR SHARE",
                        (row["connection_id"], owner),
                    )
                ).fetchone()
                if not linked or linked["status"] != "ACTIVE" or linked["revision"] != connection["revision"]:
                    raise HTTPException(409, "CONNECTOR_CHANGED")
                if not current["valid"] or current["state"] != "APPROVED":
                    raise HTTPException(409, "ACTION_ALREADY_DISPATCHED")
                if current["run_id"] and str(current["run_id"]) != str(execution.run_id):
                    raise HTTPException(409, "ACTION_RUN_MISMATCH")
                await conn.execute(
                    "INSERT INTO effects(owner_id,effect_key,request_hash,tool_id,state) VALUES(%s,%s,%s,%s,'IN_FLIGHT')",
                    (owner, key, row["request_hash"], row["kind"]),
                )
                await conn.execute(
                    "UPDATE approvals SET state='UNKNOWN',run_id=%s WHERE id=%s", (execution.run_id, action)
                )
        try:
            receipt = await self.connectors.adapter.submit(token, action, row["request"])
            result = {"state": "SUCCEEDED", "action_id": str(action), "kind": row["kind"], **receipt}
            await self._receipt(owner, action, result)
            return result
        except HTTPException as exc:
            if exc.detail in (
                "RESOURCE_CHANGED_REAPPROVAL_REQUIRED",
                "CONNECTOR_SCOPE_REQUIRED",
                "CONNECTOR_REAUTH_REQUIRED",
            ):
                async with self.core.pool.connection() as conn:
                    async with conn.transaction():
                        await conn.execute(
                            "UPDATE effects SET state='FAILED',result=%s WHERE owner_id=%s AND effect_key=%s",
                            (Jsonb({"code": exc.detail}), owner, key),
                        )
                        await conn.execute(
                            "UPDATE approvals SET state='REVOKED' WHERE id=%s AND owner_id=%s",
                            (action, owner),
                        )
                raise
            await self.core.query(
                "UPDATE effects SET state='UNKNOWN' WHERE owner_id=%s AND effect_key=%s", (owner, key)
            )
            raise HTTPException(409, "PROVIDER_UNKNOWN") from None
        except BaseException:
            # IN_FLIGHT is already uncertain and recovery cannot resubmit. Even if
            # cleanup itself is interrupted, the approval remains UNKNOWN.
            await self.core.query(
                "UPDATE effects SET state='UNKNOWN' WHERE owner_id=%s AND effect_key=%s", (owner, key)
            )
            raise

    async def _receipt(self, owner, action, result):
        if not result.get("provider_receipt") or not result.get("verified"):
            raise HTTPException(409, "PROVIDER_RECEIPT_REQUIRED")
        async with self.core.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE approvals SET state='SUCCEEDED',result=%s WHERE id=%s AND owner_id=%s AND state='UNKNOWN'",
                    (Jsonb(result), action, owner),
                )
                await conn.execute(
                    "UPDATE effects SET state='SUCCEEDED',result=%s WHERE owner_id=%s AND effect_key=%s AND state IN ('IN_FLIGHT','UNKNOWN')",
                    (Jsonb(result), owner, "action:" + str(action)),
                )

    async def reconcile(self, owner, action):
        row = await self.own(owner, action)
        if row["state"] == "SUCCEEDED":
            return row["result"]
        if row["state"] != "UNKNOWN":
            raise HTTPException(409, "RECONCILIATION_NOT_REQUIRED")
        _, token = await self.connectors.credential(owner, row["connection_id"], "read")
        if row["kind"] == "calendar.update":
            data = row["request"]["payload"]
            value = await self.connectors.adapter.snapshot(token, data["event_id"])
            if any(value.get(k, {}).get("dateTime") != data[k] for k in ("start", "end")):
                return {"state": "UNKNOWN", "resubmitted": False}
            receipt = value.get("id")
        else:
            evidence = await google.gmail_query(
                token, {"query": f"in:sent rfc822msgid:adex-{action}@adex.local"}
            )
            target = f"<adex-{action}@adex.local>"
            matches = [
                m
                for m in evidence["messages"]
                if any(
                    h.get("name", "").lower() == "message-id" and h.get("value") == target
                    for h in m["headers"]
                )
            ]
            if len(matches) != 1:
                return {"state": "UNKNOWN", "resubmitted": False}
            receipt = matches[0]["id"]
        result = {
            "state": "SUCCEEDED",
            "action_id": str(action),
            "provider_receipt": receipt,
            "verified": True,
            "reconciled": True,
        }
        await self._receipt(owner, action, result)
        return result
