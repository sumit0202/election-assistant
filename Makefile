# CivicGuide developer convenience targets.
# Run `make help` for the full list.

.DEFAULT_GOAL := help
SHELL := /bin/bash
PY ?= python3
VENV := .venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
BANDIT := $(VENV)/bin/bandit
MYPY := $(VENV)/bin/mypy
INTERROGATE := $(VENV)/bin/interrogate

.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | sort \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Create a venv and install dependencies
	$(PY) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install pytest==8.3.3 pytest-asyncio==0.24.0 pytest-cov==6.0.0 respx==0.21.1 hypothesis==6.115.6 \
	  ruff==0.6.9 'bandit[toml]==1.7.10' pip-audit==2.7.3 pre-commit mypy==1.13.0 interrogate==1.7.0

.PHONY: run
run: ## Run the dev server on port 8080
	./run.sh

.PHONY: test
test: ## Run the test suite (verbose)
	$(PYTEST) -v

.PHONY: cov
cov: ## Run tests with branch + line coverage report
	$(PYTEST) --cov=app --cov-report=term --cov-report=html

.PHONY: lint
lint: ## Run ruff + bandit checks (no fixes)
	$(RUFF) check .
	$(RUFF) format --check .
	$(BANDIT) -c pyproject.toml -r app -ll

.PHONY: typecheck
typecheck: ## Static type analysis with mypy
	$(MYPY) app

.PHONY: docstrings
docstrings: ## Verify docstring coverage >= 95%
	$(INTERROGATE) -c pyproject.toml app

.PHONY: fmt
fmt: ## Auto-fix style + formatting issues
	$(RUFF) check . --fix
	$(RUFF) format .

.PHONY: audit
audit: ## Audit installed dependencies for known CVEs
	$(VENV)/bin/pip-audit -r requirements.txt --strict

.PHONY: docker-build
docker-build: ## Build the production Docker image locally
	docker build -t civicguide:local .

.PHONY: docker-run
docker-run: docker-build ## Run the production image locally on :8080
	docker run --rm -p 8080:8080 --env-file .env civicguide:local

.PHONY: clean
clean: ## Remove caches, build artifacts, coverage data
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

.PHONY: ci
ci: lint docstrings test audit ## Run everything CI runs, locally
	@echo "All CI checks passed locally"
