#!/usr/bin/env bash
set -euo pipefail

# Local dev runner. Loads .env and starts uvicorn with reload.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

if [[ ! -f .env ]]; then
  echo "No .env found — copying from .env.example. Edit it before running again."
  cp .env.example .env
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

PORT="${APP_PORT:-8080}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload
