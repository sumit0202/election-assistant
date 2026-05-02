"""Gemini wrapper supporting both AI Studio and Vertex AI backends.

Defaults to **Vertex AI** when `GOOGLE_CLOUD_PROJECT` is set — this is the
right choice on Cloud Run, where Application Default Credentials are
automatically available and Workspace org policies often block the
consumer `generativelanguage.googleapis.com` API.

Falls back to the AI Studio API (`google-generativeai`) when only a
`GEMINI_API_KEY` is provided — handy for local dev where ADC isn't set up.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from .errors import ServiceUnavailable

log = logging.getLogger(__name__)

# Vertex AI — preferred. Loaded lazily so import errors don't break boot.
try:
    import vertexai  # type: ignore[import-not-found]
    from vertexai.generative_models import (  # type: ignore[import-not-found]
        GenerativeModel as VertexGenerativeModel,
        GenerationConfig as VertexGenerationConfig,
        HarmCategory as VertexHarmCategory,
        HarmBlockThreshold as VertexHarmBlockThreshold,
    )
except Exception:  # pragma: no cover - optional dep
    vertexai = None  # type: ignore[assignment]
    VertexGenerativeModel = None  # type: ignore[assignment]

# AI Studio — fallback for local dev with an API key.
try:
    import google.generativeai as genai  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    genai = None  # type: ignore[assignment]


@dataclass
class GeminiConfig:
    """Either (project + location) for Vertex, or api_key for AI Studio."""

    model: str
    api_key: str = ""
    project: str = ""
    location: str = "us-central1"


class GeminiClient:
    """Backend-agnostic Gemini facade.

    Chooses Vertex AI when a project is configured (recommended on GCP),
    otherwise falls back to the AI Studio SDK.
    """

    def __init__(self, config: GeminiConfig) -> None:
        self._config = config
        self._backend: str | None = None
        self._initialized = False

    # ------------------------------------------------------------------
    # Backend setup
    # ------------------------------------------------------------------

    def _ensure_ready(self) -> None:
        if self._initialized:
            return

        if self._config.project:
            self._init_vertex()
        elif self._config.api_key:
            self._init_aistudio()
        else:
            raise ServiceUnavailable(
                "Gemini",
                "neither GOOGLE_CLOUD_PROJECT nor GEMINI_API_KEY is configured",
            )

        self._initialized = True

    def _init_vertex(self) -> None:
        if vertexai is None:
            raise ServiceUnavailable("Gemini", "google-cloud-aiplatform not installed")
        try:
            vertexai.init(
                project=self._config.project,
                location=self._config.location,
            )
        except Exception as exc:  # pragma: no cover
            raise ServiceUnavailable("Gemini", f"vertexai.init failed: {exc}") from exc
        self._backend = "vertex"
        log.info("Gemini backend = Vertex AI (project=%s, location=%s)",
                 self._config.project, self._config.location)

    def _init_aistudio(self) -> None:
        if genai is None:
            raise ServiceUnavailable("Gemini", "google-generativeai not installed")
        genai.configure(api_key=self._config.api_key)
        self._backend = "aistudio"
        log.info("Gemini backend = AI Studio")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: Iterable[dict[str, Any]] = (),
        temperature: float = 0.4,
    ) -> str:
        """Generate a single text reply from the active backend."""
        self._ensure_ready()
        if self._backend == "vertex":
            return self._generate_vertex(system_prompt, user_prompt, history, temperature)
        return self._generate_aistudio(system_prompt, user_prompt, history, temperature)

    # ------------------------------------------------------------------
    # Backend-specific implementations
    # ------------------------------------------------------------------

    def _generate_vertex(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Iterable[dict[str, Any]],
        temperature: float,
    ) -> str:
        try:
            model = VertexGenerativeModel(  # type: ignore[union-attr]
                model_name=self._config.model,
                system_instruction=system_prompt,
                generation_config=VertexGenerationConfig(  # type: ignore[union-attr]
                    temperature=temperature,
                    top_p=0.95,
                    max_output_tokens=1024,
                ),
                safety_settings={
                    VertexHarmCategory.HARM_CATEGORY_HARASSMENT: VertexHarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    VertexHarmCategory.HARM_CATEGORY_HATE_SPEECH: VertexHarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    VertexHarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: VertexHarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    VertexHarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: VertexHarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                },
            )
            chat = model.start_chat(history=list(history))
            resp = chat.send_message(user_prompt)
        except Exception as exc:  # pragma: no cover - upstream failure
            log.exception("Vertex Gemini call failed")
            raise ServiceUnavailable("Gemini", str(exc)) from exc

        text = (getattr(resp, "text", "") or "").strip()
        return text or self._empty_fallback()

    def _generate_aistudio(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Iterable[dict[str, Any]],
        temperature: float,
    ) -> str:
        try:
            model = genai.GenerativeModel(  # type: ignore[union-attr]
                model_name=self._config.model,
                system_instruction=system_prompt,
                generation_config={
                    "temperature": temperature,
                    "top_p": 0.95,
                    "max_output_tokens": 1024,
                },
                safety_settings={
                    "HARM_CATEGORY_HARASSMENT": "BLOCK_MEDIUM_AND_ABOVE",
                    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_MEDIUM_AND_ABOVE",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_MEDIUM_AND_ABOVE",
                    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_MEDIUM_AND_ABOVE",
                },
            )
            chat = model.start_chat(history=list(history))
            resp = chat.send_message(user_prompt)
        except Exception as exc:  # pragma: no cover - upstream
            log.exception("AI Studio Gemini call failed")
            raise ServiceUnavailable("Gemini", str(exc)) from exc

        text = (getattr(resp, "text", "") or "").strip()
        return text or self._empty_fallback()

    @staticmethod
    def _empty_fallback() -> str:
        return (
            "I couldn't generate a confident answer for that. Could you "
            "rephrase or ask about a more specific topic such as voter "
            "registration, election dates, or polling locations?"
        )
