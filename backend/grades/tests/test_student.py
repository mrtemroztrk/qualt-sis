from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from grades.models import Grade, GradingComponent
from grades.services import course_average

from .test_teaching import BASE, TeachingWorld

MINE = "/api/grades/mine/"


class CourseAverageTests(SimpleTestCase):
    def test_average_uses_graded_components_and_their_maximums(self):
        result = course_average([
            (Decimal("30"), Decimal("80"), Decimal("100")),
            (Decimal("20"), Decimal("18"), Decimal("20")),  # 90%
            (Decimal("50"), None, Decimal("100")),
        ])
        self.assertEqual(result, {
            "average": Decimal("84.00"), "graded_weight": Decimal("50.00"), "earned": Decimal("42.00"),
        })

    def test_nothing_graded_has_no_average(self):
        result = course_average([(Decimal("100"), None, Decimal("100"))])
        self.assertEqual((result["average"], result["graded_weight"]), (None, Decimal("0.00")))


class StudentGradesTests(TeachingWorld, TestCase):
    def setUp(self):
        self.build_grading_world()
        now = timezone.now()
        self.midterm = self.component("Midterm", "30")
        self.project = self.component("Project", "20", "PROJECT", max_score="20")
        self.final = self.component("Final", "50", "FINAL")
        GradingComponent.objects.filter(pk__in=[self.midterm.pk, self.project.pk]).update(published_at=now)
        for component, score in ((self.midterm, "80"), (self.project, "18"), (self.final, "70")):
            Grade.objects.create(component=component, student=self.student, score=Decimal(score))
        Grade.objects.create(component=self.midterm, student=self.other_student, score=Decimal("40"))

    def test_student_sees_published_scores_and_average(self):
        response = self.client_for(self.student).get(MINE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row["course"]["code"], "CSE 301")
        scores = {component["name"]: (component["is_published"], component["score"]) for component in row["components"]}
        self.assertEqual(scores, {
            "Midterm": (True, "80.00"), "Project": (True, "18.00"), "Final": (False, None),
        })
        self.assertEqual((row["average"], row["graded_weight"], row["earned"]), ("84.00", "50.00", "42.00"))

    def test_students_only_see_their_own_scores(self):
        row = self.client_for(self.other_student).get(MINE).data[0]
        scores = {component["name"]: component["score"] for component in row["components"]}
        self.assertEqual(scores, {"Midterm": "40.00", "Project": None, "Final": None})
        self.assertEqual(row["average"], "40.00")

    def test_sections_without_an_approved_form_are_not_listed(self):
        self.assertEqual(self.client_for(self.drafting).get(MINE).data, [])

    def test_term_filter(self):
        client = self.client_for(self.student)
        self.assertEqual(len(client.get(MINE, {"term": self.term.pk}).data), 1)
        self.assertEqual(client.get(MINE, {"term": self.term.pk + 999}).data, [])
        self.assertEqual(client.get(MINE, {"term": "abc"}).status_code, 400)

    def test_only_students_use_my_grades(self):
        for user in (self.advisor, self.head, self.admin):
            with self.subTest(user=user.email):
                self.assertEqual(self.client_for(user).get(MINE).status_code, 403)

    def test_instructor_sheet_averages_every_graded_component(self):
        response = self.client.get(f"{BASE}/sections/{self.section.pk}/sheet/")
        rows = {row["id"]: row for row in response.data["students"]}
        # (30×80 + 20×90 + 50×70) ÷ 100, the unpublished final included.
        self.assertEqual((rows[self.student.pk]["average"], rows[self.student.pk]["earned"]), ("77.00", "77.00"))
        self.assertEqual(rows[self.other_student.pk]["graded_weight"], "30.00")


class SeedGradesDemoTests(TeachingWorld, TestCase):
    def setUp(self):
        self.build_grading_world()

    def test_seed_adds_sample_grading_once(self):
        call_command("seed_grades_demo", stdout=StringIO())
        components = list(self.section.grading_components.all())
        self.assertEqual([c.name for c in components], ["Midterm", "Project", "Final"])
        self.assertEqual(sum(c.weight for c in components), Decimal("100"))
        self.assertEqual(Grade.objects.count(), 4)  # two approved students × two published components
        call_command("seed_grades_demo", stdout=StringIO())
        self.assertEqual(GradingComponent.objects.count(), 3)
