# Testing strategy

CivicGuide ships with a deterministic, fully offline test suite that runs
in **under 2 seconds** on a laptop. This document explains the layering,
fixtures, and how to add new tests.

## Pyramid

```
                       ┌────────────────────┐
                       │  E2E (TestClient)  │   ← test_api.py
                       │  ~12 tests         │
                       └────────────────────┘
                ┌──────────────────────────────────┐
                │  Integration (mock HTTP / SDK)   │   ← test_maps.py,
                │  ~12 tests                        │     test_youtube.py,
                │                                  │     test_translate.py
                └──────────────────────────────────┘
       ┌──────────────────────────────────────────────────┐
       │  Unit (pure functions, dataclasses, agents)      │   ← test_agent.py,
       │  ~30 tests                                        │     test_safety.py,
       │                                                  │     test_faq.py,
       │                                                  │     test_calendar_ics.py,
       │                                                  │     test_gemini.py,
       │                                                  │     test_properties.py
       └──────────────────────────────────────────────────┘
```

## Categories

| Marker | What it covers | Speed |
|---|---|---|
| `unit` | Pure functions, no I/O | < 5 ms each |
| `integration` | One service client, mocked HTTP | < 50 ms each |
| `e2e` | Full FastAPI request / response cycle | < 100 ms each |
| `property` | Hypothesis-driven invariants | varies |

Run a subset:

```bash
pytest -m unit
pytest -m "integration or e2e"
pytest -m property -p hypothesis
```

## Fixtures

`tests/conftest.py` configures a deterministic environment:

- Sets dummy API keys so settings load.
- Sets `RATE_LIMIT_PER_MINUTE=600` to avoid throttling tests.
- Clears the `lru_cache` on `get_settings()` between tests.

`tests/test_api.py` adds a `client` fixture that **monkeypatches**
`ElectionAgent.respond`, `MapsClient.find_polling_places` and
`YouTubeClient.search` so no real HTTP calls happen.

## What we deliberately don't test

- The actual Gemini / Maps / YouTube SDK plumbing (would require live
  credentials and network). We test our adapter logic against fakes.
- `app/services/translate.py`'s real ADC auth flow — covered by GCP IAM
  policy in production.

These paths are tagged with `# pragma: no cover` so coverage stays honest.

## Coverage targets

| Module | Target | Current |
|---|---|---|
| `app/safety.py` | 100% | 94% |
| `app/agent.py` | 95% | 86% |
| `app/services/calendar_ics.py` | 100% | 100% |
| `app/services/faq.py` | 90% | 89% |
| `app/services/maps.py` | 90% | 93% |
| `app/services/youtube.py` | 90% | 100% |
| `app/services/translate.py` | 90% | 98% |
| `app/main.py` | 90% | 94% |
| **Overall** | **>=85%** | **91%** |

## Adding a test

1. Pick the right layer (unit if it's pure, integration if it makes HTTP
   calls — even mocked).
2. Tag with `@pytest.mark.unit` etc.
3. Use `respx` for HTTP mocks; `monkeypatch` for SDK swaps.
4. Run `pytest --cov=app` and ensure global coverage didn't drop.

## Property-based testing

`tests/test_properties.py` uses [Hypothesis](https://hypothesis.works/) to
generate thousands of synthetic inputs and assert invariants like:

- `safety.check_input` is **idempotent** — sanitising sanitised text yields
  the same string.
- The FAQ matcher's score is always in `[0, 1]`.
- Markdown citations never escape the `escapeHtml` filter.

These catch edge cases that example-based tests miss.

## CI

`.github/workflows/ci.yml` runs:

1. `ruff check` + `ruff format --check`
2. `bandit -ll` (medium+ severity)
3. `pytest --cov` on Python 3.11 *and* 3.12
4. `pip-audit` against the GitHub Advisory DB
5. `docker build` (cached)

Coverage XML is uploaded as an artifact; failing below 85% fails the build.
