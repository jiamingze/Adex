"""CalDAV effect prepared durably before I/O; ambiguous submissions stay UNKNOWN."""

import os
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from adex_kernel.core import digest


def ical_text(value):
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def calendar_object(request, uid):
    start = datetime.fromisoformat(request["start"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(request["end"].replace("Z", "+00:00"))
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        raise HTTPException(400, "INVALID_EVENT_TIME")

    def date(x):
        return x.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Adex//Calendar//EN",
            "BEGIN:VEVENT",
            f"UID:{uid}@adex",
            f"DTSTAMP:{date(datetime.now(timezone.utc))}",
            f"DTSTART:{date(start)}",
            f"DTEND:{date(end)}",
            "SUMMARY:" + ical_text(request["title"]),
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


async def create_approval(core, owner, request):
    calendar_object(request, str(uuid4()))
    row = await core.query(
        "INSERT INTO approvals(id,owner_id,request,request_hash) VALUES(%s,%s,%s,%s) RETURNING *",
        (uuid4(), owner, Jsonb(request), digest(request)),
        one=True,
    )
    return row


async def act(core, owner, approval_id, action, execution=None):
    async with core.pool.connection() as conn:
        async with conn.transaction():
            cur = await conn.execute(
                "SELECT *,expires_at>clock_timestamp() AS valid FROM approvals WHERE id=%s AND owner_id=%s AND kind='calendar.create' FOR UPDATE",
                (approval_id, owner),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(404, "APPROVAL_NOT_FOUND")
            if action == "revoke":
                if row["state"] not in ("PENDING", "APPROVED"):
                    raise HTTPException(409, "ACTION_ALREADY_DISPATCHED")
                await conn.execute("UPDATE approvals SET state='REVOKED' WHERE id=%s", (approval_id,))
                return {"state": "REVOKED"}
            if action == "approve":
                if row["state"] == "APPROVED":
                    return {"state": "APPROVED", "request": row["request"]}
                if row["state"] != "PENDING" or not row["valid"]:
                    raise HTTPException(409, "APPROVAL_EXPIRED_OR_REVOKED")
                await conn.execute("UPDATE approvals SET state='APPROVED' WHERE id=%s", (approval_id,))
                return {"state": "APPROVED", "request": row["request"]}
            if action != "execute" or not execution:
                raise HTTPException(400, "INVALID_ACTION")
            if row["state"] == "SUCCEEDED":
                return row["result"]
            if row["state"] == "UNKNOWN":
                raise HTTPException(409, "PROVIDER_UNKNOWN")
            if not row["valid"] or row["state"] != "APPROVED":
                raise HTTPException(409, "APPROVAL_EXPIRED_OR_REVOKED")
            endpoint = os.getenv("ADEX_CALDAV_URL", "")
            if os.getenv("ADEX_CALDAV_OWNER_ID", "") != str(owner):
                raise HTTPException(403, "CALENDAR_PERMISSION_REQUIRED")
            if not endpoint or urlparse(endpoint).scheme != "https":
                raise HTTPException(503, "BLOCKED_EXTERNAL")
            await conn.execute("UPDATE approvals SET state='UNKNOWN' WHERE id=%s", (approval_id,))
            await conn.execute(
                "INSERT INTO effects(owner_id,effect_key,request_hash,tool_id,state) VALUES(%s,%s,%s,'calendar.create','IN_FLIGHT')",
                (owner, "calendar:" + str(approval_id), row["request_hash"]),
            )
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client:
            response = await client.put(
                endpoint.rstrip("/") + "/" + str(approval_id) + ".ics",
                content=calendar_object(row["request"], str(approval_id)),
                headers={"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"},
                auth=(os.environ["ADEX_CALDAV_USERNAME"], os.environ["ADEX_CALDAV_PASSWORD"]),
            )
            if response.status_code not in (200, 201, 204):
                raise HTTPException(503, "CALENDAR_RESULT_UNKNOWN")
        result = {"state": "SUCCEEDED", "uid": str(approval_id)}
        async with core.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE approvals SET state='SUCCEEDED',result=%s WHERE id=%s",
                    (Jsonb(result), approval_id),
                )
                await conn.execute(
                    "UPDATE effects SET state='SUCCEEDED',result=%s WHERE owner_id=%s AND effect_key=%s",
                    (Jsonb(result), owner, "calendar:" + str(approval_id)),
                )
        return result
    except BaseException:
        await core.query("UPDATE approvals SET state='UNKNOWN' WHERE id=%s", (approval_id,))
        await core.query(
            "UPDATE effects SET state='UNKNOWN' WHERE owner_id=%s AND effect_key=%s",
            (owner, "calendar:" + str(approval_id)),
        )
        raise HTTPException(409, "PROVIDER_UNKNOWN") from None


async def reconcile(core, owner, approval_id):
    row = await core.query(
        "SELECT * FROM approvals WHERE id=%s AND owner_id=%s AND kind='calendar.create'",
        (approval_id, owner),
        one=True,
    )
    if not row:
        raise HTTPException(404, "APPROVAL_NOT_FOUND")
    if row["state"] == "SUCCEEDED":
        return row["result"]
    if row["state"] != "UNKNOWN":
        raise HTTPException(409, "RECONCILIATION_NOT_REQUIRED")
    endpoint = os.getenv("ADEX_CALDAV_URL", "")
    if os.getenv("ADEX_CALDAV_OWNER_ID", "") != str(owner):
        raise HTTPException(403, "CALENDAR_PERMISSION_REQUIRED")
    if urlparse(endpoint).scheme != "https":
        raise HTTPException(503, "BLOCKED_EXTERNAL")
    async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client:
        response = await client.get(
            endpoint.rstrip("/") + "/" + str(approval_id) + ".ics",
            auth=(os.environ["ADEX_CALDAV_USERNAME"], os.environ["ADEX_CALDAV_PASSWORD"]),
        )
    # A missing response does not prove a preceding PUT had no effect.
    if response.status_code != 200 or len(response.content) > 65536:
        return {"state": "UNKNOWN", "resubmitted": False}
    expected = calendar_object(row["request"], str(approval_id))
    required_lines = [
        line for line in expected.splitlines() if line.startswith(("UID:", "DTSTART:", "DTEND:", "SUMMARY:"))
    ]
    received = set(response.text.replace("\r\n ", "").splitlines())
    if not all(line in received for line in required_lines):
        return {"state": "UNKNOWN", "resubmitted": False}
    result = {"state": "SUCCEEDED", "uid": str(approval_id), "reconciled": True}
    async with core.pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE approvals SET state='SUCCEEDED',result=%s WHERE id=%s AND owner_id=%s AND state='UNKNOWN'",
                (Jsonb(result), approval_id, owner),
            )
            await conn.execute(
                "UPDATE effects SET state='SUCCEEDED',result=%s WHERE owner_id=%s AND effect_key=%s AND state IN ('IN_FLIGHT','UNKNOWN')",
                (Jsonb(result), owner, "calendar:" + str(approval_id)),
            )
    return result
