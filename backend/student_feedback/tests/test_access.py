from django.test import TestCase

from accounts.models import User
from student_feedback.access import author_identity, feedback_for
from student_feedback.models import Feedback


class FeedbackAccessTests(TestCase):
    def setUp(self):
        self.users = {}
        for role in ["STUDENT", "INSTRUCTOR", "HEAD", "ADMIN"]:
            self.users[role] = User.objects.create_user(username=role, email=f"{role}@example.test", role=role)
        self.feedback = Feedback.objects.create(
            student=self.users["STUDENT"], instructor=self.users["INSTRUCTOR"],
            audience="INSTRUCTOR", title="Study support", body="Could we have more examples?",
        )

    def test_instructor_only_excludes_head_but_admin_can_audit(self):
        self.assertTrue(feedback_for(self.users["INSTRUCTOR"]).exists())
        self.assertFalse(feedback_for(self.users["HEAD"]).exists())
        self.assertTrue(feedback_for(self.users["ADMIN"]).exists())

    def test_anonymous_identity_is_hidden_except_for_author_and_admin(self):
        student = self.users["STUDENT"]
        self.assertIsNone(author_identity(student, self.users["INSTRUCTOR"], hide=True)["id"])
        self.assertEqual(author_identity(student, self.users["ADMIN"], hide=True)["id"], student.pk)
        self.assertEqual(author_identity(student, student, hide=True)["id"], student.pk)
