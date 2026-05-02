# CivicGuide HTTP API

Base URL (Cloud Run): `https://<service>.run.app`
Base URL (local): `http://localhost:8080`

All endpoints return JSON unless stated otherwise. All errors share the same
shape:

```json
{ "error": "<machine-readable code>", "detail": "<human-readable message>" }
```

Interactive Swagger UI is auto-generated at **`/docs`**, ReDoc at **`/redoc`**.

---

## `GET /api/health`

Lightweight liveness probe. Used by Cloud Run, uptime monitors, and CI.

**Response 200**

```json
{ "status": "ok", "version": "1.0.0", "env": "prod" }
```

---

## `POST /api/chat`

Conversational entry point. Routes through input safety → FAQ → Gemini →
optional tool calls → output safety.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | `string` (1..2000) | yes | User question. Sanitised + redacted before LLM. |
| `session_id` | `string` (4..64) | yes | Opaque client session identifier. |
| `locale` | `string` (`en` ¦ `hi` ¦ `ta` ¦ `bn` ¦ `mr` ¦ `te`) | no, default `en` | Reply language. |
| `location` | `string` (1..200) | no | Optional user-supplied city / address. |

**Example**

```bash
curl -sX POST localhost:8080/api/chat \
  -H 'content-type: application/json' \
  -d '{"message":"How do I register as a first-time voter?","session_id":"abcd1234","locale":"en"}'
```

**Response 200**

```json
{
  "reply": "To register as a first-time voter in India, you must be 18+...",
  "locale": "en",
  "tools_used": [],
  "citations": ["Election Commission of India — eci.gov.in"],
  "safety_filtered": false
}
```

**Errors**

- `400` validation failure (missing/empty message, locale not allowed, ...)
- `429` per-IP rate-limit exceeded
- `503` upstream Google service unavailable

---

## `POST /api/polling-places`

Find polling-style venues (schools, halls, community centres) near an
address using Google Maps Geocoding + Places Text Search.

**Request body**

| Field | Type | Required |
|---|---|---|
| `address` | `string` (1..200) | yes |
| `radius_m` | `int` (200..20000), default 5000 | no |

**Response 200**

```json
{
  "query": "MG Road, Bengaluru",
  "results": [
    {
      "name": "St. Joseph's Boys' High School",
      "address": "Vittal Mallya Road, Bengaluru",
      "distance_m": 412.7,
      "map_url": "https://www.google.com/maps/?q=..."
    }
  ]
}
```

---

## `POST /api/videos`

Search YouTube for trusted election-process explainers. Boosts a curated
allow-list of channels (Election Commission of India, PIB, BBC, Reuters,
Al Jazeera, DW).

**Request body**

| Field | Type | Required |
|---|---|---|
| `topic` | `string` (1..200) | yes |
| `locale` | `string`, default `en` | no |
| `max_results` | `int` (1..10), default 5 | no |

**Response 200**

```json
{
  "topic": "EVM and VVPAT",
  "items": [
    {
      "title": "How EVMs and VVPATs work",
      "channel": "Election Commission of India",
      "url": "https://www.youtube.com/watch?v=...",
      "published_at": "2024-04-12T08:30:00Z",
      "description": "Official explainer..."
    }
  ]
}
```

---

## `POST /api/translate`

Translate any text via Google Cloud Translation v3. Uses Application
Default Credentials — no API key on disk.

**Request body**

```json
{ "text": "Hello", "target": "hi", "source": "en" }
```

**Response 200**

```json
{ "text": "नमस्ते", "target": "hi", "source_detected": "en" }
```

---

## `POST /api/reminder.ics`

Generate a universal `.ics` calendar file (RFC 5545). Importable into
Google Calendar, Apple Calendar, Outlook, Fastmail, etc. No OAuth needed.

**Request body**

```json
{
  "title": "Maharashtra polling day",
  "description": "Carry voter ID. Polling 7 AM - 6 PM.",
  "start": "2026-11-05T09:00:00+05:30",
  "duration_minutes": 60,
  "location": "Booth #123"
}
```

**Response 200**

`Content-Type: text/calendar; Content-Disposition: attachment` — binary
ICS payload.

---

## Shared response headers

| Header | Value | Why |
|---|---|---|
| `Content-Security-Policy` | `default-src 'self'; ...` | Mitigates XSS / clickjacking |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | Force HTTPS (HTTPS requests only) |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME sniffing |
| `X-Frame-Options` | `DENY` | Anti-clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer leak |
| `Permissions-Policy` | `geolocation=(self), microphone=(), camera=()` | Disables unused powerful APIs |
| `Cross-Origin-Opener-Policy` | `same-origin` | Spectre mitigations |
| `X-Request-ID` | `<uuid>` | Same value appears in server logs |

---

## Rate limits

Per-IP, applied via `slowapi`. Default: **30 requests/minute**, configurable
via the `RATE_LIMIT_PER_MINUTE` env var. Exceeding it returns
`HTTP 429 Too Many Requests` with a `Retry-After` header.

---

## Versioning & deprecation

The API version is exposed in the `version` field of `/api/health` and in
the OpenAPI document at `/openapi.json`. Breaking changes follow SemVer
and are tracked in [`CHANGELOG.md`](../CHANGELOG.md).
