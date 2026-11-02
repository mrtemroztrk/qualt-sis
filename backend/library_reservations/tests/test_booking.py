from datetime import datetime, timedelta
from unittest.mock import patch

from rest_framework.test import APITestCase

from accounts.models import User
from library_reservations.models import LibraryBan, Reservation, StudyRoom
from library_reservations.rules import LIBRARY_TIME_ZONE


class BookingTests(APITestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 2, 7, tzinfo=LIBRARY_TIME_ZONE)
        clock = patch("django.utils.timezone.now", return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.student = User.objects.create_user(
            username="student", email="student@example.test", must_change_password=False,
        )
        self.other = User.objects.create_user(
            username="other", email="other@example.test", must_change_password=False,
        )
        self.room = StudyRoom.objects.create(name="Room A", location="First floor")
        self.other_room = StudyRoom.objects.create(name="Room B", location="First floor")
        self.client.force_authenticate(self.student)

    def book(self, offset=1, room=None, **extra):
        return self.client.post("/api/library/reservations/", {
            "room": (room or self.room).pk,
            "starts_at": (self.now + timedelta(hours=offset)).isoformat(), **extra,
        }, format="json")

    def test_booking_is_one_hour_and_cannot_impersonate_a_student(self):
        response = self.book(student=self.other.pk, status="CANCELLED", ends_at="2099-01-01T00:00:00Z")
        self.assertEqual(response.status_code, 201)
        row = Reservation.objects.get(pk=response.data["id"])
        self.assertEqual(row.student, self.student)
        self.assertEqual(row.status, "CONFIRMED")
        self.assertEqual(row.ends_at - row.starts_at, timedelta(hours=1))

    def test_daily_limit_applies_across_different_rooms(self):
        self.assertEqual(self.book(1).status_code, 201)
        self.assertEqual(self.book(2, self.other_room).status_code, 201)
        response = self.book(3)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "daily_limit")

    def test_weekly_limit_includes_completed_hours(self):
        for offset in [0, 1, 24, 25, 48]:
            Reservation.objects.create(student=self.student, room=self.room, starts_at=self.now + timedelta(hours=offset))
        with patch("django.utils.timezone.now", return_value=self.now + timedelta(days=2, minutes=1)):
            response = self.book(49)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "weekly_limit")

    def test_room_and_student_overlap_are_rejected(self):
        self.book(1)
        self.assertEqual(self.book(1, self.other_room).data["code"], "overlap")
        self.client.force_authenticate(self.other)
        self.assertEqual(self.book(1).data["code"], "room_taken")

    def test_cancel_frees_room_and_allowance_and_keeps_a_record(self):
        first = self.book(1).data["id"]
        self.book(2)
        url = f"/api/library/reservations/{first}/cancel/"
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 200)
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 200)
        self.assertEqual(self.book(3).status_code, 201)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.book(1).status_code, 201)
        self.assertEqual(Reservation.objects.get(pk=first).status, "CANCELLED")

    def test_other_student_cannot_cancel_or_discover_a_reservation(self):
        row = self.book().data["id"]
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(f"/api/library/reservations/{row}/cancel/").status_code, 404)

    def test_started_booking_cannot_be_cancelled_to_reuse_allowance(self):
        row = Reservation.objects.create(student=self.student, room=self.room, starts_at=self.now - timedelta(hours=1))
        response = self.client.post(f"/api/library/reservations/{row.pk}/cancel/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "already_started")

    def test_invalid_times_offsets_and_future_weeks_are_rejected(self):
        values = [
            "2026-11-02T06:00:00+03:00", "2026-11-02T08:30:00+03:00",
            "2026-11-02T08:00:00", "2026-11-02T08:00:01+03:00",
            "2026-11-09T07:00:00+03:00", "invalid",
        ]
        for value in values:
            self.assertEqual(self.book(starts_at=value).status_code, 400, value)
        self.assertEqual(self.book(starts_at="2026-11-02T05:00:00Z").status_code, 201)

    def test_last_hour_of_week_can_be_reserved(self):
        self.assertEqual(self.book(starts_at="2026-11-09T06:00:00+03:00").status_code, 201)

    def test_monday_reset_does_not_reset_the_calendar_day_limit(self):
        for hour in [5, 6]:
            Reservation.objects.create(student=self.student, room=self.room, starts_at=self.now.replace(hour=hour))
        self.assertEqual(self.book().data["code"], "daily_limit")
        self.assertEqual(self.client.get("/api/library/summary/").data["weekly_used"], 0)

    def test_midnight_separates_daily_allowance(self):
        for value in ["2026-11-02T22:00:00+03:00", "2026-11-02T23:00:00+03:00", "2026-11-03T00:00:00+03:00"]:
            self.assertEqual(self.book(starts_at=value).status_code, 201)

    def test_ban_inactive_room_and_nonstudent_roles_cannot_book(self):
        self.room.is_active = False
        self.room.save()
        self.assertEqual(self.book().data["code"], "room_inactive")
        LibraryBan.objects.create(student=self.student, reason="Rules", created_by=self.other)
        self.assertEqual(self.book().status_code, 403)
        for role in [User.Role.INSTRUCTOR, User.Role.HEAD, User.Role.ADMIN]:
            self.student.role = role
            self.assertEqual(self.book().status_code, 403)
