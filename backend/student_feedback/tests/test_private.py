from rest_framework.test import APITestCase

from accounts.models import User
from departments.models import Department
from student_feedback.models import Feedback


class PrivateFeedbackTests(APITestCase):
    def setUp(self):
        self.department = Department.objects.create(code="CSE", name="Computer Engineering")
        self.users = {}
        for name, role in [("student", "STUDENT"), ("other", "STUDENT"), ("teacher", "INSTRUCTOR"),
                           ("other_teacher", "INSTRUCTOR"), ("head", "HEAD"), ("admin", "ADMIN")]:
            self.users[name] = User.objects.create_user(
                username=name, email=f"{name}@example.test", first_name=name,
                role=role, department=self.department if role != "ADMIN" else None, must_change_password=False,
            )
        self.client.force_authenticate(self.users["student"])

    def create_feedback(self, **kwargs):
        payload = {"title": "Study support", "body": "More worked examples please.",
                   "audience": "INSTRUCTOR", "instructor": self.users["teacher"].pk, **kwargs}
        response = self.client.post("/api/feedback/items/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        return response.data["id"]

    def test_selected_recipient_only_and_admin_audit(self):
        pk = self.create_feedback()
        for name, expected in [("student", 200), ("teacher", 200), ("head", 404),
                               ("other", 404), ("other_teacher", 404), ("admin", 200)]:
            self.client.force_authenticate(self.users[name])
            self.assertEqual(self.client.get(f"/api/feedback/items/{pk}/").status_code, expected, name)

    def test_head_only_and_both_audiences(self):
        head_pk = self.create_feedback(audience="HEAD", instructor=None)
        both_pk = self.create_feedback(audience="BOTH")
        self.client.force_authenticate(self.users["head"])
        self.assertEqual(self.client.get("/api/feedback/items/").data["count"], 2)
        self.client.force_authenticate(self.users["teacher"])
        self.assertEqual(self.client.get(f"/api/feedback/items/{head_pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/feedback/items/{both_pk}/").status_code, 200)

    def test_anonymity_also_applies_to_private_student_replies(self):
        pk = self.create_feedback()
        url = f"/api/feedback/items/{pk}/replies/"
        self.client.post(url, {"body": "Here is another example."})
        self.client.force_authenticate(self.users["teacher"])
        self.assertIsNone(self.client.get(f"/api/feedback/items/{pk}/").data["student"]["id"])
        self.assertIsNone(self.client.get(url).data["results"][0]["author"]["id"])
        self.client.force_authenticate(self.users["admin"])
        self.assertEqual(self.client.get(url).data["results"][0]["author"]["id"], self.users["student"].pk)

    def test_identified_feedback_and_forged_owner(self):
        pk = self.create_feedback(is_anonymous=False, student=self.users["other"].pk)
        self.client.force_authenticate(self.users["teacher"])
        self.assertEqual(self.client.get(f"/api/feedback/items/{pk}/").data["student"]["id"], self.users["student"].pk)

    def test_only_owner_can_delete_and_only_admin_retains_audit_access(self):
        pk = self.create_feedback()
        url = f"/api/feedback/items/{pk}/"
        self.client.force_authenticate(self.users["other"])
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.client.force_authenticate(self.users["student"])
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.client.force_authenticate(self.users["teacher"])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url + "replies/", {"body": "Reply"}).status_code, 404)
        self.client.force_authenticate(self.users["admin"])
        self.assertIsNotNone(self.client.get(url).data["deleted_at"])
        self.assertTrue(Feedback.objects.filter(pk=pk).exists())

    def test_invalid_recipients_and_staff_creation_are_rejected(self):
        base = {"title": "Title", "body": "Body", "audience": "INSTRUCTOR"}
        self.assertEqual(self.client.post("/api/feedback/items/", base).status_code, 400)
        self.assertEqual(self.client.post("/api/feedback/items/", {**base, "instructor": self.users["student"].pk}).status_code, 400)
        self.client.force_authenticate(self.users["teacher"])
        self.assertEqual(self.client.post("/api/feedback/items/", base).status_code, 403)

    def test_directory_exposes_names_but_no_account_emails(self):
        response = self.client.get("/api/feedback/instructors/")
        self.assertEqual(response.data["count"], 3)
        self.assertNotIn("email", response.content.decode())
