"""Google Cloud Translation v3 client.

Uses Application Default Credentials (ADC) — works seamlessly on Cloud Run
without leaking any keys. Locally, run `gcloud auth application-default login`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .errors import ServiceUnavailable

log = logging.getLogger(__name__)

try:
    from google.cloud import translate_v3 as translate  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dep
    translate = None  # type: ignore[assignment]


@dataclass
class TranslateConfig:
    project: str
    location: str = "global"


class TranslateClient:
    def __init__(self, config: TranslateConfig) -> None:
        self._config = config
        self._client: translate.TranslationServiceClient | None = None

    def _ensure(self) -> translate.TranslationServiceClient:
        if translate is None:
            raise ServiceUnavailable("Translate", "google-cloud-translate not installed")
        if not self._config.project:
            raise ServiceUnavailable("Translate", "GOOGLE_CLOUD_PROJECT missing")
        if self._client is None:
            try:
                self._client = translate.TranslationServiceClient()
            except Exception as exc:  # pragma: no cover - auth path
                raise ServiceUnavailable("Translate", str(exc)) from exc
        return self._client

    async def translate(
        self, text: str, target: str, source: str | None = None
    ) -> tuple[str, str | None]:
        client = self._ensure()
        parent = f"projects/{self._config.project}/locations/{self._config.location}"
        try:
            resp = client.translate_text(
                request={
                    "parent": parent,
                    "contents": [text],
                    "mime_type": "text/plain",
                    "source_language_code": source,
                    "target_language_code": target,
                }
            )
        except Exception as exc:  # pragma: no cover - upstream
            log.exception("Translate call failed")
            raise ServiceUnavailable("Translate", str(exc)) from exc

        if not resp.translations:
            return text, None
        t = resp.translations[0]
        return t.translated_text, getattr(t, "detected_language_code", None) or None
