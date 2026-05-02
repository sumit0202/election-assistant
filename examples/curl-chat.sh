#!/usr/bin/env bash
# Conversational chat — the primary entry point.
set -euo pipefail
: "${BASE_URL:=http://localhost:8080}"

curl -sS -X POST "$BASE_URL/api/chat" \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: example-chat-001' \
  -d '{
    "message": "How do I register as a first-time voter in India?",
    "session_id": "demo-session-001",
    "locale": "en",
    "location": "Bengaluru"
  }' | python3 -m json.tool
