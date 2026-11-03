from datetime import timedelta

from django.test import TestCase

from course_registration.models import CompletedCourse, Registration
from courses.models import TermPlan

from .base import CourseWorld

ADD = "/api/registration/items/"


class AddSectionTests(CourseWorld, TestCase):
    def setUp(self):
        self.build_world()
        self.client = self.client_for(self.student)

    def add(self, section, client=None):
        return (client or self.client).post(ADD, {"section": section.pk}, format="json")

    def test_student_adds_a_section_to_a_draft_form(self):
        response = self.add(self.section)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "DRAFT")
        self.assertEqual(response.data["total_credit"], 3)
        self.assertEqual(response.data["total_ects"], 6)
        self.assertEqual(response.data["items"][0]["section"]["seats_taken"], 1)

    def test_full_section_is_refused(self):
        self.section.quota = 1
        self.section.save()
        self.assertEqual(self.add(self.section, self.client_for(self.other_student)).status_code, 201)
        response = self.add(self.section)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "quota_full")

    def test_same_section_twice_and_another_section_of_the_same_course(self):
        self.add(self.section)
        self.assertEqual(self.add(self.section).data["code"], "already_added")
        second = self.make_section(self.cse301, number=2, meetings=[(3, 9, 12)])
        self.assertEqual(self.add(second).data["code"], "same_course")

    def test_overlapping_hours_are_refused(self):
        self.add(self.section)  # Monday 09-12
        clash = self.make_section(self.course("CSE 303"), meetings=[(1, 11, 13)])
        response = self.add(clash)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "schedule_conflict")
        back_to_back = self.make_section(self.course("CSE 305"), meetings=[(1, 12, 14)])
        self.assertEqual(self.add(back_to_back).status_code, 201)

    def test_credit_and_ects_limits(self):
        self.term.max_credit = 5
        self.term.save()
        self.add(self.section)
        response = self.add(self.make_section(self.course("CSE 303", credit=3)))
        self.assertEqual(response.data["code"], "credit_limit")
        self.term.max_credit, self.term.max_ects = 24, 8
        self.term.save()
        self.assertEqual(self.add(self.make_section(self.course("CSE 307", ects=3))).data["code"], "ects_limit")

    def test_prerequisite_must_be_passed(self):
        advanced = self.course("CSE 401")
        advanced.prerequisites.add(self.cse301)
        section = self.make_section(advanced)
        response = self.add(section)
        self.assertEqual(response.data["code"], "prerequisite_missing")
        self.assertIn("CSE 301", response.data["detail"])
        CompletedCourse.objects.create(student=self.student, course=self.cse301, passed=False)
        self.assertEqual(self.add(section).status_code, 409)
        CompletedCourse.objects.create(student=self.student, course=self.cse301, term=self.term, passed=True)
        self.assertEqual(self.add(section).status_code, 201)

    def test_registration_is_closed_between_and_after_the_windows(self):
        for moment in (self.now + timedelta(days=4), self.now + timedelta(days=11)):
            self.move_clock(moment)
            self.assertEqual(self.add(self.section).data["code"], "registration_closed")
        self.move_clock(self.now + timedelta(days=8))
        self.assertEqual(self.add(self.section).status_code, 201)

    def test_inactive_course_cannot_be_added(self):
        self.cse301.is_active = False
        self.cse301.save()
        self.assertEqual(self.add(self.section).data["code"], "course_inactive")

    def test_only_students_use_the_registration_endpoints(self):
        for user in (self.advisor, self.head, self.admin):
            self.assertEqual(self.add(self.section, self.client_for(user)).status_code, 403)

    def test_mandatory_course_outside_the_plan_is_refused(self):
        other_year = self.make_section(self.course("CSE 101", in_plan=False))
        self.assertEqual(self.add(other_year).data["code"], "not_in_plan")

    def test_only_offered_electives_and_only_as_many_as_the_plan_allows(self):
        self.plan.elective_count = 1
        self.plan.save()
        not_offered = self.make_section(self.elective("UNI 199", offered=False))
        self.assertEqual(self.add(not_offered).data["code"], "elective_not_offered")
        first = self.make_section(self.elective("UNI 101"))
        second = self.make_section(self.elective("UNI 102"))
        self.assertEqual(self.add(first).status_code, 201)
        self.assertEqual(self.add(second).data["code"], "elective_limit")

    def test_student_without_a_plan_cannot_add(self):
        self.student.class_year = 2
        self.student.save()
        self.assertEqual(self.add(self.section).data["code"], "no_plan")

    def test_student_cannot_remove_another_students_item(self):
        registration_data = self.add(self.section, self.client_for(self.other_student)).data
        item_id = registration_data["items"][0]["id"]
        self.assertEqual(self.client.delete(f"{ADD}{item_id}/").status_code, 404)


