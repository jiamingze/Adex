"""OAuth, revocation and provider reads with owner/revision credential fencing."""

import base64
import hashlib
import os
import secrets
import time
from uuid import uuid4
from urllib.parse import urlencode
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from adex_kernel.core import digest
from .vault import CredentialVault
from . import google
from .adapters import adapter


def configured():
    return bool(
        os.getenv("ADEX_GOOGLE_CLIENT_ID")
        and os.getenv("ADEX_GOOGLE_CLIENT_SECRET")
        and os.getenv("ADEX_GOOGLE_REDIRECT_URI")
        and os.getenv("ADEX_CONNECTOR_ENCRYPTION_KEY")
    )


def configuration():
    if not configured():
        raise HTTPException(503, "BLOCKED_EXTERNAL")
    uri = os.environ["ADEX_GOOGLE_REDIRECT_URI"]
    if not uri.startswith("https://") and not google.fixture_mode():
        raise HTTPException(503, "BLOCKED_EXTERNAL")
    return {
        "client_id": os.environ["ADEX_GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["ADEX_GOOGLE_CLIENT_SECRET"],
        "redirect_uri": uri,
    }


def aad(owner, connection):
    return f"google:{owner}:{connection}"


class ConnectorService:
    def __init__(self, core, provider=None):
        self.core = core
        self.adapter = provider or adapter()

    async def list(self, owner):
        rows = await self.core.query(
            "SELECT id,service,status,scopes,revision,created_at FROM connector_connections WHERE owner_id=%s ORDER BY created_at DESC",
            (owner,),
        )
        return {
            "items": rows,
            "availability": "CONFIGURED_UNVERIFIED" if configured() else "BLOCKED_EXTERNAL",
        }

    async def authorize(self, owner, session, service, access):
        config = configuration()
        scope = google.SCOPES.get((service, access))
        if not scope:
            raise HTTPException(400, "INVALID_CONNECTOR_ACCESS")
        await self.core.query("DELETE FROM connector_oauth_states WHERE expires_at<clock_timestamp()")
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        state_hash = digest(state)
        await self.core.query(
            "INSERT INTO connector_oauth_states(state_hash,owner_id,session_binding,service,scopes,verifier_cipher,expires_at) VALUES(%s,%s,%s,%s,%s,%s,now()+interval '10 minutes')",
            (
                state_hash,
                owner,
                session,
                service,
                Jsonb([scope]),
                CredentialVault().seal({"verifier": verifier}, aad(owner, state_hash)),
            ),
        )
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        params = {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "response_type": "code",
            "scope": scope,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
        }
        return {
            "authorization_url": (
                google.endpoint("oauth") + "/authorize"
                if google.fixture_mode()
                else "https://accounts.google.com/o/oauth2/v2/auth"
            )
            + "?"
            + urlencode(params),
            "requested_scopes": [scope],
        }

    async def callback(self, owner, session, state, code):
        config = configuration()
        state_hash = digest(state)
        row = await self.core.query(
            "UPDATE connector_oauth_states SET consumed_at=now() WHERE state_hash=%s AND owner_id=%s AND session_binding=%s AND consumed_at IS NULL AND expires_at>clock_timestamp() RETURNING *",
            (state_hash, owner, session),
            one=True,
        )
        if not row:
            raise HTTPException(403, "OAUTH_STATE_INVALID")
        vault = CredentialVault()
        verifier = vault.open(row["verifier_cipher"], aad(owner, state_hash))["verifier"]
        value = await google.tokens(
            {**config, "grant_type": "authorization_code", "code": code, "code_verifier": verifier}
        )
        scopes = value.get("scope", "").split()
        if not set(row["scopes"]).issubset(scopes) or not value.get("refresh_token"):
            raise HTTPException(403, "OAUTH_CONSENT_INCOMPLETE")
        connection = uuid4()
        await self.core.query(
            "INSERT INTO connector_connections(id,owner_id,service,status,scopes,credentials) VALUES(%s,%s,%s,'ACTIVE',%s,%s)",
            (connection, owner, row["service"], Jsonb(scopes), vault.seal(value, aad(owner, connection))),
        )
        await self.core.query("DELETE FROM connector_oauth_states WHERE state_hash=%s", (state_hash,))
        return {
            "id": connection,
            "service": row["service"],
            "status": "ACTIVE",
            "provider": "TEST_FIXTURE" if google.fixture_mode() else "google",
        }

    async def own(self, owner, connection):
        row = await self.core.query(
            "SELECT * FROM connector_connections WHERE id=%s AND owner_id=%s", (connection, owner), one=True
        )
        if not row:
            raise HTTPException(404, "CONNECTOR_NOT_FOUND")
        return row

    async def credential(self, owner, connection, access):
        row = await self.own(owner, connection)
        if row["status"] != "ACTIVE":
            raise HTTPException(403, "CONNECTOR_REVOKED_OR_REAUTH_REQUIRED")
        required = google.SCOPES.get((row["service"], access))
        scopes = set(row["scopes"])
        if required not in scopes and not (
            row["service"] == "calendar"
            and access == "read"
            and google.SCOPES[("calendar", "write")] in scopes
        ):
            raise HTTPException(403, "CONNECTOR_SCOPE_REQUIRED")
        vault = CredentialVault()
        tokens = vault.open(row["credentials"], aad(owner, connection))
        if tokens.get("expires_at", 0) < time.time() + 60:
            try:
                new = await google.tokens(
                    {
                        "client_id": configuration()["client_id"],
                        "client_secret": configuration()["client_secret"],
                        "grant_type": "refresh_token",
                        "refresh_token": tokens["refresh_token"],
                    }
                )
            except HTTPException as exc:
                if exc.detail == "CONNECTOR_REAUTH_REQUIRED":
                    await self.core.query(
                        "UPDATE connector_connections SET status='REAUTH_REQUIRED',revision=revision+1 WHERE id=%s AND revision=%s",
                        (connection, row["revision"]),
                    )
                raise
            tokens = {**tokens, **new}
            updated = await self.core.query(
                "UPDATE connector_connections SET credentials=%s,revision=revision+1,updated_at=now() WHERE id=%s AND owner_id=%s AND revision=%s AND status='ACTIVE' RETURNING *",
                (vault.seal(tokens, aad(owner, connection)), connection, owner, row["revision"]),
                one=True,
            )
            if not updated:
                raise HTTPException(409, "CONNECTOR_CHANGED")
            row = updated
        return row, tokens["access_token"]

    async def check_revision(self, row):
        current = await self.own(row["owner_id"], row["id"])
        if current["status"] != "ACTIVE" or current["revision"] != row["revision"]:
            raise HTTPException(409, "CONNECTOR_CHANGED")

    async def revoke(self, owner, connection):
        row = await self.own(owner, connection)
        if row["status"] == "REVOKED":
            return {"status": "REVOKED"}
        await self.core.query(
            "UPDATE connector_connections SET status='REVOKE_PENDING',revision=revision+1,updated_at=now() WHERE id=%s AND owner_id=%s AND status<>'REVOKED'",
            (connection, owner),
        )
        # Disable access before I/O. Retain encrypted material solely to retry
        # revocation after network failure; erase it only on confirmed revocation.
        token = CredentialVault().open(row["credentials"], aad(owner, connection))["refresh_token"]
        try:
            await google.http("POST", google.endpoint("oauth") + "/revoke", data={"token": token})
        except HTTPException:
            return {"status": "REVOKE_PENDING", "remote_revocation": "UNKNOWN"}
        await self.core.query(
            "UPDATE connector_connections SET status='REVOKED',credentials=NULL,updated_at=now() WHERE id=%s AND owner_id=%s",
            (connection, owner),
        )
        return {"status": "REVOKED", "remote_revocation": "CONFIRMED"}

    async def query(self, owner, connection, query):
        row, token = await self.credential(owner, connection, "read")
        result = await self.adapter.query(token, row["service"], query)
        await self.check_revision(row)
        return {**result, "connection_revision": row["revision"]}

    async def sync(self, owner, connection, run_id, query):
        old = await self.core.query(
            "SELECT result FROM connector_sync_receipts WHERE owner_id=%s AND run_id=%s",
            (owner, run_id),
            one=True,
        )
        if old:
            return old["result"]
        row = await self.own(owner, connection)
        evidence = await self.query(owner, connection, query)
        signals = []
        if row["service"] == "calendar":
            events = {x["id"]: x for x in evidence["events"]}
            for conflict in evidence["conflicts"]:
                pair = sorted([conflict["first"], conflict["second"]])
                signals.append(
                    {
                        "connection_id": str(connection),
                        "resource_id": ":".join(pair),
                        "resource_version": digest([events[x].get("etag") for x in pair]),
                        "kind": "CALENDAR_CONFLICT",
                        "correlation_key": "calendar:" + ":".join(pair),
                        "suggestion": "发现日历时间冲突，可查看事件并提出调整草稿，修改前需要你确认。",
                        "evidence": {"events": [events[x] for x in pair], "provider": evidence["provider"]},
                    }
                )
        else:
            for message in evidence["messages"]:
                if "IMPORTANT" in message["labelIds"]:
                    signals.append(
                        {
                            "connection_id": str(connection),
                            "resource_id": message["id"],
                            "resource_version": str(message.get("historyId") or digest(message)),
                            "kind": "IMPORTANT_EMAIL",
                            "correlation_key": "gmail:" + str(message.get("threadId") or message["id"]),
                            "suggestion": "有重要邮件发生变化，建议查看邮件并决定是否需要回复。发送回复前需要你确认。",
                            "evidence": {"message": message, "provider": evidence["provider"]},
                        }
                    )
        result = {
            "signals": signals[:100],
            "partial": evidence.get("partial", False),
            "provider": evidence["provider"],
        }
        async with self.core.pool.connection() as conn:
            async with conn.transaction():
                linked = await (
                    await conn.execute(
                        "SELECT status,revision FROM connector_connections WHERE id=%s AND owner_id=%s FOR SHARE",
                        (connection, owner),
                    )
                ).fetchone()
                if (
                    not linked
                    or linked["status"] != "ACTIVE"
                    or linked["revision"] != evidence["connection_revision"]
                ):
                    raise HTTPException(409, "CONNECTOR_CHANGED")
                await conn.execute(
                    "INSERT INTO connector_sync_receipts(owner_id,run_id,connection_id,result) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (owner, run_id, connection, Jsonb(result)),
                )
        return (
            await self.core.query(
                "SELECT result FROM connector_sync_receipts WHERE owner_id=%s AND run_id=%s",
                (owner, run_id),
                one=True,
            )
        )["result"]
