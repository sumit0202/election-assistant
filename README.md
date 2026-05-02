# CivicGuide — Election Process Education Assistant

> **Vertical chosen:** _Election Process Education_ — _"Create an assistant
> that helps users understand the election process, timelines, and steps in
> an interactive and easy-to-follow way."_

CivicGuide is a **non-partisan, multilingual** assistant that helps any
citizen understand how elections actually work — eligibility, voter
registration, ID requirements, polling timings, the role of the Election
Commission, EVM/VVPAT, postal ballots, and what happens after votes are
cast. It is built on a clean FastAPI + vanilla-JS stack and integrates
**five Google services**.

---

## ✨ What it can do

- **Conversational Q&A** about the election process, in plain language,
  in 6+ languages.
- **Find polling-style venues** near an address using Google Maps.
- **Recommend trusted explainer videos** from YouTube (boosting verified
  channels like the Election Commission, PIB, BBC, Reuters).
- **Translate** any reply on the fly via Google Cloud Translation.
- **Generate calendar reminders** as `.ics` files importable into Google
  Calendar, Apple Calendar or Outlook.
- **Refuses partisan questions** — never recommends candidates or parties.

---

## 🧠 Logic & Architecture

```
┌──────────────────────┐     ┌──────────────────────────────────────┐
│  Browser (vanilla JS)│ ──► │  FastAPI app                         │
│  /static/*.html|js   │     │  ┌────────────┐    ┌──────────────┐  │
└──────────────────────┘     │  │ Safety     │ ─► │ ElectionAgent│  │
                             │  │ guards     │    └──────┬───────┘  │
                             │  └────────────┘           │          │
                             │                ┌──────────┴────────┐ │
                             │                ▼                   ▼ │
                             │         Gemini (LLM)        Tool calls│
                             │                              │   │   │
                             │       ┌──────────────────────┘   │   │
                             │       ▼                          ▼   │
                             │  Google Maps   YouTube   Translate    │
                             └──────────────────────────────────────┘
```

### Decision flow inside `ElectionAgent`

1. **Input safety check** — strips PII (email, phone, Aadhaar, PAN), blocks
   prompt-injection, and refuses partisan questions before they reach the
   model. (`app/safety.py`)
2. **Gemini routing** — the model is instructed to emit a small JSON plan:
   `{"tool": "...", "args": {...}, "say": "..."}`.
   - `polling_locations` → calls Maps geocoding + Places Text Search.
   - `videos` → calls YouTube Data API with safe-search and trusted-channel
     boosting.
   - `none` → answer directly from the model's grounded prompt.
3. **Output safety check** rewrites/filters anything partisan that slipped
   through.
4. **Citation footer** is appended so the user knows *where* the data came
   from and is reminded to verify on the official ECI portal.

### Why ICS over Google Calendar OAuth?

OAuth would be a much heavier security and UX burden (consent screens,
verified app review, refresh tokens, secret storage). A signed ICS file
plays perfectly with Google Calendar (and every other calendar) without
ever asking the citizen for credentials. This is a deliberate, practical
trade-off that keeps the app *safer* for users and *simpler* to maintain.

---

## 🔌 Google services integrated (5)

| # | Service                          | Used for                                              | File                              |
|---|----------------------------------|-------------------------------------------------------|-----------------------------------|
| 1 | **Gemini API** (Google AI)       | Core conversational reasoning + tool routing          | `app/services/gemini.py`          |
| 2 | **Google Maps Platform**         | Geocoding + Places Text Search for polling venues     | `app/services/maps.py`            |
| 3 | **YouTube Data API v3**          | Trusted explainer-video discovery                     | `app/services/youtube.py`         |
| 4 | **Google Cloud Translation v3**  | On-demand reply translation for accessibility         | `app/services/translate.py`       |
| 5 | **Google Calendar (.ics)**       | Universal reminder-import for any calendar app        | `app/services/calendar_ics.py`    |

> All services are *lazy-initialised* — the app boots and the static UI
> loads even if some keys are missing, so each feature degrades gracefully.

---

## 🛡️ Security & responsible AI

