from decimal import Decimal

from django.test import TestCase

from learning_outcomes.scoring import learning_outcome_scores, program_outcome_profile

from .base import ScoreWorld

BASE = "/api/learning-outcomes"


def one_decimal(value):
    return Decimal(value).quantize(Decimal("0.1"))


class PdfExampleTests(ScoreWorld, TestCase):
    """Slide 6 of the project guidelines: LO1 86.0, LO2 82.9, PO1 85.0, PO2 82.9."""

    def setUp(self):
        self.build_score_world()
        self.build_pdf_example()

    def test_learning_outcome_scores(self):
        scores = learning_outcome_scores(self.section, [self.student.pk], published_only=True)[self.student.pk]
        self.assertEqual(one_decimal(scores[self.lo1.pk]), Decimal("86.0"))
        self.assertEqual(one_decimal(scores[self.lo2.pk]), Decimal("82.9"))

    def test_program_outcome_scores(self):
        profile = {row["code"]: row for row in program_outcome_profile(self.student)}
        self.assertEqual(one_decimal(profile["PO1"]["score"]), Decimal("85.0"))
        self.assertEqual(one_decimal(profile["PO2"]["score"]), Decimal("82.9"))
        self.assertEqual(profile["PO1"]["courses"], ["CSE 301"])

    def test_student_sees_their_profile(self):
        response = self.client_for(self.student).get(f"{BASE}/mine/")
        self.assertEqual(response.status_code, 200)
        scores = {row["code"]: row["score"] for row in response.data["program_outcomes"]}
        self.assertEqual(scores, {"PO1": "84.95", "PO2": "82.86"})

    def test_unmeasured_program_outcomes_have_no_score(self):
        profile = {row["code"]: row["score"] for row in program_outcome_profile(self.other_student)}
        self.assertEqual(profile, {"PO1": None, "PO2": None})


class ScoringRulesTests(ScoreWorld, TestCase):
    def setUp(self):
        self.build_score_world()
        self.midterm = self.grading_component("Midterm", "40")
        self.quiz = self.grading_component("Quiz", "60")
        self.quiz.max_score = Decimal("20")
        self.quiz.save()
        self.link(self.midterm, self.lo1, 50)
        self.link(self.quiz, self.lo1, 50)
        self.program_link(self.lo1, self.po1, 100)

    def test_scores_use_each_components_maximum(self):
        self.grade(self.midterm, self.student, "70")
        self.grade(self.quiz, self.student, "18")  # 90%
        self.publish(self.midterm, self.quiz)
        scores = learning_outcome_scores(self.section, [self.student.pk], published_only=True)
        self.assertEqual(scores[self.student.pk][self.lo1.pk], Decimal("80"))

    def test_students_only_count_published_components(self):
        self.grade(self.midterm, self.student, "70")
        self.grade(self.quiz, self.student, "18")
        self.publish(self.midterm)
        profile = {row["code"]: row["score"] for row in program_outcome_profile(self.student)}
        self.assertEqual(profile["PO1"], Decimal("70.00"))

    def test_link_changes_apply_at_once(self):
        self.grade(self.midterm, self.student, "70")
        self.grade(self.quiz, self.student, "18")
        self.publish(self.midterm, self.quiz)
        self.quiz.outcome_links.update(weight=100)
        profile = {row["code"]: row["score"] for row in program_outcome_profile(self.student)}
        self.assertEqual(profile["PO1"], Decimal("83.33"))  # (50×70 + 100×90) ÷ 150

    def test_only_the_students_department_outcomes_are_listed(self):
        self.program_link(self.lo1, self.po2, 100)
        codes = [row["code"] for row in program_outcome_profile(self.student)]
        self.assertEqual(codes, ["PO1", "PO2"])
        self.po2.is_active = False
        self.po2.save()
        self.assertEqual([row["code"] for row in program_outcome_profile(self.student)], ["PO1"])

    def test_a_retaken_course_counts_from_the_latest_attempt(self):
        self.grade(self.midterm, self.student, "40")
        self.publish(self.midterm)
        retake = self.later_term_section()
        self.enroll(self.student, retake)
        final = self.grading_component("Final", "100", section=retake)
        self.link(final, self.lo1, 100)

        # Nothing graded in the retake yet: the earlier attempt still counts.
        self.assertEqual(program_outcome_profile(self.student)[0]["score"], Decimal("40.00"))

        self.grade(final, self.student, "75")
        self.assertEqual(program_outcome_profile(self.student)[0]["score"], Decimal("40.00"))  # unpublished
        self.publish(final)
        self.assertEqual(program_outcome_profile(self.student)[0]["score"], Decimal("75.00"))


