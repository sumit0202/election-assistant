"""Wrapper around Google Generative AI (Gemini).

We use the official `google-generativeai` SDK, but expose a tiny async-friendly
interface so the rest of the app can mock it easily in tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from .errors import ServiceUnavailable

log = logging.getLogger(__name__)

# Imported lazily so the package can be installed in environments that
# don't need Gemini at runtime (e.g. CI that only runs unit tests).
try:
    import google.generativeai as genai  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - import error path
    genai = None  # type: ignore[assignment]


@dataclass
class GeminiConfig:
    api_key: str
    model: str


class GeminiClient:
    """Thin facade around `genai.GenerativeModel`."""

    def __init__(self, config: GeminiConfig) -> None:
        self._config = config
        self._configured = False

    def _ensure_ready(self) -> None:
        if self._configured:
            return
        if genai is None:
            raise ServiceUnavailable("Gemini", "google-generativeai not installed")
        if not self._config.api_key:
            raise ServiceUnavailable("Gemini", "GEMINI_API_KEY missing")
        genai.configure(api_key=self._config.api_key)
        self._configured = True

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: Iterable[dict[str, Any]] = (),
        temperature: float = 0.4,
    ) -> str:
        """Generate a single text reply.

        Note: the SDK call is synchronous; we rely on the FastAPI worker to
        run handlers in a threadpool. For higher throughput, swap to the REST
        API via httpx.AsyncClient.
        """

        self._ensure_ready()

        model = genai.GenerativeModel(  # type: ignore[union-attr]
            model_name=self._config.model,
            system_instruction=system_prompt,
            generation_config={
                "temperature": temperature,
                "top_p": 0.95,
                "max_output_tokens": 1024,
            },
            safety_settings={
                "HARASSMENT": "BLOCK_MEDIUM_AND_ABOVE",
                "HATE_SPEECH": "BLOCK_MEDIUM_AND_ABOVE",
                "SEXUALLY_EXPLICIT": "BLOCK_MEDIUM_AND_ABOVE",
                "DANGEROUS_CONTENT": "BLOCK_MEDIUM_AND_ABOVE",
            },
        )

        chat = model.start_chat(history=list(history))
        try:
            resp = chat.send_message(user_prompt)
        except Exception as exc:  # pragma: no cover - upstream failure
            log.exception("Gemini call failed")
            raise ServiceUnavailable("Gemini", str(exc)) from exc

        text = (getattr(resp, "text", "") or "").strip()
        if not text:
            return (
                "I couldn't generate a confident answer for that. Could you "
                "rephrase or ask about a more specific topic such as voter "
                "registration, election dates, or polling locations?"
            )
        return text
