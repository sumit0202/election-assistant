# Contributing to CivicGuide

Thanks for your interest! This project favours small, focused PRs and
prefers boring-but-correct over clever-but-fragile.

## Local development

```bash
git clone https://github.com/<you>/election-assistant
cd election-assistant
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in at least GEMINI_API_KEY
./run.sh
# open http://localhost:8080
```

## Running the test suite

```bash
pytest -q                                  # all tests
pytest -q --cov=app --cov-report=term      # with coverage
pytest -q tests/test_safety.py             # one file
pytest -k faq                              # by keyword
```

The suite is **fully offline** — no real Google API calls. Maps is mocked
with `respx`, the LLM is mocked with a small `FakeGemini` class.

## Code style

- **Python**: PEP 8 + type hints. Run `ruff check .` and `ruff format .`
  before committing.
- **JavaScript**: vanilla ES modules, no framework, 2-space indent.
- **Docstrings** on every public function/class. Module docstrings explain
  *why*, not just *what*.
- Avoid comments that narrate code mechanically. Comments should record
  intent, trade-offs, or non-obvious constraints.

## Pre-commit hooks (recommended)

```bash
pip install pre-commit
pre-commit install
```

This wires up `ruff`, `mypy --strict` (where applicable), and basic file
hygiene checks before every commit.

## Branching model

- Single `main` branch is the source of truth.
- Open PRs against `main` from short-lived feature branches.
- Squash-merge to keep history linear.

## Commit message style

```
<scope>: <imperative summary in <72 chars>

Optional body explaining *why* the change was needed. Wrap at 72 chars.
Reference issues like #123 if relevant.
```

Examples:

```
agent: short-circuit FAQ before invoking Gemini
safety: redact Aadhaar + PAN before LLM call
maps: use haversine distance for stable sort order
```

## Adding a new FAQ entry

`app/data/faq.json` holds the curated Q&A. Each entry:

```json
{
  "id": "kebab-case-id",
  "keywords": ["voter", "register", "form 6"],
  "title": "Short, search-engine-style title",
  "answer": "Markdown body. Cite eci.gov.in for region-specific rules."
}
```

Run `pytest tests/test_faq.py -q` after adding to confirm match scoring.

## Adding a new Google service

1. Add a thin facade under `app/services/<name>.py` exposing an
   `async`-friendly method.
2. Wire it in `app/main.py`'s `lifespan()`.
3. Inject it into `ElectionAgent` via `AgentDeps` if the agent needs it.
4. Add HTTP-level mocks in a new `tests/test_<name>.py`.
5. Document the IAM role / key needed in `README.md`.

## Reporting security issues

Please don't open a public issue for vulnerabilities — see `SECURITY.md`.

## Scope

This is a non-partisan **education** tool. PRs that add candidate
recommendation, polling-prediction, or partisan content will be declined.
