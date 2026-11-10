from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from departments.models import Department
from student_feedback.models import Feedback


class FeedbackAPITestCase(APITestCase):
    def setUp(self):
        self.department = Department.objects.create(code="CSE", name="Computer Engineering")
        for name, role in [("student", "STUDENT"), ("other", "STUDENT"), ("teacher", "INSTRUCTOR"),
                           ("other_teacher", "INSTRUCTOR"), ("head", "HEAD"), ("admin", "ADMIN")]:
            setattr(self, name, User.objects.create_user(
                username=name, email=f"{name}@example.test", first_name=name,
                role=role, department=self.department if role != "ADMIN" else None, must_change_password=False,
            ))
        self.feedback = Feedback.objects.create(
            student=self.student, department=self.department, instructor=self.teacher, audience="INSTRUCTOR",
            title="Worked examples", body="Could we have more examples?", is_anonymous=True,
        )
        self.conditions = {
            "visible_to_students": True, "visible_to_heads": False, "reveal_identity": True,
            "show_results_to_students": False, "show_comments_to_students": False,
        }

    def share(self, **changes):
        self.client.force_authenticate(self.teacher)
        response = self.client.post(f"/api/feedback/items/{self.feedback.pk}/sharing-request/", {
            **self.conditions, "introduction": "What do you think?", "poll_question": "More examples?",
            "poll_options": ["Agree", "Disagree"], "poll_closes_at": (timezone.now() + timedelta(days=2)).isoformat(),
            **changes,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def respond(self, pk, action="approve", **extra):
        self.client.force_authenticate(self.student)
        return self.client.post(f"/api/feedback/sharing-requests/{pk}/respond/", {"action": action, **extra}, format="json")

    def publish(self, pk, **extra):
        self.client.force_authenticate(self.teacher)
        return self.client.post(f"/api/feedback/sharing-requests/{pk}/publish/", {"accept_conditions": True, **extra}, format="json")
