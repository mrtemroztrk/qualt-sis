from datetime import timedelta

from django.test import TestCase

from course_registration.models import Registration, RegistrationItem

from .base import CourseWorld

SCHEDULE = "/api/registration/schedule/"


class ScheduleTests(CourseWorld, TestCase):
    def setUp(self):
        self.build_world()
        self.client = self.client_for(self.student)
        # CSE 301 is Monday 09-12 (from the base world).
        self.cse303 = self.make_section(self.course("CSE 303", "İşletim Sistemleri"), meetings=[(3, 13, 15), (1, 13, 14)])
        self.retake = self.make_section(self.course("CSE 101", in_plan=False), meetings=[(1, 10, 12)])
        self.elective = self.make_section(self.elective("UNI 101"))  # no meeting times

    def form(self, student, status, sections, approved=True):
        registration = Registration.objects.create(student=student, term=self.term, status=status)
        for section, is_retake in sections:
            RegistrationItem.objects.create(registration=registration, section=section, is_retake=is_retake)
        if approved:
            registration.approved_items = [{"section": s.pk, "is_retake": r} for s, r in sections]
            registration.last_approved_at = self.now
            registration.save()
        return registration

    def get(self, client=None, term=None):
        return (client or self.client).get(f"{SCHEDULE}?term={term or self.term.pk}")

    def test_approved_form_is_grouped_by_day_and_sorted_by_time(self):
        registration = self.form(self.student, Registration.Status.APPROVED, [
            (self.cse303, False), (self.section, False), (self.retake, True), (self.elective, False),
        ])
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["registration_id"], registration.pk)
        self.assertFalse(response.data["has_pending_changes"])
        days = response.data["days"]
        self.assertEqual([(day["weekday"], day["name"]) for day in days], [(1, "Monday"), (3, "Wednesday")])
        monday = [(s["start_time"], s["end_time"], s["course"]["code"]) for s in days[0]["slots"]]
        self.assertEqual(monday, [
            ("09:00:00", "12:00:00", "CSE 301"),
            ("10:00:00", "12:00:00", "CSE 101"),
            ("13:00:00", "14:00:00", "CSE 303"),
        ])
        slots = {s["course"]["code"]: s for s in days[0]["slots"]}
        self.assertEqual(slots["CSE 301"]["conflicts_with"], ["CSE 101"])
        self.assertEqual(slots["CSE 101"]["conflicts_with"], ["CSE 301"])
        self.assertTrue(slots["CSE 101"]["is_retake"])
        self.assertEqual(slots["CSE 303"]["conflicts_with"], [])
        self.assertEqual(response.data["unscheduled"], ["UNI 101"])

    def test_a_form_never_approved_has_no_schedule(self):
        for status in ("DRAFT", "SUBMITTED", "RETURNED"):
            Registration.objects.filter(student=self.student).delete()
            self.form(self.student, status, [(self.section, False)], approved=False)
            self.assertEqual(self.get().status_code, 404, status)

    def test_schedule_uses_the_sections_current_hours(self):
        self.form(self.student, Registration.Status.APPROVED, [(self.section, False)])
        self.section.meeting_times.update(room="B-201")
        self.assertEqual(self.get().data["days"][0]["slots"][0]["room"], "B-201")

    def test_another_students_schedule_is_not_visible(self):
        self.form(self.other_student, Registration.Status.APPROVED, [(self.section, False)])
        self.assertEqual(self.get().status_code, 404)

    def test_term_is_required_and_only_students_ask(self):
        self.assertEqual(self.client.get(SCHEDULE).status_code, 400)
        self.assertEqual(self.get(term=999).status_code, 404)
        self.assertEqual(self.get(self.client_for(self.advisor)).status_code, 403)


class ScheduleDuringAddDropTests(CourseWorld, TestCase):
    """The last approved schedule stays visible while add-drop changes wait for approval."""

    def setUp(self):
        self.build_world()
        self.client = self.client_for(self.student)
        self.cse303 = self.make_section(self.course("CSE 303"), meetings=[(2, 9, 12)])

    def codes(self):
        response = self.get()
        return response.data["has_pending_changes"], sorted(
            slot["course"]["code"] for day in response.data["days"] for slot in day["slots"]
        )

    def get(self):
        return self.client.get(f"{SCHEDULE}?term={self.term.pk}")

    def approve(self, registration_id):
        self.client.post(f"/api/registration/{registration_id}/submit/")
        response = self.client_for(self.advisor).post(f"/api/registration/advisor/{registration_id}/approve/")
        self.assertEqual(response.data["status"], "APPROVED")

    def test_drop_keeps_the_approved_schedule_until_the_advisor_approves_again(self):
        self.client.post("/api/registration/items/", {"section": self.section.pk}, format="json")
        form = self.client.post("/api/registration/items/", {"section": self.cse303.pk}, format="json").data
        self.assertEqual(self.get().status_code, 404)  # not approved yet
        self.approve(form["id"])
        self.assertEqual(self.codes(), (False, ["CSE 301", "CSE 303"]))

        # Add-drop: the student drops CSE 303 and the plan no longer requires it.
        self.move_clock(self.now + timedelta(days=8))
        self.plan.mandatory_courses.remove(self.cse303.course)
        item = next(i for i in form["items"] if i["section"]["id"] == self.cse303.pk)
        self.assertEqual(self.client.delete(f"/api/registration/items/{item['id']}/").data["status"], "DRAFT")
        self.assertEqual(self.codes(), (True, ["CSE 301", "CSE 303"]))  # still the approved version

        self.approve(form["id"])
        self.assertEqual(self.codes(), (False, ["CSE 301"]))
