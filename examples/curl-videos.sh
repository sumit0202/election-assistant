#!/usr/bin/env bash
# Search YouTube for trusted election explainer videos.
set -euo pipefail
: "${BASE_URL:=http://localhost:8080}"

curl -sS -X POST "$BASE_URL/api/videos" \
  -H 'Content-Type: application/json' \
  -d '{
    "topic": "EVM and VVPAT",
    "locale": "en",
    "max_results": 5
  }' | python3 -m json.tool
