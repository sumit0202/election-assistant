# AGENTS.md — Conventions for AI coding agents

This file is a contract between human contributors and AI coding agents
(Cursor, Claude Code, Codex, etc.) working on this repo. Following these
rules keeps the codebase predictable and reviewable.

## Repository invariants

These must remain true at every commit on `main`:

1. **Public API surface is stable.** The shapes in `app/schemas.py` are the
   contract. Adding optional fields is fine; renaming or removing existing
   fields is a breaking change → bump the major version.
2. **No secrets in code, history, or `.env.example`.** Use Google Secret
   Manager in production; rotate any key that lands in git history.
3. **Tests stay offline.** No real Google API calls in `pytest`. Use
   `respx` for HTTP, monkeypatching for SDK clients.
4. **`ruff check`, `ruff format --check`, `bandit -ll`, and the test suite
   must pass.** CI enforces this; pre-commit catches it locally.
5. **Coverage cannot drop below 85%.** It currently sits at 93%.
6. **No partisan content.** This is the project's raison d'être. PRs that
   add candidate-recommendation, polling-prediction, or campaign material
   will be declined.

## Code style

- **Python**: 3.11+, type hints on every public function, docstrings on
  every public callable (Google-style). 100-char line limit.
- **Imports**: sorted by `ruff` (`isort` rules); group stdlib, third-party,
  local.
- **Structure**: thin route → service-client → external API. No business
  logic in `main.py`; that lives in `agent.py` or `services/`.
- **Errors**: raise `ServiceUnavailable` from `app/services/errors.py` when
  an upstream Google service fails. The global handler turns it into a
  503 with a structured JSON body.
- **JS**: vanilla ES modules, no framework, 2-space indent. No build step.

## Where things live

| What | Where |
|---|---|
| FastAPI routes | `app/main.py` |
| Orchestration logic | `app/agent.py` |
| Pydantic models | `app/schemas.py` |
| Settings (12-factor) | `app/config.py` |
| Service-client adapters | `app/services/*.py` |
| Curated FAQ data | `app/data/faq.json` |
| SPA shell | `static/index.html` |
| SPA logic | `static/app.js` |
| Tests | `tests/test_*.py` |
| Architecture diagrams | `ARCHITECTURE.md` |
| API reference | `docs/API.md` |

## Common tasks — do this, not that

### Adding a route
1. Add the request/response models to `app/schemas.py` with `Field(...,
   description=..., examples=...)`.
2. Wire the route in `app/main.py` with `summary`, `description`,
   `response_description`, and a `tags` entry.
3. Add an end-to-end test in `tests/test_api.py`.
4. Add at least one unit test for any new service-layer code.
5. Update `docs/API.md`.

### Adding a Google service
1. Create a new facade in `app/services/<name>.py`. Keep it small.
2. Inject the client in `app/main.py`'s `lifespan()`.
3. Add IAM / API instructions to `README.md` (Cloud Run section).
4. Add `respx`-backed tests for HTTP calls.

### Adding an FAQ entry
- Edit `app/data/faq.json`. Each entry must have `id`, `keywords` (>=2),
  `title`, `answer` (markdown). Run `pytest tests/test_faq_integrity.py`.

## Don'ts

- **Do not** add `from __future__ import annotations` to `app/main.py` —
  it breaks FastAPI's runtime type introspection for forward references.
- **Do not** hard-code locale strings outside `SUPPORTED_LOCALES` in
  `app/schemas.py`.
- **Do not** remove the FAQ-first fallback layer. It is the project's
  resilience guarantee against LLM outages.
- **Do not** auto-merge dependabot PRs without running CI; transitively
  vulnerable upgrades sometimes break tests.

## Commit messages

- Imperative mood, scope prefix: `agent: short-circuit FAQ before LLM`.
- Body: one paragraph explaining *why*, not *what*.
- Reference the issue number if there is one.
- Do **not** add `Co-authored-by: Cursor` or other AI co-author trailers
  on this repo — those are stripped by the maintainer.

## Review checklist for PRs

- [ ] Tests added or updated for the change
- [ ] Docstrings on new public callables
- [ ] OpenAPI metadata on new routes
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] No new bandit findings
- [ ] No new dependencies without a clear reason
