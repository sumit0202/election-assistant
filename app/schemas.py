"""Pydantic request/response models — the public API contract.

Every model carries a docstring and the most important fields carry an
``examples`` list so FastAPI emits a richer OpenAPI document. Field-level
constraints (``min_length``, ``ge``, ``le``) double as input validation
*and* as defense-in-depth against pathological payloads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Locale codes the UI can submit. Keep in sync with the front-end picker.
SUPPORTED_LOCALES: tuple[str, ...] = ("en", "hi", "ta", "bn", "mr", "te")


# ---------- Chat ----------


class ChatRequest(BaseModel):
    """Inbound chat message from the citizen.

    Validation:
        - ``message`` must be 1..2000 chars after stripping whitespace.
        - ``session_id`` is opaque to the server but kept reasonably bounded.
        - ``locale`` must be one of :data:`SUPPORTED_LOCALES`.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "How do I register as a first-time voter?",
                    "session_id": "abcd1234",
                    "locale": "en",
                    "location": "Bengaluru",
                }
            ]
        }
    )

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's question. Sanitised + PII-redacted before LLM.",
    )
    session_id: str = Field(
        ...,
        min_length=4,
        max_length=128,
        description="Opaque client-generated session identifier.",
    )
    locale: str = Field(
        default="en",
        min_length=2,
        max_length=8,
        description="Reply language. Must be one of: en, hi, ta, bn, mr, te.",
    )
    location: str | None = Field(
        default=None,
        max_length=200,
        description="Optional user-supplied city or address (for tool routing).",
    )

    @field_validator("message")
    @classmethod
    def _strip(cls, v: str) -> str:
        """Trim whitespace and reject blank messages."""

        v = v.strip()
        if not v:
            raise ValueError("message must not be blank")
        return v

    @field_validator("locale")
    @classmethod
    def _check_locale(cls, v: str) -> str:
        """Reject locales we don't support — fail fast at the API edge."""

        v = v.lower()
        if v not in SUPPORTED_LOCALES:
            raise ValueError(f"locale must be one of {SUPPORTED_LOCALES}")
        return v


class ToolCall(BaseModel):
    """Metadata about one tool the agent invoked while answering."""

    name: str = Field(..., description="Canonical tool name, e.g. 'polling_locations'.")
    arguments: dict = Field(default_factory=dict, description="Arguments passed to the tool.")
    result_summary: str | None = Field(
        default=None, description="Short, human-readable summary of the tool's result."
    )


class ChatResponse(BaseModel):
    """Outgoing chat reply, including any tools used and citations."""

    reply: str = Field(..., description="Markdown-formatted assistant reply.")
    locale: str = Field(..., description="Reply language code.")
    tools_used: list[ToolCall] = Field(
        default_factory=list, description="Tools the agent invoked, in order."
    )
    citations: list[str] = Field(
        default_factory=list, description="Inline citation markers referenced in the reply."
    )
    safety_filtered: bool = Field(
        default=False,
        description="True if a safety guard rewrote or replaced the reply.",
    )


# ---------- Polling locations ----------


class PollingPlaceQuery(BaseModel):
    """Polling-venue search request."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"address": "MG Road, Bengaluru", "radius_m": 5000}]}
    )

    address: str = Field(
        ..., min_length=3, max_length=200, description="Free-text address or city."
    )
    radius_m: int = Field(
        default=5000,
        ge=500,
        le=50000,
        description="Search radius in metres (500..50000).",
    )


class PollingPlace(BaseModel):
    """A single polling-style venue (school, hall, community centre)."""

    name: str = Field(..., description="Venue name as returned by Places API.")
    address: str = Field(..., description="Formatted address.")
    distance_m: float | None = Field(
        default=None, description="Straight-line distance in metres from the geocoded address."
    )
    rating: float | None = Field(default=None, description="Google Places rating (0..5).")
    place_id: str | None = Field(default=None, description="Stable Places API identifier.")
    map_url: str | None = Field(default=None, description="Google Maps deep link.")


class PollingPlaceResponse(BaseModel):
    """Response wrapper for a polling-venue search."""

    query: str = Field(..., description="Echoed back, possibly normalised, query.")
    results: list[PollingPlace] = Field(default_factory=list)


# ---------- Calendar (ICS) reminders ----------


class ReminderRequest(BaseModel):
    """Calendar reminder payload — generates an RFC 5545 .ics file."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Maharashtra polling day",
                    "description": "Carry voter ID. Polling 7 AM - 6 PM.",
                    "start": "2026-11-05T09:00:00+05:30",
                    "duration_minutes": 60,
                    "location": "Booth #123",
                }
            ]
        }
    )

    title: str = Field(..., min_length=3, max_length=200, description="Calendar event title.")
    description: str = Field(default="", max_length=2000, description="Body text for the event.")
    start: datetime = Field(..., description="ISO-8601 start time (timezone-aware preferred).")
    duration_minutes: int = Field(
        default=60, ge=5, le=24 * 60, description="Event duration in minutes (5..1440)."
    )
    location: str | None = Field(default=None, max_length=200)


# ---------- Educational videos ----------


class VideoQuery(BaseModel):
    """YouTube explainer-search request."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"topic": "EVM and VVPAT", "locale": "en", "max_results": 5}]
        }
    )

    topic: str = Field(..., min_length=2, max_length=120)
    locale: str = Field(default="en", min_length=2, max_length=8)
    max_results: int = Field(default=5, ge=1, le=10)


class VideoItem(BaseModel):
    """A single YouTube video result."""

    title: str
    channel: str
    url: str
    published_at: str | None = None
    description: str | None = Field(default=None, max_length=300)


class VideoResponse(BaseModel):
    """Wrapper for ranked video results."""

    topic: str
    items: list[VideoItem] = Field(default_factory=list)


# ---------- Translation ----------


class TranslateRequest(BaseModel):
    """Cloud Translation v3 request payload."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"text": "Hello", "target": "hi", "source": "en"}]}
    )

    text: str = Field(..., min_length=1, max_length=4000)
    target: str = Field(..., min_length=2, max_length=8, description="BCP-47 target language code.")
    source: str | None = Field(default=None, max_length=8)


class TranslateResponse(BaseModel):
    """Translation result, plus the auto-detected source language."""

    text: str
    target: str
    source_detected: str | None = None


# ---------- Generic ----------


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: Literal["ok"] = "ok"
    version: str = Field(..., description="Semantic-version string of the running build.")
    env: str = Field(..., description="Environment label (e.g. 'dev', 'prod').")


class ErrorResponse(BaseModel):
    """Uniform error envelope used by all non-2xx responses."""

    error: str = Field(..., description="Machine-readable error code.")
    detail: str | None = Field(default=None, description="Human-readable explanation.")
