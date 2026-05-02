"""FastAPI application — entry point.

This module wires:

* CORS, gzip, request logging, structured error handling
* per-IP rate-limiting (slowapi)
* dependency-injected service clients (Gemini, Maps, YouTube, Translate)
* REST endpoints + a lightweight static SPA at `/`

Note: we deliberately do *not* enable `from __future__ import annotations`
here, because FastAPI introspects type hints at runtime to build the
request-body parsers. PEP 563 stringified annotations break that for
forward references like `ChatRequest`.
"""

import logging
import os
import sys
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
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("election_assistant")


# ---------- App lifespan + DI ----------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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
    description="Non-partisan, multilingual assistant powered by Google services.",
    version=__version__,
    lifespan=lifespan,
    default_response_class=JSONResponse,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _settings_dep() -> Settings:
    return get_settings()


# ---------- Middleware ----------

settings_boot = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_boot.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
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
async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = _CSP
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    # HSTS is meaningful only over HTTPS; Cloud Run terminates TLS upstream.
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
    return response


@app.exception_handler(ServiceUnavailable)
async def _service_unavailable(_: Request, exc: ServiceUnavailable) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorResponse(error=f"{exc.service} unavailable", detail=exc.detail).model_dump(),
    )


# ---------- Routes ----------


@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
async def health(settings: Settings = Depends(_settings_dep)) -> HealthResponse:
    return HealthResponse(version=__version__, env=settings.app_env)


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["chat"],
)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
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


@app.post("/api/polling-places", response_model=PollingPlaceResponse, tags=["tools"])
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def polling_places(request: Request, body: PollingPlaceQuery) -> PollingPlaceResponse:
    formatted, places = await app.state.maps.find_polling_places(body.address, body.radius_m)
    return PollingPlaceResponse(query=formatted, results=places)


@app.post("/api/videos", response_model=VideoResponse, tags=["tools"])
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def videos(request: Request, body: VideoQuery) -> VideoResponse:
    items = await app.state.youtube.search(
        body.topic, locale=body.locale, max_results=body.max_results
    )
    return VideoResponse(topic=body.topic, items=items)


@app.post("/api/translate", response_model=TranslateResponse, tags=["tools"])
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def translate(request: Request, body: TranslateRequest) -> TranslateResponse:
    text, detected = await app.state.translate.translate(body.text, body.target, body.source)
    return TranslateResponse(text=text, target=body.target, source_detected=detected)


@app.post("/api/reminder.ics", tags=["tools"])
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def reminder(request: Request, body: ReminderRequest):
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


# ---------- Static SPA ----------

_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))

    @app.get("/robots.txt", include_in_schema=False)
    async def robots() -> FileResponse:
        # Conventional location at site root; crawlers won't look in /static/.
        return FileResponse(os.path.join(_STATIC_DIR, "robots.txt"), media_type="text/plain")

    @app.get("/manifest.json", include_in_schema=False)
    async def manifest() -> FileResponse:
        return FileResponse(
            os.path.join(_STATIC_DIR, "manifest.json"),
            media_type="application/manifest+json",
        )


# ---------- 404 fallback ----------


@app.exception_handler(404)
async def _not_found(_: Request, __: HTTPException) -> JSONResponse:  # type: ignore[override]
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(error="not_found", detail="Resource not found").model_dump(),
    )