class ScoreViewTests(ScoreWorld, TestCase):
    def setUp(self):
        self.build_score_world()
        self.build_pdf_example()

    def test_instructor_sees_learning_outcome_scores_with_unpublished_grades(self):
        final = self.grading_component("Final", "0.01")
        self.link(final, self.lo1, 100)
        self.grade(final, self.other_student, "50")
        response = self.client_for(self.advisor).get(f"{BASE}/teaching/sections/{self.section.pk}/scores/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["code"] for row in response.data["learning_outcomes"]], ["LO1", "LO2"])
        rows = {row["id"]: row["scores"] for row in response.data["students"]}
        self.assertEqual(rows[self.other_student.pk], {str(self.lo1.pk): "50.00", str(self.lo2.pk): None})
        self.assertEqual(rows[self.student.pk][str(self.lo2.pk)], "82.86")

    def test_scores_are_private_to_the_sections_instructor(self):
        url = f"{BASE}/teaching/sections/{self.section.pk}/scores/"
        self.assertEqual(self.client_for(self.other_instructor).get(url).status_code, 404)
        self.assertEqual(self.client_for(self.student).get(url).status_code, 403)

    def test_head_reads_profiles_of_their_departments_students(self):
        url = f"{BASE}/students/{self.student.pk}/"
        response = self.client_for(self.head).get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["student"]["id"], self.student.pk)
        self.assertEqual(response.data["program_outcomes"][0]["score"], "84.95")
        self.assertEqual(self.client_for(self.admin).get(url).status_code, 200)
        self.assertEqual(self.client_for(self.other_head).get(url).status_code, 404)
        for user in (self.advisor, self.student):
            with self.subTest(user=user.email):
                self.assertEqual(self.client_for(user).get(url).status_code, 403)

    def test_only_students_have_a_mine_page(self):
        self.assertEqual(self.client_for(self.head).get(f"{BASE}/mine/").status_code, 403)


class StudentListTests(ScoreWorld, TestCase):
    URL = f"{BASE}/students/"

    def setUp(self):
        self.build_score_world()
        self.ee_student = self.user("ee@example.test", "STUDENT", department=self.ee, student_no="2001", class_year=1)

    def ids(self, response):
        return [row["id"] for row in response.data["results"]]

    def test_head_lists_their_departments_students(self):
        response = self.client_for(self.head).get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ids(response), [self.student.pk, self.other_student.pk])
        self.assertEqual(response.data["results"][0]["student_no"], "1001")
        # Asking for another department does not widen a HEAD's list.
        self.assertEqual(self.ids(self.client_for(self.head).get(self.URL, {"department": self.ee.pk})), [])

    def test_admin_lists_every_student_and_can_narrow_by_department(self):
        admin = self.client_for(self.admin)
        self.assertEqual(len(self.ids(admin.get(self.URL))), 3)
        self.assertEqual(self.ids(admin.get(self.URL, {"department": self.ee.pk})), [self.ee_student.pk])
        self.assertEqual(admin.get(self.URL, {"department": "x"}).status_code, 400)

    def test_search_matches_number_and_email(self):
        head = self.client_for(self.head)
        self.assertEqual(self.ids(head.get(self.URL, {"search": "1002"})), [self.other_student.pk])
        self.assertEqual(self.ids(head.get(self.URL, {"search": "s1@"})), [self.student.pk])

    def test_staff_and_people_are_not_listed_to_other_roles(self):
        rows = self.ids(self.client_for(self.admin).get(self.URL))
        self.assertNotIn(self.advisor.pk, rows)
        for user in (self.advisor, self.student):
            with self.subTest(user=user.email):
                self.assertEqual(self.client_for(user).get(self.URL).status_code, 403)
