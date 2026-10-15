"""Durable browser ownership and write gate on the existing approvals/effects.

Database mutex covers a bounded broker command, never holds a transaction across
browser I/O. Ambiguous commands/effects are not retried. Automation owns Run leases.
"""

import base64
import os
from contextlib import asynccontextmanager
from uuid import uuid4, uuid5, NAMESPACE_URL
import httpx
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from adex_kernel.core import digest, required
from adex_tools.connectors.vault import CredentialVault
from adex_tools.browser.process import BrowserPool
from adex_tools.browser.policy import BrowserStep, approval_summary
from adex_tools.runners.browser_policy import admitted_hosts

pool = BrowserPool()
INSTANCE = str(uuid4())


class BrowserService:
    def __init__(self, core):
        self.core = core

    def vault(self):
        return CredentialVault("ADEX_BROWSER_ENCRYPTION_KEY")

    async def authorize(self, owner, execution):
        return await self.core.call(
            "automation",
            "effect:execute",
            "POST",
            f"/internal/runs/{execution['run_id']}/authorize-effect",
            {**execution, "browser_run_id": str(execution["run_id"])},
            owner=owner,
            resource=execution["run_id"],
        )

    async def own(self, owner, session):
        row = await self.core.query(
            "SELECT * FROM browser_sessions WHERE id=%s AND owner_id=%s", (session, owner), one=True
        )
        if not row:
            raise HTTPException(404, "BROWSER_SESSION_NOT_FOUND")
        return row

    async def list(self, owner):
        rows = await self.core.query(
            "SELECT id,run_id,conversation_id,status,current_url,revision,action_id,updated_at FROM browser_sessions WHERE owner_id=%s ORDER BY updated_at DESC LIMIT 30",
            (owner,),
        )
        return {
            "items": rows,
            "availability": "CONFIGURED_UNVERIFIED"
            if os.getenv("ADEX_BROWSER_ENCRYPTION_KEY")
            else "BLOCKED_EXTERNAL",
        }

    async def ensure(self, owner, body):
        authorized = await self.authorize(owner, body)
        if str(authorized.get("origin_conversation_id")) != str(body["conversation_id"]):
            raise HTTPException(403, "BROWSER_CONVERSATION_MISMATCH")
        admitted_hosts(body["url"])
        self.vault()
        session = uuid5(NAMESPACE_URL, f"adex:browser:{owner}:{body['run_id']}")
        await self.core.query(
            "INSERT INTO browser_sessions(id,owner_id,run_id,conversation_id,origin_url,current_url) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(run_id) DO NOTHING",
            (session, owner, body["run_id"], body["conversation_id"], body["url"], body["url"]),
        )
        return await self.own(owner, session)

    @asynccontextmanager
    async def command(self, owner, session, execution=None):
        row = await self.own(owner, session)
        if row["status"] == "CLOSED":
            raise HTTPException(409, "BROWSER_SESSION_CLOSED")
        if execution:
            await self.authorize(owner, execution)
            if str(row["run_id"]) != str(execution["run_id"]):
                raise HTTPException(403, "BROWSER_RUN_MISMATCH")
            if row["status"] == "HUMAN":
                raise HTTPException(409, "BROWSER_HUMAN_CONTROL")
        command = uuid4()
        claimed = await self.core.query(
            "UPDATE browser_sessions SET active_command=%s,command_until=clock_timestamp()+interval '45 seconds' WHERE id=%s AND owner_id=%s AND (active_command IS NULL OR command_until<clock_timestamp()) RETURNING *",
            (command, session, owner),
            one=True,
        )
        if not claimed:
            raise HTTPException(409, "BROWSER_COMMAND_BUSY")
        try:
            row = claimed
            if execution and row["status"] == "HUMAN":
                raise HTTPException(409, "BROWSER_HUMAN_CONTROL")
            if row["runtime_id"] and row["runtime_id"] != INSTANCE:
                raise HTTPException(409, "BROWSER_SESSION_ON_OTHER_INSTANCE")
            storage = (
                self.vault().open(row["storage_cipher"], f"browser:{owner}:{session}")
                if row["storage_cipher"]
                else None
            )
            if not storage:
                from adex_tools.browser.profiles import BrowserProfiles

                storage = await BrowserProfiles(self.core).load(owner, session, row["current_url"])
            # Browser loss while a write is pending is not permission to replay it.
            if session not in pool.items and row["action_id"]:
                raise HTTPException(409, "BROWSER_REQUEST_LOST_REVIEW_REQUIRED")
            from urllib.parse import urlsplit

            fixture = (
                os.getenv("ADEX_BROWSER_TEST_FIXTURE") == "true"
                and os.getenv("ADEX_MODEL_PROVIDER") == "mock"
                and urlsplit(os.getenv("ADEX_DB_URL", "")).path.startswith("/adex_test_")
            )
            actor = await pool.get(
                session,
                {
                    "url": row["current_url"],
                    "storage": storage,
                    "_test_fixture": fixture,
                    "read_hosts": row["snapshot"].get("read_hosts"),
                },
            )
            await self.core.query(
                "UPDATE browser_sessions SET runtime_id=%s WHERE id=%s AND active_command=%s",
                (INSTANCE, session, command),
            )
            yield row, actor
        finally:
            await self.core.query(
                "UPDATE browser_sessions SET active_command=NULL,command_until=NULL WHERE id=%s AND active_command=%s",
                (session, command),
            )
            current = await self.own(owner, session)
            if current["status"] == "CLOSED":
                await pool.close(session)

    async def record(self, row, value, *, mode=None):
        storage = value.pop("_storage", None)
        cipher = (
            self.vault().seal(storage, f"browser:{row['owner_id']}:{row['id']}")
            if storage
            else row["storage_cipher"]
        )
        from adex_tools.browser.login import login_form

        value["login_form"] = login_form(value)
        snapshot = {k: v for k, v in value.items() if k != "screenshot"}
        progress = list(row["snapshot"].get("progress_events", []))
        if row.get("_progress"):
            progress.append(row["_progress"])
        snapshot["progress_events"] = progress[-20:]
        receipts = list(row["snapshot"].get("business_receipts", []))
        receipt = value.get("receipt")
        if (
            receipt
            and receipt.get("business_verified")
            and receipt.get("provider_receipt") not in [r.get("provider_receipt") for r in receipts]
        ):
            receipts.append(receipt)
        snapshot["business_receipts"] = receipts[-10:]
        action = row["action_id"]
        pending_cipher = row["pending_cipher"]
        state = mode or row["status"]
        if value.get("pending"):
            pending = value["pending"]
            action = uuid5(NAMESPACE_URL, f"browser-request:{row['id']}:{pending['id']}")
            request = {
                "origin_conversation_id": str(row["conversation_id"]),
                "browser_session_id": str(row["id"]),
                "browser_run_id": str(row["run_id"]),
                "payload": pending["preview"],
                "gesture": pending["gesture"],
                "before": pending.get("before", {}),
                "summary": approval_summary(pending),
            }
            await self.core.query(
                "INSERT INTO approvals(id,owner_id,kind,request,request_hash,expires_at) VALUES(%s,%s,'browser.request',%s,%s,clock_timestamp()+interval '10 minutes') ON CONFLICT(id) DO NOTHING",
                (action, row["owner_id"], Jsonb(request), digest(request)),
            )
            pending_cipher = self.vault().seal(pending, f"browser-pending:{row['owner_id']}:{row['id']}")
            state = "WAITING_APPROVAL"
        updated = await self.core.query(
            "UPDATE browser_sessions SET snapshot=%s,storage_cipher=%s,pending_cipher=%s,status=%s,action_id=%s,current_url=%s,revision=revision+1,updated_at=now() WHERE id=%s AND active_command=%s AND command_until>clock_timestamp() RETURNING *",
            (
                Jsonb(snapshot),
                cipher,
                pending_cipher,
                state,
                action,
                value["url"],
                row["id"],
                row["active_command"],
            ),
            one=True,
        )
        if not updated:
            raise HTTPException(409, "STALE_BROWSER_COMMAND")
        approval = (
            await self.core.query(
                "SELECT state FROM approvals WHERE id=%s AND owner_id=%s", (action, row["owner_id"]), one=True
            )
            if action
            else None
        )
        from urllib.parse import urlsplit

        profile = await self.core.query(
            "SELECT revision FROM browser_profiles WHERE owner_id=%s AND host=%s",
            (row["owner_id"], urlsplit(value["url"]).hostname),
            one=True,
        )
        return {
            "profile_revision": profile["revision"] if profile else 0,
            **snapshot,
            "approval_state": approval["state"] if approval else None,
            "id": str(row["id"]),
            "run_id": str(row["run_id"]),
            "status": state,
            "action_id": str(action) if action else None,
            "revision": updated["revision"],
            **({"screenshot": value["screenshot"]} if "screenshot" in value else {}),
        }

    async def view(self, owner, session):
        row = await self.own(owner, session)
        actor = pool.items.get(session)
        lost = bool(row["runtime_id"]) and (row["runtime_id"] != INSTANCE or session not in pool.items)
        if row["status"] == "HUMAN" and not row["active_command"] and not lost:
            return await self.observe(owner, session, screenshot=True)
        from urllib.parse import urlsplit

        profile = await self.core.query(
            "SELECT revision FROM browser_profiles WHERE owner_id=%s AND host=%s",
            (owner, urlsplit(row["current_url"]).hostname),
            one=True,
        )
        return {
            "profile_revision": profile["revision"] if profile else 0,
            **row["snapshot"],
            **(actor.preview if actor else {}),
            "id": str(session),
            "run_id": str(row["run_id"]),
            "status": "LOST" if lost and row["status"] not in ("CLOSED", "UNKNOWN") else row["status"],
            "action_id": str(row["action_id"]) if row["action_id"] else None,
            "revision": row["revision"],
        }

    async def observe(self, owner, session, execution=None, screenshot=False):
        async with self.command(owner, session, execution) as (row, actor):
            value = await actor.call({"action": "observe", "screenshot": screenshot or bool(execution)})
            return await self.record(row, value)

    async def step(self, owner, session, execution, body, key):
        step = BrowserStep.model_validate(body["step"])
        async with self.command(owner, session, execution) as (row, actor):
            if row["status"] != "AGENT":
                raise HTTPException(409, "BROWSER_APPROVAL_OR_HANDOFF_REQUIRED")
            if row["steps"] >= 60:
                raise HTTPException(409, "BROWSER_STEP_BUDGET_EXCEEDED")
            from datetime import datetime, timezone

            row["_progress"] = {
                "step": row["steps"] + 1,
                "at": datetime.now(timezone.utc).isoformat(),
                "text": {
                    "navigate": "打开目标网页",
                    "click": "操作网页控件",
                    "type": "整理并填写内容",
                    "select": "选择网页选项",
                    "scroll": "查看页面信息",
                    "back": "返回上一步",
                    "upload": "上传授权附件",
                    "switch_tab": "切换网页标签",
                    "handoff": "等待你登录或处理验证",
                    "done": "核对执行结果",
                }.get(step.action, "处理网页"),
            }
            request_hash = digest({"step": step.model_dump(), "observation_id": body["observation_id"]})
            effect_key = f"browser-step:{session}:{key}"
            old = await self.core.query(
                "SELECT * FROM effects WHERE owner_id=%s AND effect_key=%s", (owner, effect_key), one=True
            )
            if old:
                if old["request_hash"] != request_hash:
                    raise HTTPException(409, "IDEMPOTENCY_CONFLICT")
                if old["state"] == "SUCCEEDED":
                    return old["result"]
                raise HTTPException(409, "BROWSER_COMMAND_UNKNOWN")
            await self.core.query(
                "INSERT INTO effects(owner_id,effect_key,request_hash,tool_id,state) VALUES(%s,%s,%s,'browser.ui','IN_FLIGHT')",
                (owner, effect_key, request_hash),
            )
            try:
                command = {**step.model_dump(), "observation_id": body["observation_id"]}
                if step.action == "handoff":
                    value = await actor.call({"action": "mode", "mode": "HUMAN"})
                    result = await self.record(row, value, mode="HUMAN")
                elif step.action == "done":
                    result = await self.record(row, await actor.call({"action": "observe"}))
                else:
                    if step.action == "upload":
                        command.update(await self.upload(owner, step.file_id))
                    result = await self.record(row, await actor.call(command))
                await self.core.query("UPDATE browser_sessions SET steps=steps+1 WHERE id=%s", (session,))
                await self.core.query(
                    "UPDATE effects SET state='SUCCEEDED',result=%s WHERE owner_id=%s AND effect_key=%s",
                    (Jsonb(result), owner, effect_key),
                )
                return result
            except BaseException:
                await self.core.query(
                    "UPDATE effects SET state='UNKNOWN' WHERE owner_id=%s AND effect_key=%s",
                    (owner, effect_key),
                )
                raise

    async def upload(self, owner, file_id):
        from uuid import UUID

        file_id = UUID(file_id)
        metadata = await self.core.call(
            "app", "file:read", "GET", f"/internal/files/{file_id}", owner=owner, resource=file_id
        )
        async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
            async with client.stream(
                "GET",
                required("ADEX_APP_URL") + f"/internal/files/{file_id}/content",
                headers={"Authorization": "Bearer " + self.core.token("app", "file:read", owner, file_id)},
            ) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 5 * 1024 * 1024:
                        raise HTTPException(413, "BROWSER_UPLOAD_TOO_LARGE")
        return {
            "file_base64": base64.b64encode(content).decode(),
            "file_name": metadata.get("name", "attachment"),
            "file_mime": metadata.get("mime_type", "application/octet-stream"),
        }

    async def recover(self, owner, session):
        row = await self.own(owner, session)
        if row["status"] == "CLOSED":
            raise HTTPException(409, "BROWSER_SESSION_CLOSED")
        if row["action_id"]:
            action = await self.core.query(
                "SELECT state FROM approvals WHERE id=%s AND owner_id=%s", (row["action_id"], owner), one=True
            )
            if action and action["state"] in ("UNKNOWN", "SUCCEEDED"):
                raise HTTPException(409, "BROWSER_UNKNOWN_REQUIRES_RECONCILIATION")
        changed = await self.core.query(
            "UPDATE browser_sessions SET runtime_id=NULL,action_id=NULL,pending_cipher=NULL,status='HUMAN',active_command=NULL,command_until=NULL WHERE id=%s AND owner_id=%s AND (active_command IS NULL OR command_until<clock_timestamp()) RETURNING id",
            (session, owner),
            one=True,
        )
        if not changed:
            raise HTTPException(409, "BROWSER_COMMAND_BUSY")
        if row["action_id"]:
            await self.core.query(
                "UPDATE approvals SET state='REVOKED' WHERE id=%s AND owner_id=%s AND state IN ('PENDING','APPROVED')",
                (row["action_id"], owner),
            )
        await pool.close(session)
        async with self.command(owner, session) as (current, actor):
            value = await actor.call({"action": "mode", "mode": "HUMAN", "human": True})
            return await self.record(current, value, mode="HUMAN")

    async def control(self, owner, session, body):
        action = body["action"]
        if action == "recover":
            return await self.recover(owner, session)
        async with self.command(owner, session) as (row, actor):
            if action == "remember":
                from adex_tools.browser.profiles import BrowserProfiles

                value = await actor.call({"action": "observe", "screenshot": True})
                saved = await BrowserProfiles(self.core).remember(
                    owner, session, value["url"], value["_storage"], body.get("profile_revision", 0)
                )
                return {**(await self.record(row, value)), "saved_profile": saved}
            if action == "reject":
                approval = await self.core.query(
                    "SELECT state FROM approvals WHERE id=%s AND owner_id=%s",
                    (row["action_id"], owner),
                    one=True,
                )
                if not approval or approval["state"] != "REVOKED":
                    raise HTTPException(409, "APPROVAL_NOT_REVOKED")
                pending = self.vault().open(row["pending_cipher"], f"browser-pending:{owner}:{session}")
                await actor.call(
                    {
                        "action": "release",
                        "request_id": pending["id"],
                        "digest": pending["digest"],
                        "allow": False,
                    }
                )
                row.update(action_id=None, pending_cipher=None, status="HUMAN")
                return await self.record(
                    row, await actor.call({"action": "mode", "mode": "HUMAN", "human": True}), mode="HUMAN"
                )
            if action == "takeover":
                if row["status"] in ("WAITING_APPROVAL", "UNKNOWN"):
                    raise HTTPException(409, "RESOLVE_BROWSER_APPROVAL_FIRST")
                return await self.record(
                    row, await actor.call({"action": "mode", "mode": "HUMAN", "human": True}), mode="HUMAN"
                )
            if action == "resume" and row["status"] == "AGENT":
                return await self.record(row, await actor.call({"action": "observe"}), mode="AGENT")
            if row["status"] != "HUMAN":
                raise HTTPException(409, "BROWSER_NOT_IN_HUMAN_MODE")
            if action == "resume":
                return await self.record(
                    row, await actor.call({"action": "mode", "mode": "AGENT", "human": True}), mode="AGENT"
                )
            if action not in (
                "secure_login",
                "observe",
                "click",
                "point",
                "type",
                "key",
                "scroll",
                "navigate",
                "back",
                "switch_tab",
                "dialog_accept",
                "dialog_dismiss",
            ):
                raise HTTPException(400, "BROWSER_ACTION_NOT_ALLOWED")
            # Secure input is forwarded transiently and is never persisted as an
            # action, model prompt, checkpoint or effect request body.
            return await self.record(row, await actor.call({**body, "human": True, "screenshot": True}))

    async def dispatch(self, owner, action, execution):
        await self.authorize(owner, execution)
        approval = await self.core.query(
            "SELECT * FROM approvals WHERE id=%s AND owner_id=%s AND kind='browser.request'",
            (action, owner),
            one=True,
        )
        if not approval:
            raise HTTPException(404, "ACTION_NOT_FOUND")
        if str(approval["request"]["browser_run_id"]) != str(execution["run_id"]):
            raise HTTPException(403, "BROWSER_ACTION_RUN_MISMATCH")
        if approval["state"] == "SUCCEEDED":
            return approval["result"]
        session = approval["request"]["browser_session_id"]
        from uuid import UUID

        session = UUID(session)
        async with self.command(owner, session, execution) as (row, actor):
            if str(row["run_id"]) != str(execution["run_id"]) or str(row["action_id"]) != str(action):
                raise HTTPException(403, "BROWSER_ACTION_RUN_MISMATCH")
            pending = self.vault().open(row["pending_cipher"], f"browser-pending:{owner}:{session}")
            gate = {"request_id": pending["id"], "digest": pending["digest"], "allow": True}
            try:
                await actor.call({"action": "validate_release", **gate})
            except HTTPException as error:
                if error.detail in ("BROWSER_APPROVAL_SNAPSHOT_CHANGED", "BROWSER_REQUEST_LOST"):
                    await self.core.query(
                        "UPDATE approvals SET state='REVOKED' WHERE id=%s AND owner_id=%s AND state='APPROVED'",
                        (action, owner),
                    )
                    await actor.call({"action": "release", **gate, "allow": False})
                    row.update(status="HUMAN", action_id=None, pending_cipher=None)
                    await self.record(
                        row, await actor.call({"action": "mode", "mode": "HUMAN"}), mode="HUMAN"
                    )
                    return {"state": "REAPPROVAL_REQUIRED", "verified": False}
                raise
            # Approval -> uncertain effect is committed BEFORE releasing the actual
            # held request. Cancellation/crash after this point must not resubmit.
            async with self.core.pool.connection() as conn:
                async with conn.transaction():
                    current = await (
                        await conn.execute(
                            "SELECT *,expires_at>clock_timestamp() AS valid FROM approvals WHERE id=%s AND owner_id=%s FOR UPDATE",
                            (action, owner),
                        )
                    ).fetchone()
                    if current["state"] == "SUCCEEDED":
                        return current["result"]
                    if current["state"] != "APPROVED" or not current["valid"]:
                        raise HTTPException(409, "APPROVAL_EXPIRED_OR_ALREADY_DISPATCHED")
                    await conn.execute(
                        "INSERT INTO effects(owner_id,effect_key,request_hash,tool_id,state) VALUES(%s,%s,%s,'browser.request','IN_FLIGHT')",
                        (owner, "action:" + str(action), approval["request_hash"]),
                    )
                    await conn.execute(
                        "UPDATE approvals SET state='UNKNOWN',run_id=%s WHERE id=%s", (row["run_id"], action)
                    )
                    await conn.execute("UPDATE browser_sessions SET status='UNKNOWN' WHERE id=%s", (session,))
            value = await actor.call(
                {"action": "release", "request_id": pending["id"], "digest": pending["digest"], "allow": True}
            )
            result = await self.finish_receipt(owner, action, value.get("receipt"))
            if result.get("verified"):
                row.update(status="AGENT", action_id=None, pending_cipher=None)
            else:
                row["status"] = "UNKNOWN"
            await self.record(row, value)
            return result

    async def finish_receipt(self, owner, action, receipt):
        if not receipt or not receipt.get("verified") or not receipt.get("provider_receipt"):
            await self.core.query(
                "UPDATE effects SET state='UNKNOWN' WHERE owner_id=%s AND effect_key=%s",
                (owner, "action:" + str(action)),
            )
            return {"state": "UNKNOWN", "verified": False, "resubmitted": False}
        result = {**receipt, "action_id": str(action), "transport_only": not receipt.get("business_verified")}
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
        return result

    async def reconcile(self, owner, action):
        row = await self.core.query(
            "SELECT * FROM approvals WHERE id=%s AND owner_id=%s AND kind='browser.request'",
            (action, owner),
            one=True,
        )
        if not row:
            raise HTTPException(404, "ACTION_NOT_FOUND")
        if row["state"] == "SUCCEEDED":
            await self.core.query(
                "UPDATE browser_sessions SET status='AGENT',action_id=NULL,pending_cipher=NULL WHERE id=%s AND owner_id=%s AND status<>'CLOSED'",
                (row["request"]["browser_session_id"], owner),
            )
            return row["result"]
        from uuid import UUID

        session = UUID(row["request"]["browser_session_id"])
        value = await self.observe(owner, session)
        result = await self.finish_receipt(owner, action, value.get("receipt"))
        if result.get("verified"):
            await self.core.query(
                "UPDATE browser_sessions SET status='AGENT',action_id=NULL,pending_cipher=NULL WHERE id=%s AND owner_id=%s",
                (session, owner),
            )
        return result

    async def close(self, owner, session):
        row = await self.own(owner, session)
        await pool.close(session)
        await self.core.query(
            "UPDATE browser_sessions SET status='CLOSED',storage_cipher=NULL,pending_cipher=NULL,snapshot='{}',active_command=NULL,command_until=NULL,revision=revision+1 WHERE id=%s AND owner_id=%s",
            (session, owner),
        )
        if row["action_id"]:
            await self.core.query(
                "UPDATE approvals SET state='REVOKED' WHERE id=%s AND owner_id=%s AND state IN ('PENDING','APPROVED')",
                (row["action_id"], owner),
            )
        return {"status": "CLOSED"}
