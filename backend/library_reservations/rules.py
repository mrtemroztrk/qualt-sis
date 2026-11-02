"""Library hours use Istanbul time without changing the rest of the project."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

LIBRARY_TIME_ZONE = ZoneInfo("Europe/Istanbul")
DAILY_LIMIT = 2
WEEKLY_LIMIT = 5
SLOT_LENGTH = timedelta(hours=1)


def booking_window(now=None):
    local_now = (now or timezone.now()).astimezone(LIBRARY_TIME_ZONE)
    monday = local_now.date() - timedelta(days=local_now.weekday())
    start = datetime.combine(monday, time(7), tzinfo=LIBRARY_TIME_ZONE)
    if local_now < start:
        start -= timedelta(days=7)
    return start, start + timedelta(days=7)


def day_bounds(day):
    start = datetime.combine(day, time.min, tzinfo=LIBRARY_TIME_ZONE)
    return start, start + timedelta(days=1)
