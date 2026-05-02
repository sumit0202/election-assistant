"""End-to-end API tests using FastAPI's TestClient + monkey-patched services."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.agent import AgentResult
from app.schemas import PollingPlace, VideoItem


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    from app import main as app_main

    async def fake_respond(self, *, user_message, locale, location):
        return AgentResult(reply=f"Echo: {user_message}", citations=["test"])

    monkeypatch.setattr(app_main.ElectionAgent, "respond", fake_respond, raising=True)

    async def fake_polling(self, address, radius_m=5000):
        return address, [PollingPlace(name="School", address=address, distance_m=100.0)]

    monkeypatch.setattr(app_main.MapsClient, "find_polling_places", fake_polling, raising=True)

    async def fake_yt(self, topic, *, locale="en", max_results=5):
        return [VideoItem(title="t", channel="c", url="https://yt/x")]

    monkeypatch.setattr(app_main.YouTubeClient, "search", fake_yt, raising=True)

    with TestClient(app_main.app) as c:
        yield c


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["env"] == "test"


def test_chat_happy_path(client: TestClient):
    r = client.post(
        "/api/chat",
        json={
            "message": "How do I register to vote?",
            "session_id": "abcd1234",
            "locale": "en",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply"].startswith("Echo:")
    assert body["safety_filtered"] is False


def test_chat_blocks_partisan(client: TestClient):
    r = client.post(
        "/api/chat",
        json={
            "message": "who should I vote for?",
            "session_id": "abcd1234",
            "locale": "en",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["safety_filtered"] is True


def test_chat_validation_error(client: TestClient):
    r = client.post(
        "/api/chat",
        json={"message": "  ", "session_id": "abcd", "locale": "en"},
    )
    assert r.status_code == 422


def test_polling_endpoint(client: TestClient):
    r = client.post("/api/polling-places", json={"address": "MG Road"})
    assert r.status_code == 200
    data = r.json()
    assert data["query"] == "MG Road"
    assert data["results"][0]["name"] == "School"


def test_videos_endpoint(client: TestClient):
    r = client.post("/api/videos", json={"topic": "voter ID", "locale": "en", "max_results": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["items"][0]["title"] == "t"


def test_reminder_ics_download(client: TestClient):
    r = client.post(
        "/api/reminder.ics",
        json={
            "title": "Polling day",
            "description": "Vote",
            "start": datetime(2026, 11, 5, 9, 0, tzinfo=UTC).isoformat(),
            "duration_minutes": 60,
        },
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    assert b"BEGIN:VCALENDAR" in r.content


def test_security_headers_present(client: TestClient):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=(self)" in r.headers["permissions-policy"]
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert r.headers["cross-origin-opener-policy"] == "same-origin"


def test_hsts_header_when_forwarded_https(client: TestClient):
    r = client.get("/api/health", headers={"x-forwarded-proto": "https"})
    assert "strict-transport-security" in r.headers
    assert "max-age=" in r.headers["strict-transport-security"]


def test_unknown_route_returns_structured_404(client: TestClient):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "not_found"


def test_chat_strips_pii_before_routing(client: TestClient):
    r = client.post(
        "/api/chat",
        json={
            "message": "My email is voter@example.com, can I register?",
            "session_id": "abcd1234",
            "locale": "en",
        },
    )
    assert r.status_code == 200
    # The fake agent echoes the sanitized message, so PII must be redacted there.
    assert "voter@example.com" not in r.json()["reply"]
    assert "[EMAIL_REDACTED]" in r.json()["reply"]


def test_static_index_is_served(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
