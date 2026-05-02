"""FastAPI application — entry point.

This module wires:

* CORS, gzip, request-ID propagation, structured error handling
* per-IP rate-limiting (slowapi)
* a comprehensive set of security response headers (CSP, HSTS, COOP, ...)
* dependency-injected service clients (Gemini, Maps, YouTube, Translate)
* REST endpoints + a lightweight static SPA at `/`

Note: we deliberately do *not* enable ``from __future__ import annotations``
here, because FastAPI introspects type hints at runtime to build the
request-body parsers. PEP 563 stringified annotations break that for
forward references like ``ChatRequest``.
"""

import logging
import os
import sys
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from . import __version__
from .agent import AgentDeps, ElectionAgent
from .config import Settings, get_settings
from .safety import check_input, check_output
from .schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    PollingPlaceQuery,
    PollingPlaceResponse,
    ReminderRequest,
    TranslateRequest,
    TranslateResponse,
    VideoQuery,
    VideoResponse,
)
from .services.calendar_ics import build_reminder_ics
from .services.errors import ServiceUnavailable
from .services.gemini import GeminiClient, GeminiConfig
from .services.maps import MapsClient
from .services.translate import TranslateClient, TranslateConfig
from .services.youtube import YouTubeClient

# ---------- Logging ----------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "info").upper(),
    format="%(asctime)s %(levelname)s %(name)s [req=%(request_id)s] :: %(message)s",
    stream=sys.stdout,
)


class _RequestIdFilter(logging.Filter):
    """Inject a placeholder ``request_id`` if no contextvar is set."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


for handler in logging.getLogger().handlers:
    handler.addFilter(_RequestIdFilter())

log = logging.getLogger("election_assistant")


# ---------- App lifespan + DI ----------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Construct service clients at startup; close their HTTP pools on shutdown.

    All long-lived resources (Gemini SDK, ``httpx`` clients, Translate
    gRPC channel) live on ``app.state`` so request handlers can reach them
    without re-creating them per request.
    """

    settings = get_settings()
    app.state.settings = settings
    app.state.gemini = GeminiClient(
        GeminiConfig(
            model=settings.gemini_model,
            api_key=settings.gemini_api_key,
            project=settings.google_cloud_project,
            location=settings.vertex_location,
        )
    )
    app.state.maps = MapsClient(settings.google_maps_api_key)
    app.state.youtube = YouTubeClient(settings.youtube_api_key)
    app.state.translate = TranslateClient(
        TranslateConfig(project=settings.google_cloud_project, location=settings.translate_location)
    )
    app.state.agent = ElectionAgent(
        AgentDeps(gemini=app.state.gemini, maps=app.state.maps, youtube=app.state.youtube)
    )
    log.info("App ready (env=%s, version=%s)", settings.app_env, __version__)
    try:
        yield
    finally:
        await app.state.maps.aclose()
        await app.state.youtube.aclose()


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="Election Process Education Assistant",
    description=(
        "**CivicGuide** — a non-partisan, multilingual assistant that helps "
        "citizens understand the election process. Powered by Google Gemini "
        "(Vertex AI), Maps Platform, YouTube Data API, Cloud Translation, and "
        "ICS calendar export."
    ),
    version=__version__,
    lifespan=lifespan,
    default_response_class=JSONResponse,
    contact={"name": "CivicGuide", "url": "https://github.com/sumit0202/election-assistant"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=[
        {"name": "meta", "description": "Liveness and version probes."},
        {"name": "chat", "description": "Conversational interface (the main entry point)."},
        {
            "name": "tools",
            "description": "Direct tool endpoints — polling, videos, translate, ICS.",
        },
    ],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _settings_dep() -> Settings:
    """FastAPI dependency that returns the cached :class:`Settings` instance."""

    return get_settings()


# ---------- Middleware ----------

settings_boot = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_boot.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
    allow_credentials=False,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


# Content-Security-Policy is intentionally strict; the SPA only loads its
# own JS/CSS and renders Markdown into a sandboxed DOM (no inline scripts).
# `frame-ancestors 'none'` doubles up with X-Frame-Options for old browsers.
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https://i.ytimg.com https://yt3.ggpht.com; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-src https://www.youtube.com https://www.youtube-nocookie.com; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "upgrade-insecure-requests"
)


