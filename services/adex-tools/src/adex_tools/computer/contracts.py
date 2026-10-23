"""Closed native capability vocabulary; no script, shell or global coordinate input."""

from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ComputerExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    epoch: int = Field(ge=1)
    attempt_id: UUID
    app_name: str = Field(min_length=1, max_length=200)


class ComputerAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["press", "set_value"]
    element_id: str = Field(min_length=1, max_length=100)
    text: str = Field(default="", max_length=4000)


class ComputerStep(ComputerExecution):
    observation_id: UUID
    command_key: str = Field(min_length=1, max_length=100)
    step: ComputerAction
    approval_id: UUID | None = None
