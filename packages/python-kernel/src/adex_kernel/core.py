import base64
import hashlib
import hmac
import json
import os
import time
import httpx
from fastapi import HTTPException, Request
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


def required(key: str) -> str:
    value = os.getenv(key, "")
    if not value:
        raise RuntimeError(f"Required configuration: {key}")
    return value


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


class Core:
    def __init__(self, service: str):
        self.service = service
        self.key = required(f"ADEX_{service.upper()}_KEY")
        if len(self.key) < 32:
            raise RuntimeError("Service key too short")
        self.pool = AsyncConnectionPool(
            required("ADEX_DB_URL"),
            min_size=1,
            max_size=6,
            open=False,
            kwargs={"row_factory": dict_row, "autocommit": True},
            timeout=3,
            check=AsyncConnectionPool.check_connection,
        )

    async def start(self):
        await self.pool.open()
        await self.pool.wait(timeout=10)

    async def query(self, sql, args=(), one=False):
        async with self.pool.connection() as conn:
            cur = await conn.execute(sql, args)
            if cur.description:
                return await cur.fetchone() if one else await cur.fetchall()
            return cur.rowcount

    def token(self, audience, scope, owner="*", resource="*"):
        claims = {
            "iss": self.service,
            "aud": audience,
            "scope": scope,
            "owner": str(owner),
            "resource": str(resource),
            "exp": int(time.time()) + 180,
        }
        payload = (
            base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        )
        sig = (
            base64.urlsafe_b64encode(
                hmac.new(self.key.encode(), payload.encode(), hashlib.sha256).digest()
            )
            .decode()
            .rstrip("=")
        )
        return payload + "." + sig

    def require(self, request: Request, issuer: str, scope: str, resource=None):
        try:
            raw = request.headers.get("authorization", "")
            if not raw.startswith("Bearer "):
                raise ValueError()
            p, sig = raw[7:].split(".")
            claims = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
            if claims["iss"] != issuer or claims["aud"] != self.service:
                raise ValueError()
            key = required(f"ADEX_{issuer.upper()}_KEY")
            actual = base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4))
            expected = hmac.new(key.encode(), p.encode(), hashlib.sha256).digest()
            if (
                not hmac.compare_digest(actual, expected)
                or not time.time() < claims["exp"] <= time.time() + 240
            ):
                raise ValueError()
        except Exception:
            raise HTTPException(401, detail="UNAUTHENTICATED") from None
        if (
            claims.get("scope") != scope
            or resource is not None
            and claims.get("resource") != str(resource)
        ):
            raise HTTPException(403, detail="SCOPE_DENIED")
        return claims

    async def call(
        self, audience, scope, method, path, body=None, owner="*", resource="*"
    ):
        async with httpx.AsyncClient(
            timeout=960 if scope == "creative:write" else 90
            if scope in ("search:read", "travel:read", "vision:read")
            else 30
            if scope in ("creative:write", "artifact:write", "code:check")
            else 15,
            trust_env=False,
        ) as client:
            r = await client.request(
                method,
                required(f"ADEX_{audience.upper()}_URL") + path,
                json=body,
                headers={
                    "Authorization": "Bearer "
                    + self.token(audience, scope, owner, resource)
                },
            )
            if r.is_error:
                try:
                    code = r.json().get(
                        "code", r.json().get("detail", "DEPENDENCY_UNAVAILABLE")
                    )
                except Exception:
                    code = "DEPENDENCY_UNAVAILABLE"
                raise HTTPException(r.status_code, detail=code)
            return r.json()


def owner_match(claims, owner):
    if claims["owner"] != str(owner):
        raise HTTPException(403, detail="SCOPE_DENIED")
