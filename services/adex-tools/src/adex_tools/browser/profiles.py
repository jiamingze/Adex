"""Explicit opt-in, domain-scoped encrypted login state. No stored passwords."""

from uuid import uuid5, NAMESPACE_URL
from urllib.parse import urlsplit
from fastapi import HTTPException
from adex_tools.connectors.vault import CredentialVault


class BrowserProfiles:
    def __init__(self, core):
        self.core = core

    async def list(self, owner):
        return {
            "items": await self.core.query(
                "SELECT id,host,revision,expires_at,updated_at FROM browser_profiles WHERE owner_id=%s AND cipher IS NOT NULL AND expires_at>clock_timestamp() ORDER BY updated_at DESC",
                (owner,),
            )
        }

    async def load(self, owner, session, url):
        host = urlsplit(url).hostname
        row = await self.core.query(
            "SELECT * FROM browser_profiles WHERE owner_id=%s AND host=%s AND cipher IS NOT NULL AND expires_at>clock_timestamp()",
            (owner, host),
            one=True,
        )
        if not row:
            return None
        state = CredentialVault("ADEX_BROWSER_ENCRYPTION_KEY").open(
            row["cipher"], f"browser-profile:{owner}:{host}"
        )
        await self.core.query(
            "INSERT INTO browser_session_profiles(session_id,profile_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (session, row["id"]),
        )
        return state

    async def remember(self, owner, session, url, state, expected_revision=0):
        host = urlsplit(url).hostname
        if not host:
            raise HTTPException(400, "BROWSER_PROFILE_DOMAIN_REQUIRED")
        # Save only credentials for the visible site, not unrelated login-provider
        # or shopping accounts accumulated while browsing other origins.
        cookies = [
            c
            for c in state.get("cookies", [])
            if host == c.get("domain", "").lstrip(".") or host.endswith("." + c.get("domain", "").lstrip("."))
        ]
        origins = [o for o in state.get("origins", []) if urlsplit(o.get("origin", "")).hostname == host]
        cipher = CredentialVault("ADEX_BROWSER_ENCRYPTION_KEY").seal(
            {"cookies": cookies, "origins": origins}, f"browser-profile:{owner}:{host}"
        )
        profile = uuid5(NAMESPACE_URL, f"browser-profile:{owner}:{host}")
        async with self.core.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (f"browser-profile:{owner}:{host}",),
                )
                old = await (
                    await conn.execute(
                        "SELECT revision FROM browser_profiles WHERE id=%s AND owner_id=%s FOR UPDATE",
                        (profile, owner),
                    )
                ).fetchone()
                if (old["revision"] if old else 0) != expected_revision:
                    raise HTTPException(409, "BROWSER_PROFILE_CHANGED_REVIEW_REQUIRED")
                if old:
                    await conn.execute(
                        "UPDATE browser_profiles SET cipher=%s,revision=revision+1,expires_at=clock_timestamp()+interval '7 days',updated_at=now() WHERE id=%s AND owner_id=%s",
                        (cipher, profile, owner),
                    )
                else:
                    await conn.execute(
                        "INSERT INTO browser_profiles(id,owner_id,host,cipher,expires_at) VALUES(%s,%s,%s,%s,clock_timestamp()+interval '7 days')",
                        (profile, owner, host, cipher),
                    )
                await conn.execute(
                    "INSERT INTO browser_session_profiles(session_id,profile_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                    (session, profile),
                )
        return {"id": str(profile), "host": host, "saved": True}

    async def revoke(self, owner, profile):
        row = await self.core.query(
            "UPDATE browser_profiles SET cipher=NULL,revision=revision+1,expires_at=clock_timestamp(),updated_at=now() WHERE id=%s AND owner_id=%s RETURNING id",
            (profile, owner),
            one=True,
        )
        if not row:
            raise HTTPException(404, "BROWSER_PROFILE_NOT_FOUND")
        return await self.core.query(
            "SELECT s.id,s.run_id FROM browser_sessions s JOIN browser_session_profiles p ON p.session_id=s.id WHERE p.profile_id=%s AND s.owner_id=%s AND s.status<>'CLOSED'",
            (profile, owner),
        )
