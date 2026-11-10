from django.db.models.deletion import ProtectedError

from accounts.models import User
from departments.models import Department
from student_feedback.models import Feedback, FeedbackNotification
from .base import FeedbackAPITestCase


class FeedbackDepartmentTests(FeedbackAPITestCase):
    def setUp(self):
        super().setUp()
        self.other_department = Department.objects.create(code="EE", name="Electrical Engineering")
        self.foreign_student = self.member("foreign_student", "STUDENT", self.other_department)
        self.foreign_head = self.member("foreign_head", "HEAD", self.other_department)
        self.unassigned_head = self.member("unassigned_head", "HEAD")
        self.unassigned_student = self.member("unassigned_student", "STUDENT")

    def member(self, name, role, department=None):
        return User.objects.create_user(
            username=name, email=f"{name}@example.test", role=role,
            department=department, must_change_password=False,
        )

    def create(self, **values):
        return self.client.post("/api/feedback/items/", {
            "title": "Study support", "body": "More examples.", "audience": "BOTH",
            "instructor": self.teacher.pk, **values,
        }, format="json")

    def published(self, **conditions):
        pk = self.share(visible_to_heads=True, **conditions)
        self.assertEqual(self.respond(pk).status_code, 200)
        self.assertEqual(self.publish(pk).status_code, 200)
        return pk

    def test_department_comes_from_the_student_and_cannot_be_forged(self):
        self.client.force_authenticate(self.student)
        response = self.create(department=self.other_department.pk)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["department"], self.department.pk)
        self.assertEqual(response.data["department_name"], self.department.name)
        with self.assertRaises(ProtectedError):
            self.department.delete()

    def test_only_the_same_departments_heads_receive_private_feedback_and_notifications(self):
        self.client.force_authenticate(self.student)
        pk = self.create().data["id"]
        item = f"/api/feedback/items/{pk}/"
        self.assertEqual(set(FeedbackNotification.objects.filter(feedback_id=pk).values_list("recipient_id", flat=True)),
                         {self.teacher.pk, self.head.pk})
        for actor, expected in [(self.head, 200), (self.foreign_head, 404), (self.unassigned_head, 404), (self.admin, 200)]:
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.get(item).status_code, expected)
            self.assertEqual(self.client.get(item + "replies/").status_code, expected)
            if expected == 404:
                self.assertEqual(self.client.post(item + "replies/", {"body": "Guessing the ID"}).status_code, 404)
        self.client.force_authenticate(self.foreign_head)
        self.assertEqual(self.client.get("/api/feedback/items/").data["count"], 0)

    def test_foreign_students_and_heads_cannot_read_comment_or_vote_on_a_discussion(self):
        pk = self.published(show_comments_to_students=True)
        url = f"/api/feedback/discussions/{pk}/"
        for actor in [self.foreign_student, self.foreign_head, self.unassigned_student, self.unassigned_head]:
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.get("/api/feedback/discussions/").data["count"], 0)
            for suffix in ["", "comments/", "votes/"]:
                self.assertEqual(self.client.get(url + suffix).status_code, 404)
            self.assertEqual(self.client.post(url + "comments/", {"body": "Out of scope"}).status_code, 404)
        self.client.force_authenticate(self.foreign_student)
        self.assertEqual(self.client.post(url + "vote/", {"option": 0}).status_code, 404)
        for actor in [self.other, self.head, self.admin]:
            self.client.force_authenticate(actor)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["department"], self.department.pk)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(url + "vote/", {"option": 0}).status_code, 200)

    def test_student_transfer_does_not_move_the_conversation_or_approved_audience(self):
        self.feedback.audience = "BOTH"
        self.feedback.save()
        pk = self.published()
        self.student.department = self.other_department
        self.student.save()
        self.feedback.refresh_from_db()
        self.assertEqual(self.feedback.department_id, self.department.pk)
        for actor, expected in [(self.student, 200), (self.other, 200), (self.head, 200),
                                (self.foreign_student, 404), (self.foreign_head, 404)]:
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.get(f"/api/feedback/discussions/{pk}/").status_code, expected)
        self.client.force_authenticate(self.foreign_head)
        self.assertEqual(self.client.get(f"/api/feedback/items/{self.feedback.pk}/").status_code, 404)

    def test_hidden_student_audience_stays_hidden_inside_the_department(self):
        pk = self.published(visible_to_students=False)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/feedback/discussions/{pk}/").status_code, 404)
        self.client.force_authenticate(self.head)
        self.assertEqual(self.client.get(f"/api/feedback/discussions/{pk}/").status_code, 200)

    def test_old_head_notifications_follow_current_access_including_mark_read(self):
        self.client.force_authenticate(self.student)
        pk = self.create().data["id"]
        notification = FeedbackNotification.objects.get(feedback_id=pk, recipient=self.head)
        self.head.department = self.other_department
        self.head.save()
        self.client.force_authenticate(self.head)
        self.assertEqual(self.client.get("/api/feedback/notifications/").data["count"], 0)
        self.assertEqual(self.client.post(f"/api/feedback/notifications/{notification.pk}/read/").status_code, 404)

    def test_missing_or_inactive_department_blocks_new_feedback(self):
        self.client.force_authenticate(self.unassigned_student)
        self.assertEqual(self.create().status_code, 400)
        self.department.is_active = False
        self.department.save()
        self.client.force_authenticate(self.student)
        self.assertEqual(self.create().status_code, 400)

    def test_legacy_feedback_is_preserved_for_author_instructor_and_admin(self):
        legacy = Feedback.objects.create(student=self.student, instructor=self.teacher, audience="BOTH", title="Legacy", body="Keep this.")
        url = f"/api/feedback/items/{legacy.pk}/"
        for actor, expected in [(self.student, 200), (self.teacher, 200), (self.admin, 200),
                                (self.head, 404), (self.foreign_head, 404), (self.unassigned_head, 404)]:
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.get(url).status_code, expected)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post(url + "sharing-request/", self.conditions, format="json").status_code, 400)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(url, {"department": self.department.pk}, format="json").status_code, 200)
        legacy.refresh_from_db()
        self.assertEqual(legacy.body, "Keep this.")
        self.client.force_authenticate(self.head)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_legacy_assignment_cannot_edit_content_or_move_existing_records(self):
        url = f"/api/feedback/items/{self.feedback.pk}/"
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(url, {"department": self.other_department.pk}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"department": self.department.pk, "body": "Changed"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"department": None}, format="json").status_code, 400)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.patch(url, {"department": self.other_department.pk}, format="json").status_code, 403)

    def test_selected_instructor_can_teach_in_another_department(self):
        # Poyraz's catalog permits cross-department teaching, including electives.
        self.teacher.department = self.other_department
        self.teacher.save()
        self.client.force_authenticate(self.student)
        pk = self.create().data["id"]
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get(f"/api/feedback/items/{pk}/").status_code, 200)
