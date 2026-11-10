from decimal import Decimal

from django.test import TestCase

from course_registration.models import Registration, RegistrationItem
from course_registration.tests.base import CourseWorld
from grades.models import Grade, GradingComponent

BASE = "/api/grades/teaching"


class TeachingWorld(CourseWorld):
    """The CourseWorld section, taught by self.advisor, with two approved students and one draft."""

    def build_grading_world(self):
        self.build_world()
        self.drafting = self.user(
            "s3@example.test", "STUDENT", department=self.cse, advisor=self.advisor, student_no="1003", class_year=3,
        )
        self.enroll(self.student)
        self.enroll(self.other_student)
        self.enroll(self.drafting, approved=False)
        self.client = self.client_for(self.advisor)

    def enroll(self, student, approved=True):
        registration = Registration.objects.create(
            student=student,
            term=self.term,
            status=Registration.Status.APPROVED if approved else Registration.Status.DRAFT,
            approved_items=[{"section": self.section.pk, "is_retake": False}] if approved else [],
        )
        RegistrationItem.objects.create(registration=registration, section=self.section)
        return registration

    def components_url(self, section=None):
        return f"{BASE}/sections/{(section or self.section).pk}/components/"

    def component(self, name="Midterm", weight="30", kind="MIDTERM", max_score="100"):
        return GradingComponent.objects.create(
            section=self.section, kind=kind, name=name, weight=Decimal(weight), max_score=Decimal(max_score),
        )

    def post_grades(self, component, rows, client=None):
        return (client or self.client).post(
            f"{BASE}/components/{component.pk}/grades/", {"grades": rows}, format="json",
        )


