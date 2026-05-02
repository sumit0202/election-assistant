"""Unit tests for the Translate client (pure-Python, no real GCP calls)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import translate as translate_module
from app.services.errors import ServiceUnavailable
from app.services.translate import TranslateClient, TranslateConfig


class _FakeStub:
    """Stand-in for `google.cloud.translate_v3.TranslationServiceClient`."""

    def __init__(self) -> None:
        self.last_request: dict | None = None

    def translate_text(self, request: dict):
        self.last_request = request
        return SimpleNamespace(
            translations=[
                SimpleNamespace(
                    translated_text="नमस्ते",
                    detected_language_code="en",
                )
            ]
        )


@pytest.mark.asyncio
async def test_translate_happy_path(monkeypatch) -> None:
    fake_stub = _FakeStub()
    fake_module = SimpleNamespace(TranslationServiceClient=lambda: fake_stub)
    monkeypatch.setattr(translate_module, "translate", fake_module)

    client = TranslateClient(TranslateConfig(project="proj", location="global"))
    out, detected = await client.translate("hello", target="hi")

    assert out == "नमस्ते"
    assert detected == "en"
    assert fake_stub.last_request["parent"] == "projects/proj/locations/global"
    assert fake_stub.last_request["target_language_code"] == "hi"


@pytest.mark.asyncio
async def test_translate_without_project_is_503(monkeypatch) -> None:
    fake_module = SimpleNamespace(TranslationServiceClient=lambda: _FakeStub())
    monkeypatch.setattr(translate_module, "translate", fake_module)

    client = TranslateClient(TranslateConfig(project="", location="global"))
    with pytest.raises(ServiceUnavailable):
        await client.translate("hello", target="hi")


@pytest.mark.asyncio
async def test_translate_when_module_missing(monkeypatch) -> None:
    monkeypatch.setattr(translate_module, "translate", None)
    client = TranslateClient(TranslateConfig(project="proj"))
    with pytest.raises(ServiceUnavailable) as exc:
        await client.translate("hi", target="en")
    assert "google-cloud-translate" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_translate_handles_empty_response(monkeypatch) -> None:
    class _Empty:
        def translate_text(self, request: dict):
            return SimpleNamespace(translations=[])

    fake_module = SimpleNamespace(TranslationServiceClient=_Empty)
    monkeypatch.setattr(translate_module, "translate", fake_module)

    client = TranslateClient(TranslateConfig(project="proj"))
    out, detected = await client.translate("hello", target="hi")
    assert out == "hello"
    assert detected is None
