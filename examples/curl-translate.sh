#!/usr/bin/env bash
# Translate text via Cloud Translation v3.
set -euo pipefail
: "${BASE_URL:=http://localhost:8080}"

curl -sS -X POST "$BASE_URL/api/translate" \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Polling stations are open from 7 AM to 6 PM.",
    "target": "hi",
    "source": "en"
  }' | python3 -m json.tool
