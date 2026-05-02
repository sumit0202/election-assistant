#!/usr/bin/env bash
# Liveness probe — what Cloud Run health checks call.
set -euo pipefail
: "${BASE_URL:=http://localhost:8080}"

curl -sS -i "$BASE_URL/api/health"
