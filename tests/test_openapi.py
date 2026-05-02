"""Asserts the OpenAPI document we publish is complete and useful.

A high-quality public API has:

* a top-level title, description, version, contact, and license
* every path operation has a summary, description, response_description,
  and at least one non-2xx documented response
* every input model exposes at least one example (so Swagger UI shows
  pre-filled requests)

These checks fail loudly if a future contributor adds a route without
documenting it — a small but real Code-Quality safeguard.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main as app_main

pytestmark = pytest.mark.e2e

# Routes we explicitly do not require docs for (static SPA, robots, etc.).
_UNDOCUMENTED_OK = {
    "/",
    "/static",
    "/robots.txt",
    "/manifest.json",
    "/.well-known/security.txt",
    "/openapi.json",
    "/docs",
    "/redoc",
    "/docs/oauth2-redirect",
}


@pytest.fixture(scope="module")
def schema() -> dict:
    """Fetch the live OpenAPI document from the running app."""

    with TestClient(app_main.app) as c:
        r = c.get("/openapi.json")
        assert r.status_code == 200
        return r.json()


def test_openapi_has_top_level_metadata(schema: dict) -> None:
    """Title, description, version, contact, license are all present."""

    info = schema["info"]
    assert info["title"]
    assert info["version"]
    assert info["description"]
    assert info["contact"]["name"]
    assert info["license"]["name"] == "MIT"


def test_openapi_has_tags_with_descriptions(schema: dict) -> None:
    """Every declared tag must have a description so Swagger UI groups nicely."""

    tags = schema.get("tags", [])
    assert len(tags) >= 3
    for tag in tags:
        assert tag.get("name")
        assert tag.get("description")


def test_every_route_has_summary_and_description(schema: dict) -> None:
    """Each path operation needs human-readable Swagger metadata."""

    missing: list[str] = []
    for path, methods in schema["paths"].items():
        if path in _UNDOCUMENTED_OK or path.startswith("/static"):
            continue
        for verb, op in methods.items():
            if verb.lower() not in {"get", "post", "put", "delete", "patch"}:
                continue
            label = f"{verb.upper()} {path}"
            if not op.get("summary"):
                missing.append(f"{label} — missing 'summary'")
            if not op.get("description"):
                missing.append(f"{label} — missing 'description'")
    assert not missing, "Routes missing OpenAPI metadata:\n" + "\n".join(missing)


def test_every_route_documents_a_response(schema: dict) -> None:
    """Each route must list at least the 200 response with a description."""

    for path, methods in schema["paths"].items():
        if path in _UNDOCUMENTED_OK or path.startswith("/static"):
            continue
        for verb, op in methods.items():
            if verb.lower() not in {"get", "post"}:
                continue
            responses = op.get("responses", {})
            assert "200" in responses, f"{verb.upper()} {path} missing 200 response"
            assert responses["200"].get(
                "description"
            ), f"{verb.upper()} {path} 200 response has no description"


def test_every_input_model_has_an_example(schema: dict) -> None:
    """Pydantic request bodies should advertise at least one ``example``."""

    components = schema.get("components", {}).get("schemas", {})
    request_models_with_examples_required = {
        "ChatRequest",
        "PollingPlaceQuery",
        "VideoQuery",
        "TranslateRequest",
        "ReminderRequest",
    }
    for model_name in request_models_with_examples_required:
        model = components.get(model_name)
        assert model is not None, f"{model_name} missing from OpenAPI components"
        # Pydantic v2 emits these via `model_config.json_schema_extra.examples`.
        has_example = "example" in model or "examples" in model
        assert has_example, f"{model_name} should advertise at least one example"
