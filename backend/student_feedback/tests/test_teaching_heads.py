from datetime import timedelta

from django.utils import timezone

from .base import FeedbackAPITestCase


class TeachingHeadTests(FeedbackAPITestCase):
    def send_to_head(self):
        self.client.force_authenticate(self.student)
        response = self.client.post("/api/feedback/items/", {
            "instructor": self.head.pk, "audience": "INSTRUCTOR",
            "title": "Teaching feedback", "body": "More examples would help.",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        return response.data["id"]

    def prepare_discussion(self, feedback_id):
        self.client.force_authenticate(self.head)
        response = self.client.post(f"/api/feedback/items/{feedback_id}/sharing-request/", {
            **self.conditions, "poll_question": "More examples?", "poll_options": ["Yes", "No"],
            "poll_closes_at": (timezone.now() + timedelta(days=1)).isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 201)
        pk = response.data["id"]
        self.assertEqual(self.respond(pk).status_code, 200)
        self.client.force_authenticate(self.head)
        self.assertEqual(self.client.post(f"/api/feedback/sharing-requests/{pk}/publish/", {
            "accept_conditions": True,
        }).status_code, 200)
        return pk

    def test_heads_are_available_as_active_teaching_recipients(self):
        self.client.force_authenticate(self.student)
        ids = [row["id"] for row in self.client.get("/api/feedback/instructors/").data["results"]]
        self.assertIn(self.head.pk, ids)
        self.head.is_active = False
        self.head.save()
        ids = [row["id"] for row in self.client.get("/api/feedback/instructors/").data["results"]]
        self.assertNotIn(self.head.pk, ids)

    def test_selected_head_can_publish_comment_and_inspect_votes(self):
        feedback_id = self.send_to_head()
        pk = self.prepare_discussion(feedback_id)
        self.assertEqual(self.client.get("/api/feedback/sharing-requests/").data["count"], 1)
        url = f"/api/feedback/discussions/{pk}/"
        self.assertEqual(self.client.post(url + "comments/", {"body": "Thanks for the suggestion."}).status_code, 201)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(url + "vote/", {"option": 0}).status_code, 200)
        self.client.force_authenticate(self.head)
        self.assertEqual(self.client.get(url).data["poll"]["results"]["total_votes"], 1)
        self.assertEqual(self.client.get(url + "votes/").data["results"][0]["student"]["id"], self.other.pk)
        self.assertEqual(self.client.post(f"/api/feedback/sharing-requests/{pk}/withdraw/").status_code, 200)

    def test_department_head_cannot_request_sharing_for_another_teacher(self):
        self.feedback.audience = "BOTH"
        self.feedback.save()
        self.client.force_authenticate(self.head)
        self.assertEqual(self.client.get(f"/api/feedback/items/{self.feedback.pk}/").status_code, 200)
        response = self.client.post(f"/api/feedback/items/{self.feedback.pk}/sharing-request/", self.conditions, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/api/feedback/sharing-requests/").data["count"], 0)

    def test_teaching_head_can_receive_feedback_from_another_department(self):
        from departments.models import Department

        self.head.department = Department.objects.create(code="EE", name="Electrical Engineering")
        self.head.save()
        feedback_id = self.send_to_head()
        self.client.force_authenticate(self.head)
        self.assertEqual(self.client.get(f"/api/feedback/items/{feedback_id}/").status_code, 200)
        self.prepare_discussion(feedback_id)

    def test_head_status_does_not_expose_unrelated_instructor_only_feedback(self):
        self.client.force_authenticate(self.head)
        self.assertEqual(self.client.get(f"/api/feedback/items/{self.feedback.pk}/").status_code, 404)
