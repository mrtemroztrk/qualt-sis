from datetime import datetime
from unittest.mock import patch

from rest_framework.test import APITestCase

from accounts.models import User
from library_reservations.models import StudyRoom
from library_reservations.rules import LIBRARY_TIME_ZONE


class LibraryLoginTests(APITestCase):
    def setUp(self):
        clock = patch("django.utils.timezone.now", return_value=datetime(2026, 11, 2, 7, tzinfo=LIBRARY_TIME_ZONE))
        clock.start()
        self.addCleanup(clock.stop)
        self.password = "Initial-Library-482!"
        self.student = User.objects.create_user(username="student", email="student@example.test", password=self.password)
        self.room = StudyRoom.objects.create(name="Room A", location="First floor")

    def login(self):
        response = self.client.post("/api/auth/login/", {"email": self.student.email, "password": self.password})
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access"])
        return response.data

    def test_password_change_and_refresh_allow_booking_with_existing_login(self):
        self.login()
        self.assertEqual(self.client.get("/api/library/rooms/").status_code, 403)
        changed = self.client.post("/api/auth/change-password/", {
            "old_password": self.password, "new_password": "Updated-Library-937!",
        })
        self.assertEqual(changed.status_code, 200)
        self.password = "Updated-Library-937!"
        tokens = self.login()
        refreshed = self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(refreshed.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + refreshed.data["access"])
        response = self.client.post("/api/library/reservations/", {
            "room": self.room.pk, "starts_at": "2026-11-02T08:00:00+03:00",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.get("/api/library/reservations/mine/").data["count"], 1)

    def test_current_role_and_account_state_override_old_token(self):
        self.student.must_change_password = False
        self.student.save()
        self.login()
        self.student.role = User.Role.INSTRUCTOR
        self.student.save()
        self.assertEqual(self.client.get("/api/library/reservations/mine/").status_code, 403)
        self.assertEqual(self.client.get("/api/library/admin/reservations/").status_code, 403)
        self.student.is_active = False
        self.student.save()
        self.assertEqual(self.client.get("/api/library/rooms/").status_code, 401)

    def test_old_admin_token_does_not_keep_management_access_after_role_change(self):
        self.student.role = User.Role.ADMIN
        self.student.must_change_password = False
        self.student.save()
        self.login()
        self.assertEqual(self.client.get("/api/library/admin/reservations/").status_code, 200)
        self.student.role = User.Role.HEAD
        self.student.save()
        self.assertEqual(self.client.get("/api/library/admin/reservations/").status_code, 403)
