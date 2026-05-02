"""HTTP-level test for MapsClient using respx to mock Google endpoints."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.services.maps import MapsClient


@pytest.mark.asyncio
async def test_find_polling_places_uses_geocode_then_places():
    async with httpx.AsyncClient() as http_client:
        client = MapsClient(api_key="x", client=http_client)

        with respx.mock(assert_all_called=True) as mock:
            mock.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "status": "OK",
                        "results": [
                            {
                                "formatted_address": "MG Road, Bengaluru, India",
                                "geometry": {"location": {"lat": 12.97, "lng": 77.59}},
                            }
                        ],
                    },
                )
            )
            mock.get("https://maps.googleapis.com/maps/api/place/textsearch/json").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "name": "Govt School",
                                "formatted_address": "Brigade Rd",
                                "place_id": "p1",
                                "geometry": {"location": {"lat": 12.971, "lng": 77.591}},
                                "rating": 4.2,
                            }
                        ]
                    },
                )
            )

            formatted, places = await client.find_polling_places("MG Road")

        assert formatted.startswith("MG Road")
        assert len(places) == 1
        assert places[0].name == "Govt School"
        assert places[0].distance_m is not None
        assert places[0].map_url is not None


@pytest.mark.asyncio
async def test_geocode_failure_raises_service_unavailable():
    from app.services.errors import ServiceUnavailable

    async with httpx.AsyncClient() as http_client:
        client = MapsClient(api_key="x", client=http_client)
        with respx.mock() as mock:
            mock.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
                return_value=httpx.Response(200, json={"status": "ZERO_RESULTS", "results": []})
            )
            with pytest.raises(ServiceUnavailable):
                await client.geocode("nowhere")
