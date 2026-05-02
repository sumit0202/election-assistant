"""Standards-based ICS generator for election reminders.

Producing an `.ics` file means the reminder works in **any** calendar app
(Google Calendar, Apple Calendar, Outlook) without needing a logged-in
Google account or OAuth flow — far simpler and safer for the user.
Google Calendar imports `.ics` files natively at calendar.google.com.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from icalendar import Calendar, Event


def build_reminder_ics(
    *,
    title: str,
    description: str,
    start: datetime,
    duration_minutes: int = 60,
    location: str | None = None,
) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Election Assistant//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")

    event = Event()
    event.add("summary", title)
    event.add("description", description)
    event.add("dtstart", start)
    event.add("dtend", start + timedelta(minutes=duration_minutes))
    event.add("dtstamp", datetime.now(UTC))
    event["uid"] = f"{uuid4()}@election-assistant"
    if location:
        event.add("location", location)
    # Reminder 1 day and 1 hour before.
    from icalendar import Alarm

    for delta_minutes, label in ((1440, "1 day before"), (60, "1 hour before")):
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", f"Reminder: {title} ({label})")
        alarm.add("trigger", timedelta(minutes=-delta_minutes))
        event.add_component(alarm)

    cal.add_component(event)
    return cal.to_ical()
