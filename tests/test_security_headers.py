"""Dedicated tests for the security-header middleware and `.well-known` files.

These are split from `test_api.py` so a future security-focused contributor
can run only the security suite (`pytest tests/test_security_headers.py`).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main as app_main


@pytest.fixture()
def client() -> TestClient:
    """Plain TestClient — no monkeypatching needed for header tests."""

    with TestClient(app_main.app) as c:
        yield c


@pytest.mark.e2e
def test_basic_security_headers(client: TestClient) -> None:
    """Every response must carry the canonical hardening header set."""

    r = client.get("/api/health")
    h = {k.lower(): v for k, v in r.headers.items()}

    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=(self)" in h["permissions-policy"]
    assert h["cross-origin-opener-policy"] == "same-origin"
    assert h["cross-origin-resource-policy"] == "same-origin"
    assert h["server"] == "CivicGuide"  # banner replaced


@pytest.mark.e2e
def test_csp_directives(client: TestClient) -> None:
    """The CSP must constrain the most-abused sources."""

    csp = client.get("/api/health").headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "form-action 'self'" in csp
    assert "base-uri 'self'" in csp
    assert "upgrade-insecure-requests" in csp


@pytest.mark.e2e
def test_request_id_round_trip(client: TestClient) -> None:
    """If the client supplies X-Request-ID, the server echoes it back."""

    r = client.get("/api/health", headers={"X-Request-ID": "trace-abc-123"})
    assert r.headers["X-Request-ID"] == "trace-abc-123"


@pytest.mark.e2e
def test_request_id_generated_when_absent(client: TestClient) -> None:
    """If the client doesn't supply one, the server generates a UUID."""

    r = client.get("/api/health")
    rid = r.headers["X-Request-ID"]
    assert len(rid) >= 16  # UUIDv4 hex is 32 chars; tolerate format change
    assert rid != "-"


@pytest.mark.e2e
def test_hsts_only_on_https(client: TestClient) -> None:
    """HSTS must be sent only over HTTPS / x-forwarded-proto=https."""

    plain = client.get("/api/health")
    assert "strict-transport-security" not in {k.lower() for k in plain.headers}

    secure = client.get("/api/health", headers={"x-forwarded-proto": "https"})
    assert "max-age=" in secure.headers["strict-transport-security"]
    assert "preload" in secure.headers["strict-transport-security"]


@pytest.mark.e2e
def test_well_known_security_txt(client: TestClient) -> None:
    """`.well-known/security.txt` must be served per RFC 9116."""

    r = client.get("/.well-known/security.txt")
    assert r.status_code == 200
    body = r.text
    assert "Contact:" in body
    assert "Expires:" in body
    assert "Policy:" in body


@pytest.mark.e2e
def test_robots_txt(client: TestClient) -> None:
    """robots.txt must be served at the conventional site root."""

    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "User-agent:" in r.text


@pytest.mark.e2e
def test_manifest_json(client: TestClient) -> None:
    """The PWA manifest must be served with the spec'd MIME type."""

    r = client.get("/manifest.json")
    assert r.status_code == 200
    assert "application/manifest" in r.headers["content-type"]
    body = r.json()
    assert body["name"] == "CivicGuide — Election Process Assistant"
    assert body["display"] == "standalone"


@pytest.mark.e2e
def test_cors_origin_header_safe(client: TestClient) -> None:
    """An untrusted Origin must NOT be reflected back."""

    r = client.options(
        "/api/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    # Either no ACAO (preferred) or one that does NOT echo the evil origin.
    acao = r.headers.get("access-control-allow-origin")
    assert acao != "https://evil.example"
