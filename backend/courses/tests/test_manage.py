from django.test import TestCase

from course_registration.models import Registration, RegistrationItem
from course_registration.tests.base import CourseWorld
from courses.models import Course

COURSES = "/api/courses/manage/courses/"
SECTIONS = "/api/courses/manage/sections/"


class HeadCourseTests(CourseWorld, TestCase):
    def setUp(self):
        self.build_world()
        self.client = self.client_for(self.head)

    def test_head_creates_a_course_in_their_own_department(self):
        response = self.client.post(COURSES, {
            "code": "CSE 303", "name": "İşletim Sistemleri", "credit": 3, "ects": 5,
            "theory_hours": 3, "practice_hours": 0, "department": self.ee.pk,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        created = Course.objects.get(code="CSE 303")
        self.assertEqual((created.department, created.kind), (self.cse, "MANDATORY"))

    def test_head_cannot_see_or_edit_another_departments_course(self):
        ee_course = self.course("EE 201", department=self.ee)
        self.assertEqual(self.client.patch(f"{COURSES}{ee_course.pk}/", {"name": "x"}, format="json").status_code, 404)
        codes = [row["code"] for row in self.client.get(COURSES).data["results"]]
        self.assertEqual(codes, ["CSE 301"])

    def test_course_cannot_require_itself(self):
        response = self.client.patch(f"{COURSES}{self.cse301.pk}/", {"prerequisites": [self.cse301.pk]}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_other_roles_cannot_manage_courses(self):
        for user in (self.student, self.advisor):
            self.assertEqual(self.client_for(user).get(COURSES).status_code, 403)

    def test_admin_writes_electives_and_heads_only_see_mandatory_courses(self):
        admin = self.client_for(self.admin)
        response = admin.post(COURSES, {"code": "UNI 101", "name": "Müzik Tarihi", "credit": 2, "ects": 3}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual((response.data["kind"], response.data["department"]), ("ELECTIVE", None))
        self.assertEqual([row["code"] for row in admin.get(COURSES).data["results"]], ["UNI 101"])
        self.assertEqual([row["code"] for row in self.client.get(COURSES).data["results"]], ["CSE 301"])
        elective_id = response.data["id"]
        self.assertEqual(self.client.patch(f"{COURSES}{elective_id}/", {"name": "x"}, format="json").status_code, 404)
        self.assertEqual(admin.patch(f"{COURSES}{self.cse301.pk}/", {"name": "x"}, format="json").status_code, 404)

    def test_head_without_department_is_refused(self):
        self.head.department = None
        self.head.save()
        self.assertEqual(self.client.get(COURSES).status_code, 403)


class HeadSectionTests(CourseWorld, TestCase):
    def setUp(self):
        self.build_world()
        self.client = self.client_for(self.head)

    def section_payload(self, **overrides):
        payload = {
            "course": self.cse301.pk, "term": self.term.pk, "number": 2, "quota": 40,
            "instructor": self.advisor.pk,
            "meeting_times": [{"weekday": 2, "start_time": "13:00", "end_time": "16:00", "room": "B-201"}],
        }
        payload.update(overrides)
        return payload

    def test_head_creates_a_section_with_hours(self):
        response = self.client.post(SECTIONS, self.section_payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["seats_taken"], 0)
        self.assertEqual(response.data["meeting_times"][0]["room"], "B-201")

    def test_section_rules(self):
        ee_course = self.course("EE 201", department=self.ee)
        self.assertEqual(self.client.post(SECTIONS, self.section_payload(course=ee_course.pk), format="json").status_code, 400)
        self.assertEqual(self.client.post(SECTIONS, self.section_payload(instructor=self.student.pk), format="json").status_code, 400)
        overlapping = [
            {"weekday": 1, "start_time": "09:00", "end_time": "11:00"},
            {"weekday": 1, "start_time": "10:00", "end_time": "12:00"},
        ]
        self.assertEqual(self.client.post(SECTIONS, self.section_payload(meeting_times=overlapping), format="json").status_code, 400)

    def take_seat(self, student):
        registration = Registration.objects.create(student=student, term=self.term)
        RegistrationItem.objects.create(registration=registration, section=self.section)

    def test_quota_cannot_go_below_taken_seats_and_used_sections_stay(self):
        self.take_seat(self.student)
        self.take_seat(self.other_student)
        url = f"{SECTIONS}{self.section.pk}/"
        self.assertEqual(self.client.patch(url, {"quota": 1}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"quota": 2}, format="json").status_code, 200)
        self.assertEqual(self.client.delete(url).data["code"], "section_in_use")
        students = self.client.get(f"{url}students/").data["results"]
        self.assertEqual([row["student_no"] for row in students], ["1001", "1002"])

    def test_unused_section_can_be_deleted(self):
        self.assertEqual(self.client.delete(f"{SECTIONS}{self.section.pk}/").status_code, 204)

    def test_other_head_cannot_touch_the_section(self):
        other = self.client_for(self.other_head)
        self.assertEqual(other.patch(f"{SECTIONS}{self.section.pk}/", {"quota": 5}, format="json").status_code, 404)

    def test_elective_sections_are_opened_by_admin_only(self):
        elective = self.elective("UNI 101")
        payload = self.section_payload(course=elective.pk, number=1)
        self.assertEqual(self.client.post(SECTIONS, payload, format="json").status_code, 400)
        self.assertEqual(self.client_for(self.admin).post(SECTIONS, payload, format="json").status_code, 201)
        mandatory = self.section_payload()
        self.assertEqual(self.client_for(self.admin).post(SECTIONS, mandatory, format="json").status_code, 400)


PLANS = "/api/courses/manage/plans/"


class TermPlanTests(CourseWorld, TestCase):
    def setUp(self):
        self.build_world()
        self.client = self.client_for(self.head)
        self.cse303 = self.course("CSE 303", in_plan=False)
        self.uni101 = self.elective("UNI 101", offered=False)

    def plan_payload(self, **overrides):
        payload = {"term": self.term.pk, "class_year": 2, "mandatory_courses": [self.cse303.pk], "elective_count": 1}
        payload.update(overrides)
        return payload

    def test_head_plans_mandatory_courses_and_elective_count_for_own_department(self):
        response = self.client.post(PLANS, self.plan_payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["department"], self.cse.pk)
        self.assertEqual([c["code"] for c in response.data["mandatory_courses"]], ["CSE 303"])
        self.assertEqual(response.data["elective_count"], 1)
        url = f"{PLANS}{response.data['id']}/"
        self.assertEqual(self.client.patch(url, {"elective_count": 2}, format="json").data["elective_count"], 2)

    def test_only_admin_chooses_electives(self):
        url = f"{PLANS}{self.plan.pk}/"
        self.assertEqual(self.client.patch(url, {"elective_options": [self.uni101.pk]}, format="json").status_code, 403)
        response = self.client_for(self.admin).patch(url, {"elective_options": [self.uni101.pk]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c["code"] for c in response.data["elective_options"]], ["UNI 101"])
        # A mandatory course is not an elective option.
        bad = self.client_for(self.admin).patch(url, {"elective_options": [self.cse303.pk]}, format="json")
        self.assertEqual(bad.status_code, 400)

    def test_admin_also_sets_mandatory_courses_and_counts(self):
        response = self.client_for(self.admin).post(
            PLANS, self.plan_payload(department=self.cse.pk, elective_options=[self.uni101.pk]), format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn("department", self.client_for(self.admin).post(PLANS, self.plan_payload(class_year=4), format="json").data)

    def test_plan_rules(self):
        ee_course = self.course("EE 201", department=self.ee)
        self.assertEqual(self.client.post(PLANS, self.plan_payload(mandatory_courses=[ee_course.pk]), format="json").status_code, 400)
        self.assertEqual(self.client.post(PLANS, self.plan_payload(department=self.ee.pk), format="json").status_code, 403)
        self.assertEqual(self.client.post(PLANS, self.plan_payload(class_year=3), format="json").status_code, 400)

    def test_other_department_head_cannot_see_the_plan(self):
        other = self.client_for(self.other_head)
        self.assertEqual(other.get(f"{PLANS}{self.plan.pk}/").status_code, 404)
        self.assertEqual(other.get(PLANS).data["results"], [])

    def test_student_reads_own_plan(self):
        self.plan.elective_options.add(self.uni101)
        response = self.client_for(self.student).get(f"/api/courses/my-plan/?term={self.term.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c["code"] for c in response.data["mandatory_courses"]], ["CSE 301"])
        self.assertEqual([c["code"] for c in response.data["elective_options"]], ["UNI 101"])
        self.student.class_year = 1
        self.student.save()
        self.assertEqual(self.client_for(self.student).get(f"/api/courses/my-plan/?term={self.term.pk}").status_code, 404)


class CatalogAndTermTests(CourseWorld, TestCase):
    def setUp(self):
        self.build_world()

    def test_catalog_shows_the_course_card(self):
        response = self.client_for(self.student).get(f"/api/courses/sections/?term={self.term.pk}&search=mimari")
        card = response.data["results"][0]
        self.assertEqual(card["course"]["code"], "CSE 301")
        self.assertEqual(card["course"]["department"], "CSE - Bilgisayar Mühendisliği")
        self.assertEqual((card["number"], card["quota"], card["seats_taken"]), (1, 2, 0))
        self.assertEqual(card["instructor"]["email"], "advisor@example.test")

    def test_instructor_sees_their_sections(self):
        rows = self.client_for(self.advisor).get("/api/courses/my-sections/").data["results"]
        self.assertEqual([row["id"] for row in rows], [self.section.pk])
        self.assertEqual(self.client_for(self.other_instructor).get("/api/courses/my-sections/").data["results"], [])

    def test_only_admin_opens_terms(self):
        payload = {
            "year": 2027, "season": "SPRING",
            "registration_start": "2027-02-01T08:00:00Z", "registration_end": "2027-02-05T08:00:00Z",
            "add_drop_start": "2027-02-15T08:00:00Z", "add_drop_end": "2027-02-19T08:00:00Z",
        }
        self.assertEqual(self.client_for(self.head).post("/api/courses/terms/", payload, format="json").status_code, 403)
        response = self.client_for(self.admin).post("/api/courses/terms/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual((response.data["max_credit"], response.data["max_ects"]), (24, 30))
        backwards = dict(payload, season="SUMMER", registration_end="2027-01-01T08:00:00Z")
        self.assertEqual(self.client_for(self.admin).post("/api/courses/terms/", backwards, format="json").status_code, 400)
