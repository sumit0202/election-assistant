"""Pydantic request/response models — the public API contract."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------- Chat ----------


class ChatRequest(BaseModel):
    """Inbound chat message from the citizen."""

    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., min_length=4, max_length=128)
    locale: str = Field(default="en", min_length=2, max_length=8)
    location: Optional[str] = Field(default=None, max_length=200)

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
    result_summary: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    locale: str
    tools_used: List[ToolCall] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    safety_filtered: bool = False


# ---------- Polling locations ----------


class PollingPlaceQuery(BaseModel):
    address: str = Field(..., min_length=3, max_length=200)
    radius_m: int = Field(default=5000, ge=500, le=50000)


class PollingPlace(BaseModel):
    name: str
    address: str
    distance_m: Optional[float] = None
    rating: Optional[float] = None
    place_id: Optional[str] = None
    map_url: Optional[str] = None


class PollingPlaceResponse(BaseModel):
    query: str
    results: List[PollingPlace]


# ---------- Calendar (ICS) reminders ----------


class ReminderRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(default="", max_length=2000)
    start: datetime
    duration_minutes: int = Field(default=60, ge=5, le=24 * 60)
    location: Optional[str] = Field(default=None, max_length=200)


# ---------- Educational videos ----------


class VideoQuery(BaseModel):
    topic: str = Field(..., min_length=2, max_length=120)
    locale: str = Field(default="en", min_length=2, max_length=8)
    max_results: int = Field(default=5, ge=1, le=10)


class VideoItem(BaseModel):
    title: str
    channel: str
    url: str
    published_at: Optional[str] = None
    description: Optional[str] = None


class VideoResponse(BaseModel):
    topic: str
    items: List[VideoItem]


# ---------- Translation ----------


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    target: str = Field(..., min_length=2, max_length=8)
    source: Optional[str] = Field(default=None, max_length=8)


class TranslateResponse(BaseModel):
    text: str
    target: str
    source_detected: Optional[str] = None


# ---------- Generic ----------


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    env: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
