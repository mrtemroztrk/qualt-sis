from rest_framework.test import APITestCase

from accounts.models import User
from student_feedback.models import Feedback


class FeedbackLoginTests(APITestCase):
    def setUp(self):
        self.password = "Initial-Feedback-482!"
        self.student = User.objects.create_user(username="student", email="student@example.test", password=self.password)
        self.teacher = User.objects.create_user(username="teacher", email="teacher@example.test", role="INSTRUCTOR")

    def login(self):
        response = self.client.post("/api/auth/login/", {"email": self.student.email, "password": self.password})
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access"])
        return response.data

    def test_first_password_change_and_refresh_unlock_feedback(self):
        self.login()
        self.assertEqual(self.client.get("/api/feedback/items/").status_code, 403)
        changed = self.client.post("/api/auth/change-password/", {
            "old_password": self.password, "new_password": "Updated-Feedback-937!",
        })
        self.assertEqual(changed.status_code, 200)
        self.password = "Updated-Feedback-937!"
        tokens = self.login()
        refreshed = self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(refreshed.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + refreshed.data["access"])
        created = self.client.post("/api/feedback/items/", {"audience": "INSTRUCTOR", "instructor": self.teacher.pk,
                                                                   "title": "Examples", "body": "More examples please."})
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.data["is_anonymous"])
        self.assertEqual(self.client.get("/api/feedback/items/").data["count"], 1)

    def test_database_role_change_revokes_admin_audit_access_with_old_token(self):
        other = User.objects.create_user(username="other", email="other@example.test", role="STUDENT")
        feedback = Feedback.objects.create(student=other, audience="HEAD", title="Private", body="Private content")
        self.student.role = "ADMIN"
        self.student.must_change_password = False
        self.student.save()
        self.login()
        url = f"/api/feedback/items/{feedback.pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.student.role = "INSTRUCTOR"
        self.student.save()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.student.is_active = False
        self.student.save()
        self.assertEqual(self.client.get("/api/feedback/items/").status_code, 401)

    def test_anonymous_requests_cannot_access_any_feedback_channel(self):
        for path in ["items/", "instructors/", "sharing-requests/", "discussions/", "notifications/"]:
            self.assertEqual(self.client.get("/api/feedback/" + path).status_code, 401)
