"""Fixed-host Google adapter. Fixture transports are isolated-test only."""

import base64
import os
import time
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import quote
import httpx
from fastapi import HTTPException

SCOPES = {
    ("calendar", "read"): "https://www.googleapis.com/auth/calendar.events.owned.readonly",
    ("calendar", "write"): "https://www.googleapis.com/auth/calendar.events.owned",
    ("gmail", "read"): "https://www.googleapis.com/auth/gmail.readonly",
    ("gmail", "send"): "https://www.googleapis.com/auth/gmail.send",
}


def fixture_mode():
    return os.getenv("ADEX_CONNECTOR_TEST_FIXTURE") == "true" and "/adex_test_" in os.getenv(
        "ADEX_DB_URL", ""
    )


def endpoint(kind: str):
    if fixture_mode():
        return "http://127.0.0.1:18109/" + kind
    return {
        "oauth": "https://oauth2.googleapis.com",
        "calendar": "https://www.googleapis.com/calendar/v3",
        "gmail": "https://gmail.googleapis.com/gmail/v1",
    }[kind]


async def http(method, url, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
            response = await client.request(method, url, **kwargs)
    except httpx.HTTPError:
        raise HTTPException(409, "PROVIDER_UNKNOWN") from None
    if (
        response.status_code == 400
        and url.endswith("/token")
        and response.json().get("error") == "invalid_grant"
    ):
        raise HTTPException(409, "CONNECTOR_REAUTH_REQUIRED")
    if response.status_code == 401:
        raise HTTPException(409, "CONNECTOR_REAUTH_REQUIRED")
    if response.status_code == 412:
        raise HTTPException(409, "RESOURCE_CHANGED_REAPPROVAL_REQUIRED")
    if response.status_code == 403:
        raise HTTPException(403, "CONNECTOR_SCOPE_REQUIRED")
    if response.is_error:
        raise HTTPException(503, "CONNECTOR_PROVIDER_UNAVAILABLE")
    return response


async def tokens(data):
    response = await http("POST", endpoint("oauth") + "/token", data=data)
    value = response.json()
    if not value.get("access_token"):
        raise HTTPException(503, "INVALID_OAUTH_RESPONSE")
    value["expires_at"] = time.time() + int(value.get("expires_in", 3600))
    return value


def interval(value):
    for key in ("start", "end"):
        try:
            date = datetime.fromisoformat(value[key].replace("Z", "+00:00"))
            if not date.tzinfo:
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise HTTPException(400, "INVALID_CALENDAR_INTERVAL") from None
    if datetime.fromisoformat(value["start"].replace("Z", "+00:00")) >= datetime.fromisoformat(
        value["end"].replace("Z", "+00:00")
    ):
        raise HTTPException(400, "INVALID_CALENDAR_INTERVAL")


async def calendar_query(token, query):
    interval(query)
    response = await http(
        "GET",
        endpoint("calendar") + "/calendars/primary/events",
        headers={"Authorization": "Bearer " + token},
        params={
            "timeMin": query["start"],
            "timeMax": query["end"],
            "singleEvents": "true",
            "maxResults": 100,
        },
    )
    value = response.json()
    events = [
        {k: item.get(k) for k in ("id", "etag", "summary", "start", "end", "status", "updated")}
        for item in value.get("items", [])
        if item.get("status") != "cancelled"
    ]
    conflicts = []
    unassessed = False
    for i, first in enumerate(events):
        for second in events[i + 1 :]:
            a, b = first.get("start") or {}, first.get("end") or {}
            c, d = second.get("start") or {}, second.get("end") or {}
            # All-day dates use exclusive end. Mixed all-day/timed events remain
            # visible but aren't guessed as conflicts without calendar timezone.
            field = (
                "dateTime"
                if all(x.get("dateTime") for x in (a, b, c, d))
                else "date"
                if all(x.get("date") for x in (a, b, c, d))
                else None
            )
            if not field:
                unassessed = True
            if field:

                def parse(x):
                    return datetime.fromisoformat(x.replace("Z", "+00:00"))

                if parse(a[field]) < parse(d[field]) and parse(c[field]) < parse(b[field]):
                    conflicts.append({"first": first["id"], "second": second["id"]})
    return {
        "warnings": ["混合全天与定时事件未自动判定冲突，需人工核对"] if unassessed else [],
        "events": events,
        "conflicts": conflicts,
        "partial": bool(value.get("nextPageToken")),
        "provider": "TEST_FIXTURE" if fixture_mode() else "google",
    }


async def calendar_event(token, event_id):
    return (
        await http(
            "GET",
            endpoint("calendar") + "/calendars/primary/events/" + quote(event_id, safe=""),
            headers={"Authorization": "Bearer " + token},
        )
    ).json()


async def gmail_query(token, query):
    response = await http(
        "GET",
        endpoint("gmail") + "/users/me/messages",
        headers={"Authorization": "Bearer " + token},
        params={"q": query.get("query", "in:inbox"), "maxResults": 10},
    )
    result = []
    for item in response.json().get("messages", [])[:10]:
        value = (
            await http(
                "GET",
                endpoint("gmail") + "/users/me/messages/" + quote(item["id"], safe=""),
                headers={"Authorization": "Bearer " + token},
                params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Message-ID"]},
            )
        ).json()
        result.append(
            {
                "id": value["id"],
                "threadId": value.get("threadId"),
                "historyId": value.get("historyId"),
                "labelIds": value.get("labelIds", []),
                "headers": value.get("payload", {}).get("headers", []),
            }
        )
    return {
        "messages": result,
        "partial": bool(response.json().get("nextPageToken")),
        "provider": "TEST_FIXTURE" if fixture_mode() else "google",
    }


async def write(token, action_id, request):
    if request["kind"] == "calendar.update":
        data = request["payload"]
        response = await http(
            "PATCH",
            endpoint("calendar") + "/calendars/primary/events/" + quote(data["event_id"], safe=""),
            headers={"Authorization": "Bearer " + token, "If-Match": request["before"]["etag"]},
            json={"start": {"dateTime": data["start"]}, "end": {"dateTime": data["end"]}},
        )
        value = response.json()
        verified = await calendar_event(token, data["event_id"])
        if (
            not value.get("etag")
            or verified.get("etag") != value["etag"]
            or any(verified.get(k) != value.get(k) for k in ("start", "end"))
        ):
            raise HTTPException(409, "PROVIDER_UNKNOWN")
        return {
            "provider_receipt": value["id"],
            "verified": True,
            "etag": value["etag"],
            "provider": "TEST_FIXTURE" if fixture_mode() else "google",
        }
    data = request["payload"]
    message = EmailMessage()
    message["To"] = data["to"]
    message["Subject"] = data["subject"]
    message["Message-ID"] = f"<adex-{action_id}@adex.local>"
    message.set_content(data["text"])
    value = (
        await http(
            "POST",
            endpoint("gmail") + "/users/me/messages/send",
            headers={"Authorization": "Bearer " + token},
            json={"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()},
        )
    ).json()
    if not value.get("id"):
        raise HTTPException(409, "PROVIDER_UNKNOWN")
    return {
        "provider_receipt": value["id"],
        "verified": True,
        "provider": "TEST_FIXTURE" if fixture_mode() else "google",
    }
