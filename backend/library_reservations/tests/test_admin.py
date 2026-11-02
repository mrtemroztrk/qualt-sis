from datetime import datetime, timedelta
from unittest.mock import patch

from rest_framework.test import APITestCase

from accounts.models import User
from library_reservations.models import LibraryBan, Reservation, StudyRoom
from library_reservations.rules import LIBRARY_TIME_ZONE


class LibraryAdminTests(APITestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 2, 9, tzinfo=LIBRARY_TIME_ZONE)
        clock = patch("django.utils.timezone.now", return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.test", role=User.Role.ADMIN, must_change_password=False,
        )
        self.student = User.objects.create_user(
            username="student", email="student@example.test", must_change_password=False, student_no="1001",
        )
        self.room = StudyRoom.objects.create(name="Room A", location="First floor")
        self.row = Reservation.objects.create(student=self.student, room=self.room, starts_at=self.now + timedelta(hours=1))
        self.client.force_authenticate(self.admin)

    def ban(self):
        return self.client.post("/api/library/admin/bans/", {
            "student": self.student.pk, "reason": "Repeated library rule violations.",
        }, format="json")

    def test_only_admin_can_read_reservation_identities(self):
        response = self.client.get("/api/library/admin/reservations/")
        self.assertEqual(response.data["results"][0]["student"], self.student.pk)
        for role in [User.Role.STUDENT, User.Role.INSTRUCTOR, User.Role.HEAD]:
            self.student.role = role
            self.student.is_staff = True
            self.student.is_superuser = True
            self.client.force_authenticate(self.student)
            for path in ["reservations/", "rooms/", "bans/"]:
                self.assertEqual(self.client.get("/api/library/admin/" + path).status_code, 403)
            self.assertEqual(self.ban().status_code, 403)
            self.assertEqual(self.client.post(f"/api/library/admin/reservations/{self.row.pk}/cancel/", {"reason": "x"}).status_code, 403)
            self.assertEqual(self.client.post("/api/library/admin/bans/1/lift/").status_code, 403)

    def test_admin_can_create_update_and_deactivate_a_room_without_deleting_bookings(self):
        created = self.client.post("/api/library/admin/rooms/", {"name": "Room B", "location": "Second floor"})
        self.assertEqual(created.status_code, 201)
        url = f"/api/library/admin/rooms/{self.room.pk}/"
        self.assertEqual(self.client.patch(url, {"is_active": False}).status_code, 200)
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, "CONFIRMED")
        self.assertEqual(self.client.delete(url).status_code, 405)

    def test_admin_cancellation_requires_reason_and_records_actor(self):
        url = f"/api/library/admin/reservations/{self.row.pk}/cancel/"
        self.assertEqual(self.client.post(url, {}).status_code, 400)
        response = self.client.post(url, {"reason": "Room maintenance"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["cancelled_by"], self.admin.pk)
        self.assertEqual(response.data["cancellation_reason"], "Room maintenance")

    def test_ban_cancels_future_reservations_but_keeps_past_records(self):
        past = Reservation.objects.create(student=self.student, room=self.room, starts_at=self.now - timedelta(hours=1))
        response = self.ban()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["cancelled_reservations"], 1)
        self.row.refresh_from_db()
        past.refresh_from_db()
        self.assertEqual(self.row.status, "CANCELLED")
        self.assertEqual(self.row.cancelled_by, self.admin)
        self.assertEqual(past.status, "CONFIRMED")
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/announcements/official/").status_code, 200)
        self.assertTrue(self.client.get("/api/library/summary/").data["is_banned"])

    def test_lifting_ban_allows_new_bookings_without_restoring_cancelled_ones(self):
        ban_id = self.ban().data["ban"]["id"]
        url = f"/api/library/admin/bans/{ban_id}/lift/"
        self.assertFalse(self.client.post(url).data["is_active"])
        self.assertEqual(self.client.post(url).status_code, 200)
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, "CANCELLED")
        self.client.force_authenticate(self.student)
        result = self.client.post("/api/library/reservations/", {
            "room": self.room.pk, "starts_at": self.row.starts_at.isoformat(),
        })
        self.assertEqual(result.status_code, 201)

    def test_ban_history_is_kept_after_lifting_and_banning_again(self):
        first_id = self.ban().data["ban"]["id"]
        self.assertEqual(self.ban().status_code, 409)
        self.client.post(f"/api/library/admin/bans/{first_id}/lift/")
        self.assertEqual(self.ban().status_code, 201)
        self.assertEqual(LibraryBan.objects.filter(student=self.student).count(), 2)

    def test_nonstudents_missing_students_and_empty_ban_reasons_are_rejected(self):
        for payload, expected in [
            ({"student": self.admin.pk, "reason": "x"}, 400),
            ({"student": 99999, "reason": "x"}, 404),
            ({"student": self.student.pk, "reason": " "}, 400),
        ]:
            self.assertEqual(self.client.post("/api/library/admin/bans/", payload).status_code, expected)

    def test_admin_filters_apply_date_in_istanbul_time(self):
        Reservation.objects.create(student=self.student, room=self.room, starts_at=self.now.replace(day=3, hour=0))
        response = self.client.get("/api/library/admin/reservations/", {"date": "2026-11-03", "student": self.student.pk})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(self.client.get("/api/library/admin/reservations/", {"date": "invalid"}).status_code, 400)
