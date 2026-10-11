"""Validated transport contracts; execution code receives explicit data."""

from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class Search(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=300)


class Creative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    prompt: str = Field(min_length=1, max_length=16000)
    request_key: str = Field(min_length=1, max_length=180)
    provider: str = "mock"
    rights_confirmed: bool = False
    input_refs: list[UUID] = Field(default_factory=list, max_length=3)
    params: dict = Field(default_factory=dict)
    run_id: UUID | None = None
    epoch: int | None = None
    attempt_id: UUID | None = None


class CalendarRequest(BaseModel):
    origin_conversation_id: UUID | None = None
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    start: str = Field(max_length=60)
    end: str = Field(max_length=60)


class FileExtract(BaseModel):
    file_id: UUID


class GameSource(BaseModel):
    source: str = Field(min_length=1, max_length=128000)


class TextArtifact(BaseModel):
    kind: str
    source: str = Field(min_length=1, max_length=128000)
    request_key: str = Field(min_length=1, max_length=180)


class TravelRequest(BaseModel):
    city: str = Field(min_length=1, max_length=100)
    start: str = Field(max_length=10)
    end: str = Field(max_length=10)


class VisionRequest(BaseModel):
    file_id: UUID
    prompt: str = Field(min_length=1, max_length=2000)


class CalendarExecution(BaseModel):
    approval_id: UUID
    run_id: UUID
    epoch: int
    attempt_id: UUID


class WeatherRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class BrowserRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2000)
    query: str = Field(default="", max_length=300)
