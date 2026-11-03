from django.test import TestCase

from course_registration.models import Registration, RegistrationItem

from .base import CourseWorld


class RosterWorld(CourseWorld):
    def setUp(self):
        self.build_world()  # self.section (CSE 301) is taught by self.advisor
        self.draft = Registration.objects.create(student=self.student, term=self.term)
        RegistrationItem.objects.create(registration=self.draft, section=self.section, is_retake=True)


class InstructorRosterTests(RosterWorld, TestCase):
    def url(self, section=None):
        return f"/api/courses/my-sections/{(section or self.section).pk}/students/"

    def test_instructor_sees_who_holds_a_seat_in_their_section(self):
        submitted = Registration.objects.create(student=self.other_student, term=self.term, status="SUBMITTED")
        RegistrationItem.objects.create(registration=submitted, section=self.section)
        rows = self.client_for(self.advisor).get(self.url()).data["results"]
        self.assertEqual(
            [(r["student_no"], r["class_year"], r["is_retake"], r["registration_status"]) for r in rows],
            [("1001", 3, True, "DRAFT"), ("1002", 3, False, "SUBMITTED")],
        )

    def test_only_the_sections_own_instructor(self):
        self.assertEqual(self.client_for(self.other_instructor).get(self.url()).status_code, 404)
        self.assertEqual(self.client_for(self.student).get(self.url()).status_code, 403)

    def test_head_roster_has_the_same_rows(self):
        rows = self.client_for(self.head).get(f"/api/courses/manage/sections/{self.section.pk}/students/").data["results"]
        self.assertEqual([(r["student_no"], r["registration_status"]) for r in rows], [("1001", "DRAFT")])


class AdviseeListTests(RosterWorld, TestCase):
    def get(self, user=None, query=""):
        return self.client_for(user or self.advisor).get(f"/api/registration/advisor/students/?term={self.term.pk}{query}")

    def test_advisor_sees_every_advisee_including_those_without_a_form(self):
        rows = self.get().data["results"]
        self.assertEqual([r["student_no"] for r in rows], ["1001", "1002"])
        self.assertEqual(rows[0]["registration"]["status"], "DRAFT")
        self.assertIsNone(rows[1]["registration"])

    def test_status_filter(self):
        self.assertEqual([r["student_no"] for r in self.get(query="&status=NONE").data["results"]], ["1002"])
        self.assertEqual([r["student_no"] for r in self.get(query="&status=DRAFT").data["results"]], ["1001"])
        self.assertEqual(self.get(query="&status=APPROVED").data["results"], [])

    def test_other_advisors_students_and_other_terms_are_not_mixed_in(self):
        self.assertEqual(self.get(self.other_instructor).data["results"], [])
        self.other_student.advisor = self.other_instructor
        self.other_student.save()
        self.assertEqual([r["student_no"] for r in self.get().data["results"]], ["1001"])

    def test_term_is_required_and_students_cannot_ask(self):
        self.assertEqual(self.client_for(self.advisor).get("/api/registration/advisor/students/").status_code, 400)
        self.assertEqual(self.get(self.student).status_code, 403)
