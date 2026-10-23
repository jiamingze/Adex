"""Closed tool registry with owner-observation binding, independent of model prose."""

from datetime import datetime, time
from typing import Literal
from zoneinfo import ZoneInfo
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from adex_agent.routing.schedule import ScheduleDraft
from adex_agent.routing.productivity import TodoDraft
from adex_agent.routing.notification import NotificationCondition


class SchedulePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    instruction: str | None = Field(default=None, min_length=1, max_length=16000)
    kind: Literal["ONCE", "DAILY", "INTERVAL"] | None = None
    timezone: str | None = None
    local_time: str | None = None
    first_fire_at: str | None = None
    interval_seconds: int | None = Field(default=None, ge=60, le=31536000)
    status: Literal["ACTIVE", "PAUSED", "CANCELLED"] | None = None
    notification_policy: Literal["EVERY_RUN", "CHANGES_ONLY", "CONDITION_MET"] | None = None
    notification_condition: NotificationCondition | None = None

    @model_validator(mode="after")
    def valid(self):
        if not self.model_fields_set or any(getattr(self, k) is None for k in self.model_fields_set):
            raise ValueError("Empty patch/null fields")
        if self.timezone:
            ZoneInfo(self.timezone)
        if self.local_time:
            time.fromisoformat(self.local_time)
        if (
            self.first_fire_at
            and datetime.fromisoformat(self.first_fire_at.replace("Z", "+00:00")).tzinfo is None
        ):
            raise ValueError("Offset required")
        if self.notification_policy == "CONDITION_MET" and not self.notification_condition:
            raise ValueError("Condition required")
        if self.notification_condition and self.notification_policy != "CONDITION_MET":
            raise ValueError("Conditional policy required")
        return self


class TodoPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=16000)
    important: bool | None = None
    urgent: bool | None = None
    due_at: str | None = None
    status: Literal["TODO", "DONE"] | None = None

    @model_validator(mode="after")
    def valid(self):
        if not self.model_fields_set or any(
            k != "due_at" and getattr(self, k) is None for k in self.model_fields_set
        ):
            raise ValueError("Empty patch/null fields")
        if self.due_at and datetime.fromisoformat(self.due_at.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("Offset required")
        return self


class ComputerStart(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    goal: str = Field(min_length=2, max_length=16000)
    app_name: str = Field(min_length=1, max_length=200)


class WorkflowStart(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    goal: str = Field(min_length=10, max_length=16000)
    acceptance: list[str] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def valid(self):
        if any(not c.strip() or len(c) > 500 for c in self.acceptance):
            raise ValueError("Invalid acceptance criterion")
        return self


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tool: Literal[
        "workflow.start",
        "computer.start",
        "none",
        "clarify",
        "schedule.create",
        "schedule.update",
        "schedule.list",
        "todo.create",
        "todo.update",
        "todo.list",
    ]
    target_id: str = ""
    arguments: dict = Field(default_factory=dict, max_length=16)
    message: str = Field(default="", max_length=600)


REGISTRY = {
    "computer.start": ComputerStart,
    "workflow.start": WorkflowStart,
    "schedule.create": ScheduleDraft,
    "schedule.update": SchedulePatch,
    "todo.create": TodoDraft,
    "todo.update": TodoPatch,
}


def validate_action(raw, snapshot):
    call = ToolCall.model_validate(raw)
    if call.tool in {"none", "clarify", "schedule.list", "todo.list"}:
        if call.target_id or call.arguments:
            raise ValueError("Read/final response cannot include mutation arguments")
        if call.tool == "clarify" and not call.message.strip():
            raise ValueError("Clarification required")
        return call.model_dump()
    args = REGISTRY[call.tool].model_validate(call.arguments).model_dump(exclude_unset=True)
    if call.tool.endswith(".update"):
        UUID(call.target_id)
        rows = snapshot["schedules" if call.tool.startswith("schedule") else "todos"]
        row = next((r for r in rows if str(r["id"]) == call.target_id), None)
        if row is None or (
            call.tool.startswith("schedule") and row.get("status") not in {"ACTIVE", "PAUSED"}
        ):
            raise ValueError("Target is not an editable observed record")
        if call.tool == "schedule.update":
            kind = args.get("kind", row.get("kind"))
            required = {"DAILY": "local_time", "INTERVAL": "interval_seconds", "ONCE": "first_fire_at"}
            if "kind" in args and args["kind"] != row.get("kind") and required[kind] not in args:
                raise ValueError("Frequency change requires its timing field")
            if "local_time" in args and kind != "DAILY":
                raise ValueError("Local time requires DAILY")
            if "interval_seconds" in args and kind != "INTERVAL":
                raise ValueError("Interval requires INTERVAL")
        same = [r for r in rows if r.get("title") == row.get("title")]
        if len(same) > 1 and call.target_id not in snapshot["request"]:
            return {
                "tool": "clarify",
                "message": "找到多条同名事项，请提供任务 ID 或更具体的信息，避免改错。",
                "arguments": {},
                "target_id": "",
            }
        args["revision"] = int(row["revision"])
    elif call.target_id:
        raise ValueError("Create cannot select a target ID")
    return {**call.model_dump(), "arguments": args}
