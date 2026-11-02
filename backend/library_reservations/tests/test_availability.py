from datetime import datetime, timedelta
from unittest.mock import patch

from rest_framework.test import APITestCase

from accounts.models import User
from library_reservations.models import LibraryBan, Reservation, StudyRoom
from library_reservations.rules import LIBRARY_TIME_ZONE


class AvailabilityTests(APITestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 2, 7, tzinfo=LIBRARY_TIME_ZONE)
        clock = patch("django.utils.timezone.now", return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.student = User.objects.create_user(
            username="student", email="student@example.test", must_change_password=False,
        )
        self.other = User.objects.create_user(username="other", email="other@example.test")
        self.room = StudyRoom.objects.create(name="Room A", location="First floor")
        self.client.force_authenticate(self.student)

    def availability(self, day="2026-11-02"):
        return self.client.get("/api/library/availability/", {"room": self.room.pk, "date": day})

    def test_reset_day_contains_twenty_four_slots_but_hours_before_seven_are_closed(self):
        response = self.availability()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["slots"]), 24)
        self.assertFalse(response.data["slots"][6]["available"])
        self.assertTrue(response.data["slots"][7]["available"])
        self.assertEqual(response.data["weekly_remaining"], 5)

    def test_last_monday_only_allows_hours_before_seven(self):
        response = self.availability("2026-11-09")
        self.assertTrue(response.data["slots"][6]["available"])
        self.assertFalse(response.data["slots"][7]["available"])

    def test_weekend_and_overnight_hours_are_available(self):
        response = self.availability("2026-11-08")
        self.assertTrue(all(row["available"] for row in response.data["slots"]))

    def test_availability_does_not_disclose_other_students(self):
        Reservation.objects.create(student=self.other, room=self.room, starts_at=self.now)
        response = self.availability()
        self.assertEqual(response.data["slots"][7]["unavailable_reason"], "reserved")
        self.assertNotIn(self.other.email, response.content.decode())
        self.assertNotIn("student_id", response.content.decode())

    def test_mine_does_not_include_other_students_even_with_forged_filter(self):
        own = Reservation.objects.create(student=self.student, room=self.room, starts_at=self.now)
        Reservation.objects.create(student=self.other, room=self.room, starts_at=self.now + timedelta(hours=1))
        response = self.client.get("/api/library/reservations/mine/", {"student": self.other.pk})
        self.assertEqual([item["id"] for item in response.data["results"]], [own.pk])

    def test_instructors_heads_and_admins_cannot_use_student_endpoints(self):
        for role in [User.Role.INSTRUCTOR, User.Role.HEAD, User.Role.ADMIN]:
            self.student.role = role
            for path in ["rooms/", "summary/", "reservations/mine/"]:
                self.assertEqual(self.client.get("/api/library/" + path).status_code, 403)

    def test_anonymous_and_password_change_required_are_blocked(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/library/rooms/").status_code, 401)
        self.student.must_change_password = True
        self.client.force_authenticate(self.student)
        self.assertEqual(self.availability().status_code, 403)

    def test_inactive_rooms_and_invalid_dates_cannot_be_selected(self):
        self.room.is_active = False
        self.room.save()
        self.assertEqual(self.client.get("/api/library/rooms/").data["count"], 0)
        self.assertEqual(self.availability().data["slots"][7]["unavailable_reason"], "room_inactive")
        self.assertEqual(self.availability("2026-11-10").status_code, 400)
        self.assertEqual(self.availability("invalid").status_code, 400)

    def test_banned_student_can_still_view_summary_and_own_records(self):
        LibraryBan.objects.create(student=self.student, reason="Library rules", created_by=self.other)
        response = self.client.get("/api/library/summary/")
        self.assertTrue(response.data["is_banned"])
        self.assertEqual(self.availability().data["slots"][7]["unavailable_reason"], "banned")
        self.assertEqual(self.client.get("/api/library/reservations/mine/").status_code, 200)
