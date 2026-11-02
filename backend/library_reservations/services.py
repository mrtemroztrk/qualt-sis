"""Reservation writes share one transaction and lock order: student, then room."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from accounts.models import User

from .availability import confirmed_reservations
from .models import LibraryBan, Reservation, StudyRoom
from .rules import DAILY_LIMIT, WEEKLY_LIMIT, LIBRARY_TIME_ZONE, SLOT_LENGTH, booking_window, day_bounds


class ReservationConflict(APIException):
    status_code = 409

    def __init__(self, code, message):
        super().__init__({"code": code, "detail": message})


@transaction.atomic
def book_room(student_id, room_id, starts_at):
    # This also serializes bookings in different rooms by the same student.
    student = get_object_or_404(User.objects.select_for_update(), pk=student_id)
    if not student.is_active or student.must_change_password or student.role != User.Role.STUDENT:
        raise PermissionDenied("Only eligible student accounts can reserve a room.")
    room = get_object_or_404(StudyRoom.objects.select_for_update(), pk=room_id)
    now = timezone.now()
    local_start = starts_at.astimezone(LIBRARY_TIME_ZONE)
    window_start, window_end = booking_window(now)
    if local_start.minute or local_start.second or local_start.microsecond:
        raise ValidationError({"starts_at": "Choose a full hour, such as 10:00."})
    if starts_at < now or starts_at < window_start or starts_at + SLOT_LENGTH > window_end:
        raise ValidationError({"starts_at": "Choose a future hour in the current booking week."})
    if LibraryBan.objects.filter(student=student, lifted_at__isnull=True).exists():
        raise PermissionDenied({"code": "library_ban", "detail": "Library reservations are blocked for your account."})
    if not room.is_active:
        raise ReservationConflict("room_inactive", "This room is not accepting new reservations.")
    if Reservation.objects.filter(room=room, starts_at=starts_at, status=Reservation.Status.CONFIRMED).exists():
        raise ReservationConflict("room_taken", "This room has already been reserved for that hour.")
    own = confirmed_reservations(student)
    if own.filter(starts_at=starts_at).exists():
        raise ReservationConflict("overlap", "You already have a reservation for that hour.")
    day_start, day_end = day_bounds(local_start.date())
    if own.filter(starts_at__gte=day_start, starts_at__lt=day_end).count() >= DAILY_LIMIT:
        raise ReservationConflict("daily_limit", "You can reserve at most two hours per calendar day.")
    if own.filter(starts_at__gte=window_start, starts_at__lt=window_end).count() >= WEEKLY_LIMIT:
        raise ReservationConflict("weekly_limit", "You can reserve at most five hours per booking week.")
    return Reservation.objects.create(student=student, room=room, starts_at=starts_at)


@transaction.atomic
def cancel_reservation(reservation_id, actor, reason=""):
    visible = Reservation.objects.all()
    if actor.role != User.Role.ADMIN:
        visible = visible.filter(student=actor)
    reservation = get_object_or_404(visible, pk=reservation_id)
    # Use the same lock as booking and banning, before reading the current state.
    User.objects.select_for_update().get(pk=reservation.student_id)
    reservation = Reservation.objects.select_related("room").get(pk=reservation_id)
    if reservation.status == Reservation.Status.CANCELLED:
        return reservation
    now = timezone.now()
    if reservation.starts_at < now:
        raise ReservationConflict("already_started", "A reservation cannot be cancelled after it starts.")
    reservation.status = Reservation.Status.CANCELLED
    reservation.cancelled_at = now
    reservation.cancelled_by = actor
    reservation.cancellation_reason = reason
    reservation.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancellation_reason"])
    return reservation


@transaction.atomic
def ban_student(student_id, actor, reason):
    student = get_object_or_404(User.objects.select_for_update(), pk=student_id)
    if student.role != User.Role.STUDENT:
        raise ValidationError({"student": "Choose a student account."})
    if LibraryBan.objects.filter(student=student, lifted_at__isnull=True).exists():
        raise ReservationConflict("already_banned", "This student already has an active library ban.")
    ban = LibraryBan.objects.create(student=student, reason=reason, created_by=actor)
    now = timezone.now()
    cancelled_count = confirmed_reservations(student).filter(starts_at__gte=now).update(
        status=Reservation.Status.CANCELLED, cancelled_at=now, cancelled_by=actor,
        cancellation_reason="Cancelled because of a library ban.",
    )
    return ban, cancelled_count


@transaction.atomic
def lift_ban(ban_id, actor):
    ban = get_object_or_404(LibraryBan, pk=ban_id)
    User.objects.select_for_update().get(pk=ban.student_id)
    ban.refresh_from_db()
    if ban.lifted_at is None:
        ban.lifted_at = timezone.now()
        ban.lifted_by = actor
        ban.save(update_fields=["lifted_at", "lifted_by"])
    # Cancelled reservations are not restored when the ban is lifted.
    return ban