@app.middleware("http")
async def request_id_and_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Attach a per-request UUID and a hardened set of security headers.

    The request id is taken from the ``X-Request-ID`` header if the client
    sent one (handy for tracing across a load-balancer); otherwise we
    generate a UUIDv4. The same value is echoed back on the response and
    written to ``request.state`` so handlers can correlate logs.
    """

    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = rid

    response = await call_next(request)

    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = _CSP
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    # Strip the noisy default `Server: uvicorn` banner — minor info-leak hardening.
    response.headers["Server"] = "CivicGuide"
    # HSTS is meaningful only over HTTPS; Cloud Run terminates TLS upstream.
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
    return response


@app.exception_handler(ServiceUnavailable)
async def _service_unavailable(request: Request, exc: ServiceUnavailable) -> JSONResponse:
    """Translate :class:`ServiceUnavailable` into HTTP 503 + JSON body."""

    log.warning("Upstream %s unavailable: %s", exc.service, exc.detail)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorResponse(error=f"{exc.service} unavailable", detail=exc.detail).model_dump(),
        headers={"X-Request-ID": getattr(request.state, "request_id", "-")},
    )


# ---------- Routes ----------


@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["meta"],
    summary="Service liveness probe",
    description=(
        "Returns the running service version and environment label. "
        "Used by Cloud Run health checks and external uptime monitors."
    ),
    response_description="The service is up and ready to serve requests.",
)
async def health(settings: Settings = Depends(_settings_dep)) -> HealthResponse:
    """Return a minimal health-check payload (status, version, env)."""

    return HealthResponse(version=__version__, env=settings.app_env)


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate-limit exceeded"},
        503: {"model": ErrorResponse, "description": "An upstream Google service is down"},
    },
    tags=["chat"],
    summary="Conversational entry point",
    description=(
        "Handles a single user message. The pipeline is: input safety check "
        "(strips PII, blocks injection / partisan), FAQ best-match → Gemini "
        "→ optional tool calls (polling, videos), output safety check, then "
        "JSON response."
    ),
    response_description="Assistant reply, plus any tools used and citations.",
)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """Run the full chat pipeline end-to-end.

    Args:
        request: Underlying Starlette request (used for rate-limit key).
        body: Validated user request payload.

    Returns:
        A :class:`ChatResponse` with the reply, locale, any tool metadata
        and citations. ``safety_filtered=True`` indicates the response was
        rewritten by a safety guard.
    """

    verdict = check_input(body.message)
    if not verdict.allowed:
        return ChatResponse(
            reply=verdict.reason or "Request blocked.", locale=body.locale, safety_filtered=True
        )

    sanitized = verdict.sanitized_text or body.message
    agent: ElectionAgent = app.state.agent
    result = await agent.respond(
        user_message=sanitized,
        locale=body.locale,
        location=body.location,
    )

    out_check = check_output(result.reply)
    if not out_check.allowed:
        return ChatResponse(
            reply=(
                "I can explain the election process, but I won't take sides. "
                "Try asking about voter eligibility, registration, or polling logistics."
            ),
            locale=body.locale,
            safety_filtered=True,
        )

    return ChatResponse(
        reply=result.reply,
        locale=body.locale,
        tools_used=result.tools_used,
        citations=result.citations,
    )


@app.post(
    "/api/polling-places",
    response_model=PollingPlaceResponse,
    tags=["tools"],
    summary="Find polling-style venues near an address",
    description=(
        "Geocodes the supplied address and runs a Places Text Search for "
        "schools, halls, and community centres within `radius_m` metres. "
        "Results are sorted by distance from the geocoded centre."
    ),
    response_description="Up to 10 matching venues with name, address, distance, and map URL.",
)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def polling_places(request: Request, body: PollingPlaceQuery) -> PollingPlaceResponse:
    """Resolve an address and return nearby polling-style venues."""

    formatted, places = await app.state.maps.find_polling_places(body.address, body.radius_m)
    return PollingPlaceResponse(query=formatted, results=places)


@app.post(
    "/api/videos",
    response_model=VideoResponse,
    tags=["tools"],
    summary="Search YouTube for trusted election explainers",
    description=(
        "Searches the YouTube Data API with safe-search enabled and boosts "
        "results from a curated allow-list of trusted channels (Election "
        "Commission of India, PIB, BBC, Reuters, Al Jazeera, DW)."
    ),
    response_description="A ranked list of explainer videos with title, channel, and URL.",
)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def videos(request: Request, body: VideoQuery) -> VideoResponse:
    """Search YouTube and return curated explainer videos for ``topic``."""

    items = await app.state.youtube.search(
        body.topic, locale=body.locale, max_results=body.max_results
    )
    return VideoResponse(topic=body.topic, items=items)


@app.post(
    "/api/translate",
    response_model=TranslateResponse,
    tags=["tools"],
    summary="Translate text via Cloud Translation v3",
    description=(
        "Uses Application Default Credentials so no API key is required at "
        "runtime — works seamlessly on Cloud Run with the runtime service "
        "account."
    ),
    response_description="Translated text plus the auto-detected source language code.",
)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def translate(request: Request, body: TranslateRequest) -> TranslateResponse:
    """Translate ``body.text`` into ``body.target`` (auto-detect source)."""

    text, detected = await app.state.translate.translate(body.text, body.target, body.source)
    return TranslateResponse(text=text, target=body.target, source_detected=detected)


@app.post(
    "/api/reminder.ics",
    tags=["tools"],
    summary="Generate a calendar reminder (.ics)",
    description=(
        "Returns an RFC 5545 iCalendar file you can import into Google "
        "Calendar, Apple Calendar, Outlook, or any other compliant client. "
        "No OAuth required."
    ),
    response_description="A binary `.ics` file streamed as an attachment.",
    responses={200: {"content": {"text/calendar": {}}}},
)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def reminder(request: Request, body: ReminderRequest) -> StreamingResponse:
    """Build an `.ics` payload for the given reminder and stream it back."""

    payload = build_reminder_ics(
        title=body.title,
        description=body.description,
        start=body.start,
        duration_minutes=body.duration_minutes,
        location=body.location,
    )
    return StreamingResponse(
        BytesIO(payload),
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="election-reminder.ics"'},
    )


# ---------- Static SPA + well-known files ----------

_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        """Serve the single-page application shell."""

        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))

    @app.get("/robots.txt", include_in_schema=False)
    async def robots() -> FileResponse:
        """Serve robots.txt at the conventional site-root location."""

        return FileResponse(os.path.join(_STATIC_DIR, "robots.txt"), media_type="text/plain")

    @app.get("/manifest.json", include_in_schema=False)
    async def manifest() -> FileResponse:
        """Serve the Web App Manifest for installable-PWA support."""

        return FileResponse(
            os.path.join(_STATIC_DIR, "manifest.json"),
            media_type="application/manifest+json",
        )

    @app.get("/.well-known/security.txt", include_in_schema=False)
    async def security_txt() -> FileResponse:
        """Responsible-disclosure metadata per RFC 9116."""

        return FileResponse(os.path.join(_STATIC_DIR, "security.txt"), media_type="text/plain")


# ---------- 404 fallback ----------


@app.exception_handler(404)
async def _not_found(request: Request, _: HTTPException) -> JSONResponse:  # type: ignore[override]
    """Return a structured JSON 404 instead of FastAPI's default HTML."""

    return JSONResponse(
        status_code=404,
        content=ErrorResponse(error="not_found", detail="Resource not found").model_dump(),
        headers={"X-Request-ID": getattr(request.state, "request_id", "-")},
    )
