"""Shared pytest fixtures.

We keep tests fully offline by stubbing out the Gemini, Maps, YouTube and
Translate clients before the FastAPI app is imported.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# Force a deterministic, key-less environment for every test.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GOOGLE_MAPS_API_KEY", "test-maps")
os.environ.setdefault("YOUTUBE_API_KEY", "test-yt")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "600")


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
