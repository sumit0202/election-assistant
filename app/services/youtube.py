"""YouTube Data API v3 search wrapper for trusted election explainer videos."""

from __future__ import annotations

from typing import Any

import httpx

from ..schemas import VideoItem
from .errors import ServiceUnavailable

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# Short list of broadly trusted election-information channels. We bias the
# search but never *force* it; the model can still recommend other sources.
_TRUSTED_CHANNELS = (
    "Election Commission of India",
    "PIB India",
    "BBC News",
    "Reuters",
    "Al Jazeera English",
    "DW News",
)


class YouTubeClient:
    """Async wrapper around YouTube Data API v3 search."""

    def __init__(self, api_key: str, *, client: httpx.AsyncClient | None = None) -> None:
        """Construct a client. Pass an `httpx.AsyncClient` to share connection pools."""
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=10.0)

    def _ensure(self) -> None:
        """Raise `ServiceUnavailable` if no API key is configured."""
        if not self._api_key:
            raise ServiceUnavailable("YouTube", "YOUTUBE_API_KEY missing")

    async def search(
        self, topic: str, *, locale: str = "en", max_results: int = 5
    ) -> list[VideoItem]:
        """Search YouTube and return up to `max_results` videos, trusted-channels first."""
        self._ensure()
        query = f"{topic} election explainer"
        params: dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max(1, min(max_results, 10)),
            "safeSearch": "strict",
            "relevanceLanguage": locale[:2],
            "key": self._api_key,
        }
        r = await self._client.get(_SEARCH_URL, params=params)
        if r.status_code != 200:
            raise ServiceUnavailable("YouTube", f"HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        items: list[VideoItem] = []
        for entry in data.get("items", []):
            sn = entry.get("snippet") or {}
            vid = (entry.get("id") or {}).get("videoId")
            if not vid:
                continue
            items.append(
                VideoItem(
                    title=sn.get("title", ""),
                    channel=sn.get("channelTitle", ""),
                    url=f"https://www.youtube.com/watch?v={vid}",
                    published_at=sn.get("publishedAt"),
                    description=(sn.get("description") or "")[:300],
                )
            )

        def _rank(v: VideoItem) -> int:
            """Sort key: trusted channels first (0), everyone else (1)."""
            return 0 if v.channel in _TRUSTED_CHANNELS else 1

        items.sort(key=_rank)
        return items

    async def aclose(self) -> None:
        """Close the underlying `httpx.AsyncClient`."""
        await self._client.aclose()