class ComponentTests(TeachingWorld, TestCase):
    def setUp(self):
        self.build_grading_world()

    def test_instructor_creates_a_component_for_their_section(self):
        response = self.client.post(self.components_url(), {
            "kind": "MIDTERM", "name": " Midterm ", "weight": "30", "display_order": 1,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        created = GradingComponent.objects.get()
        self.assertEqual((created.section, created.name, created.weight), (self.section, "Midterm", Decimal("30")))
        self.assertEqual(response.data["max_score"], "100.00")
        self.assertFalse(response.data["is_published"])
        self.assertEqual(response.data["grade_count"], 0)

    def test_instructor_lists_their_sections_components(self):
        self.component("Final", "70", "FINAL")
        self.component("Midterm", "30")
        names = [row["name"] for row in self.client.get(self.components_url()).data]
        self.assertEqual(sorted(names), ["Final", "Midterm"])

    def test_component_names_are_unique_in_a_section(self):
        self.component("Midterm", "30")
        response = self.client.post(self.components_url(), {"name": "midterm", "weight": "10"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)

    def test_weights_cannot_exceed_one_hundred_percent(self):
        self.component("Midterm", "60")
        response = self.client.post(self.components_url(), {"name": "Final", "weight": "50"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("weight", response.data)
        self.assertEqual(GradingComponent.objects.count(), 1)

    def test_weights_can_be_rebalanced(self):
        midterm = self.component("Midterm", "60")
        self.component("Final", "40", "FINAL")
        response = self.client.patch(f"{BASE}/components/{midterm.pk}/", {"weight": "30"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        midterm.refresh_from_db()
        self.assertEqual(midterm.weight, Decimal("30"))

    def test_other_instructors_and_heads_see_404(self):
        midterm = self.component()
        for user in (self.other_instructor, self.head):
            client = self.client_for(user)
            with self.subTest(user=user.email):
                self.assertEqual(client.get(self.components_url()).status_code, 404)
                self.assertEqual(client.get(f"{BASE}/components/{midterm.pk}/").status_code, 404)
                self.assertEqual(client.get(f"{BASE}/sections/{self.section.pk}/sheet/").status_code, 404)

    def test_head_who_teaches_the_section_can_grade_it(self):
        self.section.instructor = self.head
        self.section.save()
        response = self.client_for(self.head).post(self.components_url(), {"name": "Midterm", "weight": "40"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def test_students_and_admins_cannot_use_teaching_endpoints(self):
        for user in (self.student, self.admin):
            with self.subTest(user=user.email):
                self.assertEqual(self.client_for(user).get(self.components_url()).status_code, 403)

    def test_max_score_cannot_drop_below_an_existing_grade(self):
        midterm = self.component()
        Grade.objects.create(component=midterm, student=self.student, score=Decimal("85"))
        response = self.client.patch(f"{BASE}/components/{midterm.pk}/", {"max_score": "80"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("max_score", response.data)

    def test_component_without_grades_can_be_deleted(self):
        midterm = self.component()
        self.assertEqual(self.client.delete(f"{BASE}/components/{midterm.pk}/").status_code, 204)
        self.assertFalse(GradingComponent.objects.exists())

    def test_component_with_grades_cannot_be_deleted(self):
        midterm = self.component()
        Grade.objects.create(component=midterm, student=self.student, score=Decimal("85"))
        response = self.client.delete(f"{BASE}/components/{midterm.pk}/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "has_grades")


class GradeEntryTests(TeachingWorld, TestCase):
    def setUp(self):
        self.build_grading_world()
        self.midterm = self.component("Midterm", "30")

    def test_instructor_enters_a_batch_of_grades(self):
        response = self.post_grades(self.midterm, [
            {"student": self.student.pk, "score": "85"},
            {"student": self.other_student.pk, "score": "72.5"},
        ])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["missing_grades"], 0)
        scores = dict(Grade.objects.values_list("student_id", "score"))
        self.assertEqual(scores, {self.student.pk: Decimal("85"), self.other_student.pk: Decimal("72.5")})
        self.assertEqual(set(Grade.objects.values_list("entered_by_id", flat=True)), {self.advisor.pk})

    def test_entering_again_updates_the_grade(self):
        self.post_grades(self.midterm, [{"student": self.student.pk, "score": "60"}])
        self.post_grades(self.midterm, [{"student": self.student.pk, "score": "65"}])
        self.assertEqual(Grade.objects.get(student=self.student).score, Decimal("65"))
        self.assertEqual(Grade.objects.count(), 1)

    def test_null_score_removes_the_grade(self):
        self.post_grades(self.midterm, [{"student": self.student.pk, "score": "60"}])
        response = self.post_grades(self.midterm, [{"student": self.student.pk, "score": None}])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Grade.objects.exists())

    def test_students_without_an_approved_form_cannot_be_graded(self):
        response = self.post_grades(self.midterm, [
            {"student": self.student.pk, "score": "85"},
            {"student": self.drafting.pk, "score": "90"},
        ])
        self.assertEqual(response.status_code, 400)
        self.assertIn("1", response.data["grades"])
        # The batch is all or nothing.
        self.assertFalse(Grade.objects.exists())

    def test_score_cannot_exceed_the_maximum(self):
        quiz = self.component("Quiz", "10", "QUIZ", max_score="20")
        response = self.post_grades(quiz, [{"student": self.student.pk, "score": "25"}])
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Grade.objects.exists())

    def test_a_student_appears_once_per_batch(self):
        response = self.post_grades(self.midterm, [
            {"student": self.student.pk, "score": "50"},
            {"student": self.student.pk, "score": "60"},
        ])
        self.assertEqual(response.status_code, 400)

    def test_negative_and_empty_batches_are_rejected(self):
        self.assertEqual(self.post_grades(self.midterm, [{"student": self.student.pk, "score": "-1"}]).status_code, 400)
        self.assertEqual(self.post_grades(self.midterm, []).status_code, 400)

    def test_other_instructors_cannot_grade(self):
        response = self.post_grades(
            self.midterm, [{"student": self.student.pk, "score": "85"}], client=self.client_for(self.other_instructor),
        )
        self.assertEqual(response.status_code, 404)

    def test_sheet_shows_graded_students_and_their_scores(self):
        final = self.component("Final", "70", "FINAL")
        self.post_grades(self.midterm, [{"student": self.student.pk, "score": "85"}])
        response = self.client.get(f"{BASE}/sections/{self.section.pk}/sheet/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["weight_total"], "100.00")
        self.assertEqual([c["name"] for c in response.data["components"]], ["Midterm", "Final"])
        rows = {row["id"]: row["grades"] for row in response.data["students"]}
        # The student still drafting their form is not on the sheet.
        self.assertEqual(set(rows), {self.student.pk, self.other_student.pk})
        self.assertEqual(rows[self.student.pk], {str(self.midterm.pk): "85.00", str(final.pk): None})
        self.assertEqual(rows[self.other_student.pk], {str(self.midterm.pk): None, str(final.pk): None})


class PublishTests(TeachingWorld, TestCase):
    def setUp(self):
        self.build_grading_world()
        self.midterm = self.component("Midterm", "30")

    def publish(self, component):
        return self.client.post(f"{BASE}/components/{component.pk}/publish/")

    def test_publishing_needs_weights_adding_up_to_one_hundred(self):
        response = self.publish(self.midterm)
        self.assertEqual(response.status_code, 409)
        self.assertEqual((response.data["code"], response.data["weight_total"]), ("weights_incomplete", "30.00"))
        self.midterm.refresh_from_db()
        self.assertIsNone(self.midterm.published_at)

    def test_publishing_reports_missing_grades(self):
        self.component("Final", "70", "FINAL")
        self.post_grades(self.midterm, [{"student": self.student.pk, "score": "85"}])
        response = self.publish(self.midterm)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["is_published"])
        self.assertEqual(response.data["missing_grades"], 1)

    def test_weights_stay_at_one_hundred_after_publishing(self):
        final = self.component("Final", "70", "FINAL")
        self.publish(self.midterm)
        response = self.client.patch(f"{BASE}/components/{final.pk}/", {"weight": "60"}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "published_weights")

    def test_published_component_cannot_be_deleted(self):
        self.component("Final", "70", "FINAL")
        self.publish(self.midterm)
        response = self.client.delete(f"{BASE}/components/{self.midterm.pk}/")
        self.assertEqual((response.status_code, response.data["code"]), (409, "published"))

    def test_unpublish_hides_the_component_again(self):
        self.component("Final", "70", "FINAL")
        self.publish(self.midterm)
        response = self.client.post(f"{BASE}/components/{self.midterm.pk}/unpublish/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_published"])
