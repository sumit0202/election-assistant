# Changelog

All notable changes to CivicGuide are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Docstring coverage gate (`interrogate`)** enforcing ≥95% (now 100%) on `app/`
- **Mypy** static type-check step in CI for the whole `app/` package
- `docs/CODE-QUALITY.md` documenting enforced engineering metrics
- `make typecheck` + `make docstrings` developer targets
- README badges for docstring coverage and mypy
- Property-based tests using `hypothesis` for the safety + FAQ modules
- Request-ID middleware (`X-Request-ID` header for traceability)
- `/.well-known/security.txt` for responsible-disclosure metadata
- `Makefile` aggregating common dev commands (`make test`, `make lint`, ...)
- `.editorconfig` for IDE-agnostic style consistency
- `docs/API.md`, `docs/TESTING.md`, `docs/ACCESSIBILITY.md`
- Standalone `LICENSE` and this `CHANGELOG.md`
- `<noscript>` accessibility fallback in the SPA
- ARIA `role="toolbar"` on action button group
- Live-region status announcements for tool actions

### Changed

- All public callables now carry a docstring (Google style)
- Every route has explicit `summary`, `description`, `response_description`
  and `responses` for richer OpenAPI schema
- Server banner header stripped from responses

### Security

- Field-level `max_length` caps reinforced on all schema strings
- Per-request UUID propagated to logs for incident forensics

## [1.0.0] - 2026-05-02

### Added

- Initial public release for the H2S Round-1 hackathon
- 6 routes: `/api/chat`, `/api/polling-places`, `/api/videos`,
  `/api/translate`, `/api/reminder.ics`, `/api/health`
- 5 Google services integrated: Gemini (Vertex AI / AI Studio),
  Maps Platform (Geocoding + Places), YouTube Data API,
  Cloud Translation, ICS calendar export
- 3-layer fallback chain: FAQ → Gemini → graceful degradation
- Multilingual UI (English, Hindi, Tamil, Bengali, Marathi, Telugu)
- Cloud Run deployment instructions in `README.md`
- 50 tests, 91% coverage
- CI: ruff, bandit, pytest matrix (Py3.11/3.12), pip-audit, Docker build
- `ARCHITECTURE.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`
- Dependabot weekly updates for pip / actions / docker
- Pre-commit hooks: ruff, bandit, secret detection
