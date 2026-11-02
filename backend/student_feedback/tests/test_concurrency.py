from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import User
from student_feedback.models import Feedback, SharingRequest


class ConsentConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.student = User.objects.create_user(username="student", email="student@example.test", must_change_password=False)
        self.teacher = User.objects.create_user(username="teacher", email="teacher@example.test", role="INSTRUCTOR", must_change_password=False)
        self.feedback = Feedback.objects.create(student=self.student, instructor=self.teacher, audience="INSTRUCTOR", title="Title", body="Body")
        self.conditions = {
            "visible_to_students": True, "visible_to_heads": False, "reveal_identity": False,
            "show_results_to_students": False, "show_comments_to_students": False,
        }
        self.proposal = SharingRequest.objects.create(
            feedback=self.feedback, instructor=self.teacher, state="APPROVED",
            student_conditions=self.conditions, **self.conditions,
        )

    def run_requests(self, requests):
        barrier = Barrier(len(requests))

        def perform(item):
            user_id, method, url, payload = item
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=user_id))
                barrier.wait(timeout=10)
                return getattr(client, method)(url, payload, format="json").status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(requests)) as executor:
            futures = [executor.submit(perform, item) for item in requests]
            return [future.result(timeout=20) for future in futures]

    def test_withdrawal_racing_publication_always_leaves_discussion_private(self):
        prefix = f"/api/feedback/sharing-requests/{self.proposal.pk}/"
        results = self.run_requests([
            (self.teacher.pk, "post", prefix + "publish/", {"accept_conditions": True}),
            (self.student.pk, "post", prefix + "withdraw/", {}),
        ])
        self.assertIn(results[0], [200, 409])
        self.assertEqual(results[1], 200)
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.state, "WITHDRAWN")

    def test_deletion_racing_publication_never_leaves_feedback_public(self):
        results = self.run_requests([
            (self.teacher.pk, "post", f"/api/feedback/sharing-requests/{self.proposal.pk}/publish/", {"accept_conditions": True}),
            (self.student.pk, "delete", f"/api/feedback/items/{self.feedback.pk}/", {}),
        ])
        self.assertIn(results[0], [200, 404])
        self.assertEqual(results[1], 204)
        self.proposal.refresh_from_db()
        self.feedback.refresh_from_db()
        self.assertEqual(self.proposal.state, "WITHDRAWN")
        self.assertIsNotNone(self.feedback.deleted_at)