- **Pydantic v2 validation** on every endpoint.
- **CORS allow-list**, **GZip**, **per-IP rate-limiting** (slowapi).
- **Full security-header suite**: `Content-Security-Policy` (strict, no
  inline script), `Strict-Transport-Security` (HSTS, preload-ready),
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`, `Cross-Origin-Opener-Policy`,
  `Cross-Origin-Resource-Policy`.
- **PII redaction** of phone, email, Aadhaar, PAN before LLM calls.
- **Prompt-injection** patterns blocked at input.
- **Non-partisanship** enforced on input *and* output.
- **Container hardening**: multi-stage build, runs as non-root user,
  minimal `python:3.11-slim` base.
- **Supply chain**: Dependabot weekly PRs (`.github/dependabot.yml`),
  `pip-audit` and `bandit` in CI, pinned versions in `requirements.txt`.
- **Pre-commit**: `ruff`, `bandit`, secret-detection (`.pre-commit-config.yaml`).
- See [`SECURITY.md`](./SECURITY.md) for the full threat model and
  responsible-disclosure policy.

---

## ♿ Accessibility

- Skip-link, semantic landmarks (`<header>`, `<main>`, `<aside>`,
  `<footer>`), `aria-live` chat region (`role="log"`), visible focus rings.
- Keyboard-first: `Enter` to send, `Shift+Enter` for newline. Form fields
  carry explicit labels, `autocomplete` hints, and `aria-describedby`
  guidance.
- `<html lang>` updates dynamically when the locale changes — screen
  readers pronounce content correctly.
- Honours `prefers-color-scheme`, `prefers-reduced-motion`,
  `prefers-contrast`, and `forced-colors` (Windows High Contrast).
- Mobile-first responsive grid; tested down to 320 px viewports.
- 6 starter languages (English, Hindi, Tamil, Bengali, Marathi, Telugu)
  with proper `lang=""` per option for correct text-to-speech.
- Web App Manifest + theme-color for installable PWA experience.

---

## 🚀 Run locally

Prereqs: Python 3.11+, a Gemini API key (and optionally Maps + YouTube).

```bash
cd election_assistant
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit with your keys
./run.sh
# open http://localhost:8080
```

### Tests

```bash
pytest -q --cov=app --cov-report=term-missing
```

The test suite is fully offline — Google clients are stubbed via fakes and
HTTP-mocked with `respx`. Current state: **50 tests, 91% coverage**.

### Continuous integration

Every push and PR runs `.github/workflows/ci.yml`:

1. `ruff check` + `ruff format --check`
2. `bandit` security audit
3. `pytest --cov` on Python 3.11 *and* 3.12 (matrix)
4. `pip-audit` dependency CVE scan
5. `docker build` (cached) — proves the Cloud Run image still builds

### Dev hygiene

```bash
pip install pre-commit && pre-commit install
```

Wires up `ruff`, `bandit`, secret-detection, large-file & merge-conflict
checks before every commit.

### More docs

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — system + agent flow diagrams
- [`SECURITY.md`](./SECURITY.md) — threat model & disclosure policy
- [`docs/API.md`](./docs/API.md) — every endpoint documented with examples
- [`docs/TESTING.md`](./docs/TESTING.md) — test pyramid, fixtures, markers
- [`docs/ACCESSIBILITY.md`](./docs/ACCESSIBILITY.md) — WCAG 2.2 AA conformance plan
- [`CHANGELOG.md`](./CHANGELOG.md) — version history (Keep-a-Changelog format)
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — local dev, code style, PR flow
- [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) — community standards
- [`LICENSE`](./LICENSE) — MIT

### Convenience targets (`Makefile`)

```bash
make install     # set up venv + install everything
make test        # run the suite verbose
make cov         # run with coverage + HTML report
make lint        # ruff + bandit (no fixes)
make fmt         # auto-fix style
make audit       # pip-audit against the GHSA DB
make ci          # everything CI runs, locally
make docker-run  # build + run the prod image on :8080
```

---

## ☁️ Deploy to Google Cloud Run

This is the **fastest, cheapest, most scalable** path: a single container
auto-scaling from zero, with secrets managed by Secret Manager and
**Application Default Credentials** for Translate (no JSON keys on disk).

### 0. One-time prerequisites

```bash
# Install the gcloud CLI: https://cloud.google.com/sdk/docs/install
gcloud auth login
gcloud auth application-default login
```

### 1. Set environment variables (edit values)

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="asia-south1"            # or us-central1, etc.
export SERVICE="civicguide"
export REPO="apps"                     # Artifact Registry repo name
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}:v1"
```

### 2. Configure the project & enable APIs

