"""Validated transport contracts; execution code receives explicit data."""

from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invocation_key: str = Field(max_length=180)
    owner_id: UUID
    conversation_id: UUID
    turn_id: UUID
    context: dict
    web_search: bool = False
    model: Literal["", "qwen3.8-max", "minimax"] = ""


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    owner_id: UUID
    conversation_id: UUID
    instruction: str = Field(min_length=1, max_length=2000)
    timezone: str = Field(max_length=80)
    current_time: str
