from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase, SimpleTestCase

from accounts.models import User
from library_reservations.models import LibraryBan, Reservation, StudyRoom
from library_reservations.rules import LIBRARY_TIME_ZONE, booking_window, day_bounds


class LibraryCalendarTests(SimpleTestCase):
    def test_monday_before_seven_belongs_to_previous_week(self):
        now = datetime(2026, 11, 2, 6, 59, tzinfo=LIBRARY_TIME_ZONE)
        start, end = booking_window(now)
        self.assertEqual(start.isoformat(), "2026-10-26T07:00:00+03:00")
        self.assertEqual(end.isoformat(), "2026-11-02T07:00:00+03:00")

    def test_monday_at_seven_opens_exactly_seven_days(self):
        now = datetime(2026, 11, 2, 7, tzinfo=LIBRARY_TIME_ZONE)
        start, end = booking_window(now)
        self.assertEqual(start, now)
        self.assertEqual(end, now + timedelta(days=7))

    def test_calendar_day_starts_at_midnight_not_week_reset(self):
        start, end = day_bounds(datetime(2026, 11, 2).date())
        self.assertEqual(start.hour, 0)
        self.assertEqual(end - start, timedelta(days=1))


class LibraryRecordTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username="student", email="student@example.test")
        self.other = User.objects.create_user(username="other", email="other@example.test")
        self.room = StudyRoom.objects.create(name="Room A", location="First floor")
        self.other_room = StudyRoom.objects.create(name="Room B", location="First floor")
        self.start = datetime(2026, 11, 2, 10, tzinfo=LIBRARY_TIME_ZONE)

    def test_room_cannot_be_reserved_twice_for_the_same_hour(self):
        Reservation.objects.create(student=self.student, room=self.room, starts_at=self.start)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reservation.objects.create(student=self.other, room=self.room, starts_at=self.start)

    def test_student_cannot_reserve_two_rooms_for_the_same_hour(self):
        Reservation.objects.create(student=self.student, room=self.room, starts_at=self.start)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reservation.objects.create(student=self.student, room=self.other_room, starts_at=self.start)

    def test_cancelled_reservation_keeps_history_and_releases_slot(self):
        cancelled = Reservation.objects.create(
            student=self.student, room=self.room, starts_at=self.start, status="CANCELLED",
            cancelled_at=self.start - timedelta(hours=1), cancelled_by=self.student,
        )
        current = Reservation.objects.create(student=self.other, room=self.room, starts_at=self.start)
        self.assertEqual(current.ends_at, self.start + timedelta(hours=1))
        self.assertNotEqual(cancelled.pk, current.pk)

    def test_only_one_active_ban_is_allowed(self):
        LibraryBan.objects.create(student=self.student, reason="Rule violation", created_by=self.other)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LibraryBan.objects.create(student=self.student, reason="Duplicate", created_by=self.other)