```bash
gcloud config set project "$PROJECT_ID"

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  generativelanguage.googleapis.com \
  translate.googleapis.com \
  youtube.googleapis.com \
  maps-backend.googleapis.com \
  places-backend.googleapis.com \
  geocoding-backend.googleapis.com
```

### 3. Create the Artifact Registry repository

```bash
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="App images"
```

### 4. Store secrets in Secret Manager

```bash
printf "%s" "YOUR_GEMINI_KEY"   | gcloud secrets create GEMINI_API_KEY     --data-file=-
printf "%s" "YOUR_MAPS_KEY"     | gcloud secrets create GOOGLE_MAPS_API_KEY --data-file=-
printf "%s" "YOUR_YOUTUBE_KEY"  | gcloud secrets create YOUTUBE_API_KEY    --data-file=-
```

### 5. Create a dedicated runtime service account

```bash
gcloud iam service-accounts create civicguide-runtime \
  --display-name="CivicGuide Cloud Run runtime"

export SA="civicguide-runtime@${PROJECT_ID}.iam.gserviceaccount.com"

# Allow it to read secrets & call Translate
for SECRET in GEMINI_API_KEY GOOGLE_MAPS_API_KEY YOUTUBE_API_KEY; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${SA}" \
    --role="roles/secretmanager.secretAccessor"
done

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/cloudtranslate.user"
```

### 6. Build the image with Cloud Build

```bash
gcloud builds submit --tag "$IMAGE" .
```

### 7. Deploy to Cloud Run

```bash
gcloud run deploy "$SERVICE" \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --service-account="$SA" \
  --cpu=1 --memory=512Mi \
  --concurrency=40 --min-instances=0 --max-instances=5 \
  --set-env-vars="APP_ENV=prod,LOG_LEVEL=info,GEMINI_MODEL=gemini-1.5-flash,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},TRANSLATE_LOCATION=global,RATE_LIMIT_PER_MINUTE=30,ALLOWED_ORIGINS=*" \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest,GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY:latest,YOUTUBE_API_KEY=YOUTUBE_API_KEY:latest"
```

The command prints a HTTPS URL like
`https://civicguide-xxxx-uc.a.run.app` — open it in any browser.

### 8. Updating

```bash
gcloud builds submit --tag "$IMAGE" .
gcloud run services update "$SERVICE" --region="$REGION" --image="$IMAGE"
```

### 9. Tear-down

```bash
gcloud run services delete "$SERVICE" --region="$REGION" --quiet
gcloud artifacts repositories delete "$REPO" --location="$REGION" --quiet
```

---

## 🧪 What gets tested

- Safety guards (PII redaction, partisan + injection blocks).
- Agent routing (direct answer, polling tool, video tool, malformed JSON).
- HTTP layer (health, chat, polling, videos, ICS download, security headers).
- Maps client against a mocked Google Geocoding/Places HTTP server.
- ICS generator output structure (VCALENDAR, VEVENT, two VALARMs).

---

## 📂 Project layout

```
election_assistant/
├── app/
│   ├── agent.py            # Gemini + tool orchestration
│   ├── config.py           # 12-factor settings (pydantic-settings)
│   ├── main.py             # FastAPI app, routes, middleware
│   ├── safety.py           # input/output content guards
│   ├── schemas.py          # request/response models
│   └── services/
│       ├── calendar_ics.py # universal .ics generator
│       ├── errors.py
│       ├── gemini.py       # Google Gemini wrapper
│       ├── maps.py         # Geocoding + Places
│       ├── translate.py    # Cloud Translation v3
│       └── youtube.py      # YouTube Data API v3
├── static/                 # vanilla-JS SPA (no build step)
├── tests/                  # pytest suite (offline)
├── Dockerfile              # multi-stage, non-root
├── pyproject.toml
├── requirements.txt
├── run.sh                  # local dev launcher
├── .env.example
└── README.md
```

---

## 📝 Assumptions

- The Election Commission of any region publishes its **own authoritative
  voter-roll/booth-finder portal**. CivicGuide therefore deliberately does
  **not** claim to be that portal — instead it surfaces *candidate* venues
  and always points users back to the official source.
- Users may not have a Google account; `.ics` is preferred over OAuth-based
  Google Calendar inserts.
- Gemini may occasionally produce non-JSON output; the agent parses
  defensively and falls back to the raw text as the answer.

---

## 📄 License

MIT — see `LICENSE` (or use as-is for the H2S submission).
