"""HTTP-level tests for the YouTube client (uses respx to mock the API)."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.services.errors import ServiceUnavailable
from app.services.youtube import YouTubeClient


def _payload() -> dict:
    return {
        "items": [
            {
                "id": {"videoId": "abc123"},
                "snippet": {
                    "title": "How EVMs work",
                    "channelTitle": "Some Random Channel",
                    "publishedAt": "2024-01-01T00:00:00Z",
                    "description": "x" * 600,
                },
            },
            {
                "id": {"videoId": "xyz789"},
                "snippet": {
                    "title": "Voter registration explained",
                    "channelTitle": "Election Commission of India",
                    "publishedAt": "2024-02-01T00:00:00Z",
                    "description": "EC explainer",
                },
            },
            {
                # Live broadcast with no videoId — should be skipped.
                "id": {"kind": "youtube#channel"},
                "snippet": {"title": "noise", "channelTitle": "noise"},
            },
        ]
    }


@pytest.mark.asyncio
@respx.mock
async def test_search_boosts_trusted_channels_to_top() -> None:
    respx.get("https://www.googleapis.com/youtube/v3/search").mock(
        return_value=httpx.Response(200, json=_payload())
    )
    client = YouTubeClient(api_key="test")
    items = await client.search("voter id", locale="en-IN", max_results=3)
    await client.aclose()

    assert len(items) == 2
    assert items[0].channel == "Election Commission of India"  # boosted
    assert items[0].url == "https://www.youtube.com/watch?v=xyz789"
    # Description trimmed to 300 chars
    assert all(len(i.description or "") <= 300 for i in items)


@pytest.mark.asyncio
async def test_search_without_api_key_is_503() -> None:
    client = YouTubeClient(api_key="")
    with pytest.raises(ServiceUnavailable):
        await client.search("anything")
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_search_propagates_http_failure() -> None:
    respx.get("https://www.googleapis.com/youtube/v3/search").mock(
        return_value=httpx.Response(403, text="quota exceeded")
    )
    client = YouTubeClient(api_key="test")
    with pytest.raises(ServiceUnavailable) as exc:
        await client.search("voter")
    assert "403" in str(exc.value.detail)
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_search_clamps_max_results() -> None:
    captured = {}

    def _record(request):
        captured["max"] = request.url.params.get("maxResults")
        return httpx.Response(200, json={"items": []})

    respx.get("https://www.googleapis.com/youtube/v3/search").mock(side_effect=_record)
    client = YouTubeClient(api_key="test")
    await client.search("voter", max_results=42)
    await client.aclose()

    assert captured["max"] == "10"  # upper bound enforced
