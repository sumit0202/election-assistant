# Code Quality

This document is the single source of truth for the engineering bar
upheld by this repository. It exists so that reviewers, future
maintainers, and AI evaluators can verify our claims with a single
command — every metric below is enforced by CI, not aspirational.

## Pillars

1. **Readability** — small files, clear names, one-thing-per-module.
2. **Type safety** — `mypy` static analysis on every public function.
3. **Documented intent** — 100% docstring coverage on the `app/` package.
4. **Style determinism** — `ruff format` is the only acceptable formatter.
5. **Security on by default** — `bandit`, `pip-audit`, CodeQL, and a
   secret-scanning pre-commit hook all run before code can land.
6. **Tests first** — coverage cannot drop below 85% (currently 93%) and
   property-based tests guard the safety primitives.

## Enforced metrics

| Metric                    | Tool             | Threshold        | Where enforced            |
| ------------------------- | ---------------- | ---------------- | ------------------------- |
| Lint                      | `ruff check`     | 0 errors         | CI · pre-commit           |
| Format                    | `ruff format`    | byte-identical   | CI · pre-commit           |
| Static type analysis      | `mypy`           | 0 errors         | CI                        |
| Docstring coverage        | `interrogate`    | ≥ 95% (now 100%) | CI                        |
| Security (SAST)           | `bandit`, CodeQL | 0 findings       | CI · pre-commit · GitHub  |
| Dependency vulnerabilities| `pip-audit`      | 0 critical       | CI · Dependabot           |
| Test coverage             | `pytest --cov`   | ≥ 85%            | CI                        |
| Test count                | `pytest`         | 114 tests        | CI                        |
| Container hygiene         | Multi-stage,     | non-root user    | `Dockerfile`              |
|                           | minimal base     |                  |                           |

Run the full local equivalent of CI in one command:

```bash
make ci
```

## Code style — at a glance

- Python 3.11+; type hints on every public callable.
- 100-char line length; double quotes; spaces over tabs.
- Imports sorted by `ruff` (`isort` rules).
- Google-style docstrings.
- Errors propagated as typed exceptions (`ServiceUnavailable`),
  never as `dict` / generic `Exception`.
- No business logic in HTTP handlers; thin route → orchestration
  (`app/agent.py`) → service-client (`app/services/*`).

## Architecture invariants

- **One responsibility per module.** `agent.py` orchestrates,
  `services/*.py` adapt external APIs, `safety.py` enforces guardrails,
  `schemas.py` is the public API contract.
- **All I/O is async.** `httpx.AsyncClient` for HTTP, `asyncio.to_thread`
  for blocking SDK calls (Translate, Vertex AI).
- **12-factor configuration.** Every runtime knob is an env var
  validated by `pydantic-settings`.
- **Stable public surface.** Adding optional fields to `app/schemas.py`
  is fine; renaming or removing existing fields is a major-version bump.
- **Resilience through layering.** Even if the LLM is down, the FAQ
  responder still answers the top 10 election questions deterministically.

## How review works

PRs run the full CI matrix on Python 3.11 and 3.12, plus a Docker
build and a CodeQL scan. The merge bar is:

1. CI green on every check
2. Tests added or updated
3. Docstrings on new public callables
4. `CHANGELOG.md` updated under `[Unreleased]`
5. No new bandit, ruff, or mypy findings

`AGENTS.md` codifies the same rules for AI coding agents.

## Why this matters

Election information is high-stakes. The cost of a regression is not
a re-deploy — it is a citizen who showed up at the wrong polling
station, or a partisan response leaking through a quota retry.
Every checkbox above exists to prevent a category of bug we can't
afford to ship.
