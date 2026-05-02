"""Pydantic request/response models — the public API contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---------- Chat ----------


class ChatRequest(BaseModel):
    """Inbound chat message from the citizen."""

    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., min_length=4, max_length=128)
    locale: str = Field(default="en", min_length=2, max_length=8)
    location: str | None = Field(default=None, max_length=200)

    @field_validator("message")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be blank")
        return v


class ToolCall(BaseModel):
    name: str
    arguments: dict
    result_summary: str | None = None


class ChatResponse(BaseModel):
    reply: str
    locale: str
    tools_used: list[ToolCall] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    safety_filtered: bool = False


# ---------- Polling locations ----------


class PollingPlaceQuery(BaseModel):
    address: str = Field(..., min_length=3, max_length=200)
    radius_m: int = Field(default=5000, ge=500, le=50000)


class PollingPlace(BaseModel):
    name: str
    address: str
    distance_m: float | None = None
    rating: float | None = None
    place_id: str | None = None
    map_url: str | None = None


class PollingPlaceResponse(BaseModel):
    query: str
    results: list[PollingPlace]


# ---------- Calendar (ICS) reminders ----------


class ReminderRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(default="", max_length=2000)
    start: datetime
    duration_minutes: int = Field(default=60, ge=5, le=24 * 60)
    location: str | None = Field(default=None, max_length=200)


# ---------- Educational videos ----------


class VideoQuery(BaseModel):
    topic: str = Field(..., min_length=2, max_length=120)
    locale: str = Field(default="en", min_length=2, max_length=8)
    max_results: int = Field(default=5, ge=1, le=10)


class VideoItem(BaseModel):
    title: str
    channel: str
    url: str
    published_at: str | None = None
    description: str | None = None


class VideoResponse(BaseModel):
    topic: str
    items: list[VideoItem]


# ---------- Translation ----------


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    target: str = Field(..., min_length=2, max_length=8)
    source: str | None = Field(default=None, max_length=8)


class TranslateResponse(BaseModel):
    text: str
    target: str
    source_detected: str | None = None


# ---------- Generic ----------


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    env: str


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
