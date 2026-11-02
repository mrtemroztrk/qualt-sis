from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import User
from library_reservations.models import LibraryBan, Reservation, StudyRoom
from library_reservations.rules import LIBRARY_TIME_ZONE


class ConcurrentBookingTests(TransactionTestCase):
    """Use separate PostgreSQL connections, not TestCase's shared transaction."""

    def setUp(self):
        self.now = datetime(2026, 11, 2, 7, tzinfo=LIBRARY_TIME_ZONE)
        clock = patch("django.utils.timezone.now", return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.student = User.objects.create_user(username="student", email="student@example.test", must_change_password=False)
        self.other = User.objects.create_user(username="other", email="other@example.test", must_change_password=False)
        self.admin = User.objects.create_user(username="admin", email="admin@example.test", role="ADMIN", must_change_password=False)
        self.room = StudyRoom.objects.create(name="Room A", location="First floor")
        self.other_room = StudyRoom.objects.create(name="Room B", location="First floor")

    def run_requests(self, requests):
        barrier = Barrier(len(requests))

        def perform(item):
            user_id, url, payload = item
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=user_id))
                barrier.wait(timeout=10)
                response = client.post(url, payload, format="json")
                return response.status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(requests)) as executor:
            futures = [executor.submit(perform, item) for item in requests]
            return [future.result(timeout=20) for future in futures]

    def booking(self, student, hour, room=None):
        return (student.pk, "/api/library/reservations/", {
            "room": (room or self.room).pk,
            "starts_at": (self.now + timedelta(hours=hour)).isoformat(),
        })

    def test_two_students_cannot_take_the_same_room_hour(self):
        results = self.run_requests([self.booking(self.student, 1), self.booking(self.other, 1)])
        self.assertEqual(sorted(results), [201, 409])
        self.assertEqual(Reservation.objects.filter(status="CONFIRMED").count(), 1)

    def test_parallel_requests_cannot_exceed_daily_limit_across_rooms(self):
        Reservation.objects.create(student=self.student, room=self.room, starts_at=self.now)
        results = self.run_requests([self.booking(self.student, 1), self.booking(self.student, 2, self.other_room)])
        self.assertEqual(sorted(results), [201, 409])
        self.assertEqual(Reservation.objects.filter(student=self.student, status="CONFIRMED").count(), 2)

    def test_parallel_requests_cannot_exceed_weekly_limit(self):
        for hour in [0, 1, 24, 25]:
            Reservation.objects.create(student=self.student, room=self.room, starts_at=self.now + timedelta(hours=hour))
        results = self.run_requests([self.booking(self.student, 48), self.booking(self.student, 72, self.other_room)])
        self.assertEqual(sorted(results), [201, 409])
        self.assertEqual(Reservation.objects.filter(student=self.student, status="CONFIRMED").count(), 5)

    def test_ban_and_booking_cannot_leave_a_future_reservation_active(self):
        results = self.run_requests([
            self.booking(self.student, 1),
            (self.admin.pk, "/api/library/admin/bans/", {"student": self.student.pk, "reason": "Library rules"}),
        ])
        self.assertIn(results[0], [201, 403])
        self.assertEqual(results[1], 201)
        self.assertTrue(LibraryBan.objects.filter(student=self.student, lifted_at__isnull=True).exists())
        self.assertFalse(Reservation.objects.filter(student=self.student, status="CONFIRMED").exists())
