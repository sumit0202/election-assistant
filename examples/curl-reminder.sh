#!/usr/bin/env bash
# Generate an .ics calendar reminder for a polling milestone.
set -euo pipefail
: "${BASE_URL:=http://localhost:8080}"

curl -sS -X POST "$BASE_URL/api/reminder.ics" \
  -H 'Content-Type: application/json' \
  -o "election-reminder.ics" \
  -d '{
    "title": "Maharashtra polling day",
    "description": "Carry voter ID. Polling 7 AM - 6 PM.",
    "start": "2026-11-05T09:00:00+05:30",
    "duration_minutes": 60,
    "location": "Booth #123"
  }'

echo "Saved election-reminder.ics — open it to add to your calendar."