class ApprovalFlowTests(CourseWorld, TestCase):
    def setUp(self):
        self.build_world()
        self.client = self.client_for(self.student)
        self.registration_id = self.client.post(ADD, {"section": self.section.pk}, format="json").data["id"]

    def submit(self):
        return self.client.post(f"/api/registration/{self.registration_id}/submit/")

    def decide(self, user, action, note=""):
        return self.client_for(user).post(
            f"/api/registration/advisor/{self.registration_id}/{action}/", {"note": note}, format="json",
        )

    def test_submit_then_advisor_approves(self):
        self.assertEqual(self.submit().data["status"], "SUBMITTED")
        listed = self.client_for(self.advisor).get("/api/registration/advisor/?status=SUBMITTED")
        self.assertEqual([row["id"] for row in listed.data["results"]], [self.registration_id])
        response = self.decide(self.advisor, "approve")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "APPROVED")
        self.assertEqual(response.data["decided_by"], self.advisor.pk)
        self.assertEqual(self.submit().data["code"], "already_approved")

    def test_another_instructor_cannot_decide_or_see_the_form(self):
        self.submit()
        self.assertEqual(self.decide(self.other_instructor, "approve").status_code, 404)
        listed = self.client_for(self.other_instructor).get("/api/registration/advisor/")
        self.assertEqual(listed.data["results"], [])

    def test_advisor_cannot_decide_a_draft(self):
        self.assertEqual(self.decide(self.advisor, "approve").data["code"], "not_submitted")

    def test_return_needs_a_note_and_a_change_reopens_the_form(self):
        self.submit()
        self.assertEqual(self.decide(self.advisor, "return").status_code, 400)
        returned = self.decide(self.advisor, "return", "Take CSE 303 too.")
        self.assertEqual(returned.data["status"], "RETURNED")
        self.assertEqual(self.submit().data["status"], "SUBMITTED")

    def test_add_drop_after_approval_needs_a_new_approval(self):
        self.submit()
        self.decide(self.advisor, "approve")
        self.move_clock(self.now + timedelta(days=8))
        item_id = Registration.objects.get(pk=self.registration_id).items.get().pk
        response = self.client.delete(f"{ADD}{item_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "DRAFT")
        self.assertIsNone(response.data["decided_by"])
        self.assertEqual(self.submit().data["code"], "empty_registration")

    def test_form_must_match_the_plan_before_submitting(self):
        cse303 = self.make_section(self.course("CSE 303"), meetings=[(2, 9, 12)])
        elective = self.make_section(self.elective("UNI 101"), meetings=[(4, 9, 11)])
        self.plan.elective_count = 1
        self.plan.save()
        response = self.submit()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "plan_incomplete")
        self.assertEqual(response.data["missing_courses"], ["CSE 303"])
        self.assertEqual((response.data["electives_required"], response.data["electives_chosen"]), (1, 0))
        self.client.post(ADD, {"section": cse303.pk}, format="json")
        self.assertEqual(self.submit().data["code"], "plan_incomplete")
        self.client.post(ADD, {"section": elective.pk}, format="json")
        self.assertEqual(self.submit().data["status"], "SUBMITTED")

    def test_course_with_a_prerequisite_never_taken_is_not_required(self):
        advanced = self.course("CSE 401")
        advanced.prerequisites.add(self.course("CSE 201", in_plan=False))
        self.assertEqual(self.submit().data["status"], "SUBMITTED")

    def test_student_without_advisor_cannot_submit(self):
        self.student.advisor = None
        self.student.save()
        self.assertEqual(self.submit().data["code"], "no_advisor")


