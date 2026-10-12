"""Validated connector/action contracts independent of HTTP composition."""

from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OAuthStart(Strict):
    service: Literal["calendar", "gmail"]
    access: Literal["read", "write", "send"]
    session_binding: str = Field(pattern=r"^[a-f0-9]{64}$")


class OAuthCallback(Strict):
    state: str = Field(min_length=20, max_length=180)
    code: str = Field(min_length=1, max_length=4096)
    session_binding: str = Field(pattern=r"^[a-f0-9]{64}$")


class Query(Strict):
    query: str = Field(default="in:inbox", max_length=500)
    start: str | None = Field(default=None, max_length=60)
    end: str | None = Field(default=None, max_length=60)


class ActionPayload(Strict):
    event_id: str | None = Field(default=None, max_length=180)
    start: str | None = Field(default=None, max_length=60)
    end: str | None = Field(default=None, max_length=60)
    to: str | None = Field(default=None, max_length=320)
    subject: str | None = Field(default=None, max_length=300)
    text: str | None = Field(default=None, max_length=16000)


class ActionDraft(Strict):
    connection_id: UUID
    origin_conversation_id: UUID
    kind: Literal["calendar.update", "gmail.send"]
    payload: ActionPayload

    @model_validator(mode="after")
    def valid_payload(self):
        import re

        data = self.payload.model_dump(exclude_none=True)
        required = (
            {"event_id", "start", "end"} if self.kind == "calendar.update" else {"to", "subject", "text"}
        )
        if set(data) != required or any(not data[k] for k in required):
            raise ValueError("INVALID_ACTION_PAYLOAD")
        if self.kind == "gmail.send" and (
            not re.fullmatch(r"[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+", data["to"])
            or any("\r" in data[k] or "\n" in data[k] for k in ("to", "subject"))
        ):
            raise ValueError("INVALID_EMAIL_HEADERS")
        return self


class Decision(Strict):
    request_hash: str = Field(default="", max_length=64)


class Execution(Strict):
    approval_id: UUID
    run_id: UUID
    epoch: int = Field(ge=0)
    attempt_id: UUID


class SyncExecution(Strict):
    connection_id: UUID
    run_id: UUID
    epoch: int = Field(ge=0)
    attempt_id: UUID
    query: Query
