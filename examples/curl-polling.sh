#!/usr/bin/env bash
# Find polling-style venues near an address.
set -euo pipefail
: "${BASE_URL:=http://localhost:8080}"

curl -sS -X POST "$BASE_URL/api/polling-places" \
  -H 'Content-Type: application/json' \
  -d '{
    "address": "MG Road, Bengaluru",
    "radius_m": 5000
  }' | python3 -m json.tool
