from datetime import timedelta

from rest_framework.exceptions import ValidationError

from .models import LibraryBan, Reservation
from .rules import DAILY_LIMIT, WEEKLY_LIMIT, SLOT_LENGTH, booking_window, day_bounds


def confirmed_reservations(student):
    return Reservation.objects.filter(student=student, status=Reservation.Status.CONFIRMED)


def student_summary(student, now):
    start, end = booking_window(now)
    used = confirmed_reservations(student).filter(starts_at__gte=start, starts_at__lt=end).count()
    ban = LibraryBan.objects.filter(student=student, lifted_at__isnull=True).first()
    return {
        "time_zone": "Europe/Istanbul", "server_time": now,
        "window_start": start, "window_end": end,
        "slot_minutes": 60, "daily_limit": DAILY_LIMIT, "weekly_limit": WEEKLY_LIMIT,
        "weekly_used": used, "weekly_remaining": max(0, WEEKLY_LIMIT - used),
        "is_banned": ban is not None, "ban_reason": ban.reason if ban else None,
    }


def room_availability(student, room, day, now):
    summary = student_summary(student, now)
    start, end = day_bounds(day)
    if end <= summary["window_start"] or start >= summary["window_end"]:
        raise ValidationError({"date": "Choose a date in the current booking week."})
    own_hours = set(confirmed_reservations(student).filter(
        starts_at__gte=start, starts_at__lt=end,
    ).values_list("starts_at", flat=True))
    reserved_hours = set(Reservation.objects.filter(
        room=room, status=Reservation.Status.CONFIRMED, starts_at__gte=start, starts_at__lt=end,
    ).values_list("starts_at", flat=True))
    slots = []
    for hour in range(24):
        slot_start = start + timedelta(hours=hour)
        reason = None
        if slot_start < summary["window_start"] or slot_start + SLOT_LENGTH > summary["window_end"]:
            reason = "outside_window"
        elif slot_start < now:
            reason = "past"
        elif not room.is_active:
            reason = "room_inactive"
        elif slot_start in reserved_hours:
            reason = "reserved"
        elif summary["is_banned"]:
            reason = "banned"
        elif slot_start in own_hours:
            reason = "overlap"
        elif len(own_hours) >= DAILY_LIMIT:
            reason = "daily_limit"
        elif summary["weekly_remaining"] == 0:
            reason = "weekly_limit"
        slots.append({
            "starts_at": slot_start, "ends_at": slot_start + SLOT_LENGTH,
            "available": reason is None, "unavailable_reason": reason,
        })
    return {
        **summary, "room_id": room.pk, "date": day,
        "daily_used": len(own_hours), "daily_remaining": max(0, DAILY_LIMIT - len(own_hours)),
        "slots": slots,
    }
