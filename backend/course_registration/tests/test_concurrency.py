from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import User
from course_registration.models import RegistrationItem

from .base import CourseWorld


class ConcurrentSeatTests(CourseWorld, TransactionTestCase):
    """Use separate PostgreSQL connections, not TestCase's shared transaction."""

    def setUp(self):
        self.build_world()

    def run_posts(self, requests):
        barrier = Barrier(len(requests))

        def perform(item):
            user_id, url, payload = item
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=user_id))
                barrier.wait(timeout=10)
                return client.post(url, payload, format="json").status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(requests)) as executor:
            futures = [executor.submit(perform, item) for item in requests]
            return [future.result(timeout=20) for future in futures]

    def test_two_students_cannot_take_the_last_seat(self):
        self.section.quota = 1
        self.section.save()
        payload = {"section": self.section.pk}
        results = self.run_posts([
            (self.student.pk, "/api/registration/items/", payload),
            (self.other_student.pk, "/api/registration/items/", payload),
        ])
        self.assertEqual(sorted(results), [201, 409])
        self.assertEqual(RegistrationItem.objects.filter(section=self.section).count(), 1)

    def test_parallel_adds_cannot_exceed_the_credit_limit(self):
        self.term.max_credit = 6
        self.term.save()
        first = self.make_section(self.course("CSE 303", credit=3), meetings=[(2, 9, 12)])
        second = self.make_section(self.course("CSE 305", credit=3), meetings=[(3, 9, 12)])
        self.client_for(self.student).post("/api/registration/items/", {"section": self.section.pk}, format="json")
        results = self.run_posts([
            (self.student.pk, "/api/registration/items/", {"section": first.pk}),
            (self.student.pk, "/api/registration/items/", {"section": second.pk}),
        ])
        self.assertEqual(sorted(results), [201, 409])
        self.assertEqual(RegistrationItem.objects.filter(registration__student=self.student).count(), 2)
