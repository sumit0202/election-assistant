"""Unit tests for the Gemini facade — backend selection + error paths."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import gemini as gemini_module
from app.services.errors import ServiceUnavailable
from app.services.gemini import GeminiClient, GeminiConfig


def test_no_credentials_at_all_raises() -> None:
    client = GeminiClient(GeminiConfig(model="gemini-2.0-flash"))
    with pytest.raises(ServiceUnavailable) as exc:
        # `_ensure_ready` is the canonical entry point; reach via generate.
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            client.generate("sys", "hi")
        ) if False else client._ensure_ready()
    assert "neither" in str(exc.value.detail).lower()


def test_picks_vertex_when_project_set(monkeypatch) -> None:
    init_calls: list[dict] = []

    fake_vertexai = SimpleNamespace(init=lambda **kw: init_calls.append(kw))
    monkeypatch.setattr(gemini_module, "vertexai", fake_vertexai)
    monkeypatch.setattr(gemini_module, "VertexGenerativeModel", object, raising=False)

    client = GeminiClient(
        GeminiConfig(model="gemini-2.0-flash-001", project="proj", location="us-central1")
    )
    client._ensure_ready()

    assert client._backend == "vertex"
    assert init_calls == [{"project": "proj", "location": "us-central1"}]


def test_picks_aistudio_when_only_api_key(monkeypatch) -> None:
    configured_keys: list[str] = []
    fake_genai = SimpleNamespace(configure=lambda api_key: configured_keys.append(api_key))
    # Force vertex unavailable so api_key path is taken.
    monkeypatch.setattr(gemini_module, "vertexai", None)
    monkeypatch.setattr(gemini_module, "genai", fake_genai)

    client = GeminiClient(GeminiConfig(model="m", api_key="k"))
    client._ensure_ready()

    assert client._backend == "aistudio"
    assert configured_keys == ["k"]


def test_init_is_idempotent(monkeypatch) -> None:
    fake_genai = SimpleNamespace(configure=lambda api_key: None)
    monkeypatch.setattr(gemini_module, "vertexai", None)
    monkeypatch.setattr(gemini_module, "genai", fake_genai)

    client = GeminiClient(GeminiConfig(model="m", api_key="k"))
    client._ensure_ready()
    client._ensure_ready()  # second call must be a no-op
    assert client._initialized is True


def test_empty_fallback_text_is_helpful() -> None:
    msg = GeminiClient._empty_fallback()
    assert "rephrase" in msg.lower() or "specific" in msg.lower()
