from datetime import UTC, datetime

from app.services.calendar_ics import build_reminder_ics


def test_builds_valid_ics_with_reminders():
    blob = build_reminder_ics(
        title="Polling day",
        description="Vote!",
        start=datetime(2026, 11, 5, 9, 0, tzinfo=UTC),
        duration_minutes=120,
        location="Booth 14",
    )
    text = blob.decode("utf-8")
    assert "BEGIN:VCALENDAR" in text
    assert "END:VCALENDAR" in text
    assert "SUMMARY:Polling day" in text
    assert "LOCATION:Booth 14" in text
    # Two VALARM blocks (1 day before + 1 hour before).
    assert text.count("BEGIN:VALARM") == 2