class RetakeTests(CourseWorld, TestCase):
    """A third year who failed CSE 101; this term's first-year plan includes it."""

    def setUp(self):
        self.build_world()
        self.client = self.client_for(self.student)
        self.first_year_plan = TermPlan.objects.create(department=self.cse, term=self.term, class_year=1)
        self.cse101 = self.course("CSE 101", credit=4, ects=6, in_plan=False)
        self.first_year_plan.mandatory_courses.add(self.cse101)
        self.retake_section = self.make_section(self.cse101, meetings=[(1, 10, 12)])  # clashes with CSE 301
        CompletedCourse.objects.create(student=self.student, course=self.cse101, passed=False)

    def add(self, section):
        return self.client.post(ADD, {"section": section.pk}, format="json")

    def rows_by_code(self, registration):
        return {row["section"]["course"]["code"]: row for row in registration["items"]}

    def test_failed_lower_year_course_is_added_as_a_retake(self):
        response = self.add(self.retake_section)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["items"][0]["is_retake"])

    def test_failed_prerequisite_means_retake_only_and_the_form_is_still_complete(self):
        # The year-3 plan requires CSE 303, which needs CSE 101: the course Ali failed.
        cse303 = self.course("CSE 303")
        cse303.prerequisites.add(self.cse101)
        cse303_section = self.make_section(cse303, meetings=[(2, 9, 12)])
        registration_id = self.add(self.section).data["id"]
        self.assertEqual(self.add(cse303_section).data["code"], "prerequisite_missing")
        submit = f"/api/registration/{registration_id}/submit/"
        response = self.client.post(submit)
        self.assertEqual(response.data["missing_courses"], [])  # CSE 303 is not required this term
        self.assertEqual(response.data["missing_retakes"], ["CSE 101"])
        self.add(self.retake_section)
        self.assertEqual(self.client.post(submit).data["status"], "SUBMITTED")

    def test_plan_shows_missing_prerequisites(self):
        cse303 = self.course("CSE 303")
        cse303.prerequisites.add(self.cse101)
        rows = self.client.get(f"/api/courses/my-plan/?term={self.term.pk}").data["mandatory_courses"]
        self.assertEqual({row["code"]: row["missing_prerequisites"] for row in rows}, {"CSE 301": [], "CSE 303": ["CSE 101"]})

    def test_only_failed_and_not_yet_passed_courses_are_retakes(self):
        never_failed = self.course("CSE 102", in_plan=False)
        self.first_year_plan.mandatory_courses.add(never_failed)
        self.assertEqual(self.add(self.make_section(never_failed)).data["code"], "not_in_plan")
        CompletedCourse.objects.create(student=self.student, course=self.cse101, term=self.term, passed=True)
        self.assertEqual(self.add(self.retake_section).data["code"], "not_in_plan")

    def test_upper_year_course_is_not_a_retake(self):
        fourth_year_plan = TermPlan.objects.create(department=self.cse, term=self.term, class_year=4)
        cse401 = self.course("CSE 401", in_plan=False)
        fourth_year_plan.mandatory_courses.add(cse401)
        CompletedCourse.objects.create(student=self.student, course=cse401, passed=False)
        self.assertEqual(self.add(self.make_section(cse401)).data["code"], "not_in_plan")

    def test_retake_may_clash_and_the_form_shows_it(self):
        self.add(self.section)  # CSE 301, Monday 09-12
        response = self.add(self.retake_section)  # CSE 101, Monday 10-12
        self.assertEqual(response.status_code, 201, response.data)
        rows = self.rows_by_code(response.data)
        self.assertEqual(rows["CSE 101"]["conflicts_with"], ["CSE 301"])
        self.assertEqual(rows["CSE 301"]["conflicts_with"], ["CSE 101"])

    def test_retake_does_not_count_toward_the_limits(self):
        self.term.max_credit = 3
        self.term.save()
        self.add(self.section)  # 3 credits
        response = self.add(self.retake_section)  # +4 credits, retake
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data["counted_credit"], response.data["total_credit"]), (3, 7))
        self.assertEqual(self.client.post(f"/api/registration/{response.data['id']}/submit/").data["status"], "SUBMITTED")

    def test_offered_retakes_are_required_to_submit(self):
        not_offered = self.course("CSE 102", in_plan=False)  # failed, but no section this term
        self.first_year_plan.mandatory_courses.add(not_offered)
        CompletedCourse.objects.create(student=self.student, course=not_offered, passed=False)
        registration_id = self.add(self.section).data["id"]
        submit = f"/api/registration/{registration_id}/submit/"
        response = self.client.post(submit)
        self.assertEqual(response.data["code"], "plan_incomplete")
        self.assertEqual(response.data["missing_retakes"], ["CSE 101"])
        self.add(self.retake_section)
        self.assertEqual(self.client.post(submit).data["status"], "SUBMITTED")

    def test_student_lists_retakes(self):
        not_offered = self.course("CSE 102", in_plan=False)
        self.first_year_plan.mandatory_courses.add(not_offered)
        CompletedCourse.objects.create(student=self.student, course=not_offered, passed=False)
        rows = self.client.get(f"/api/registration/retakes/?term={self.term.pk}").data
        self.assertEqual({row["code"]: row["required"] for row in rows}, {"CSE 101": True, "CSE 102": False})
        self.assertEqual(self.client.get("/api/registration/retakes/?term=x").status_code, 400)
