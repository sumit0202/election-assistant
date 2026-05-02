"""Google Maps Platform integration.

Two endpoints are used:

* Geocoding API - turn a free-text address into lat/lng.
* Places API (Text Search) - find candidate polling locations nearby.

The HTTP layer uses `httpx.AsyncClient` so it composes naturally with FastAPI.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import httpx

from ..schemas import PollingPlace
from .errors import ServiceUnavailable

log = logging.getLogger(__name__)

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_PLACES_TEXT_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


class MapsClient:
    def __init__(self, api_key: str, *, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=10.0)

    def _ensure(self) -> None:
        if not self._api_key:
            raise ServiceUnavailable("Google Maps", "GOOGLE_MAPS_API_KEY missing")

    async def geocode(self, address: str) -> tuple[float, float, str]:
        self._ensure()
        params = {"address": address, "key": self._api_key}
        r = await self._client.get(_GEOCODE_URL, params=params)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "OK" or not data.get("results"):
            raise ServiceUnavailable("Google Maps", f"geocoding failed: {data.get('status')}")
        top = data["results"][0]
        loc = top["geometry"]["location"]
        return float(loc["lat"]), float(loc["lng"]), top.get("formatted_address", address)

    async def find_polling_places(
        self, address: str, radius_m: int = 5000
    ) -> tuple[str, list[PollingPlace]]:
        """Return polling-relevant places near the given address.

        Election commissions usually publish polling stations on dedicated
        portals, so we fall back to public landmarks (schools, community
        halls) typically used as polling stations and surface them with a
        clear caveat in the UI.
        """

        lat, lng, formatted = await self.geocode(address)
        params: dict[str, Any] = {
            "query": "polling station OR school OR community hall",
            "location": f"{lat},{lng}",
            "radius": radius_m,
            "key": self._api_key,
        }

        try:
            r = await self._client.get(_PLACES_TEXT_URL, params=params)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            log.warning("Places API failed: %s", exc)
            raise ServiceUnavailable("Google Maps", str(exc)) from exc

        results: list[PollingPlace] = []
        for item in (data.get("results") or [])[:10]:
            geom = (item.get("geometry") or {}).get("location") or {}
            try:
                d = _haversine_m(lat, lng, float(geom["lat"]), float(geom["lng"]))
            except (KeyError, TypeError, ValueError):
                d = None  # type: ignore[assignment]
            place_id = item.get("place_id")
            results.append(
                PollingPlace(
                    name=item.get("name", "Unknown"),
                    address=item.get("formatted_address", ""),
                    distance_m=round(d, 1) if d is not None else None,
                    rating=item.get("rating"),
                    place_id=place_id,
                    map_url=(
                        f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                        if place_id
                        else None
                    ),
                )
            )

        results.sort(key=lambda p: p.distance_m if p.distance_m is not None else 1e12)
        return formatted, results

    async def aclose(self) -> None:
        await self._client.aclose()
